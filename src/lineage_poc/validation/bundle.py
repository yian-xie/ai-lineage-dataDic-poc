"""Strict, read-only validation shared by generation, enrichment, and HTML."""
from __future__ import annotations

import argparse
import copy
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path

from lineage_poc.dictionary.description_provenance import DESCRIPTION_COLUMNS
from lineage_poc.dictionary.generate import ADDED_MAPPING_COLUMNS, ASSET_COLUMNS, FIELD_COLUMNS
from lineage_poc.dictionary.io import (
    CSV_FILES, ID_COLUMNS, equal, parse_json, pointer, read_tables, require, scoped,
)
from lineage_poc.dictionary.legacy_projection import COLUMNS, cell, jtype, walk
from lineage_poc.enrichment.contracts import ENRICHMENT_COLUMNS, RUBRIC_ID, description_reference, eligible
from .descriptions import nonempty, validate_assessment, validate_sentences

SOURCE_INVARIANTS = [
    'source_field_id', 'source_asset_id', 'hvr_field_id', 'hvr_asset_id',
    'ultracs_field_id', 'ultracs_field_name', 'source_name_origin', 'business_field_label',
    'identity_scope', 'source_locator', 'source_references_json', 'source_program',
    'ultracs_source_path', 'hvr_parameter_source_path', 'source_description',
    'source_description_origin', 'business_definition', 'definition_status',
    'business_review_json', 'extract_file', 'extract_column', 'extract_position',
    'basic_expression', 'basic_transformation', 'basic_comment', 'basic_source_line',
    'hvr_type', 'hvr_obfuscation', 'hvr_cleanup_json', 'hvr_cleanup_enabled',
    'hvr_cleanup_remove_chars_json', 'primary_target_field_id', 'source_primary_target_json',
    'original_mapping_confidence', 'original_mapping_notes', 'original_record_json',
    'source_file', 'source_record_reference', 'source_record_key_reference',
    'source_attribute_position', 'source_value_position', 'source_subvalue_position',
    'source_file_binding_status',
] + ['source_' + column for column in DESCRIPTION_COLUMNS + ENRICHMENT_COLUMNS]
DESCRIPTION_SURFACES = ['description', 'description_origin'] + DESCRIPTION_COLUMNS


class Checks:
    def __init__(self):
        self.count = 0

    def __call__(self, condition, message):
        self.count += 1
        require(condition, 'Bundle validation failed: ' + message)


def _ids(value, label, check):
    check(isinstance(value, list) and all(nonempty(item) for item in value),
          label + ' must be an array of nonempty IDs')
    check(len(value) == len(set(value)), label + ' contains duplicate IDs')
    return value


def _description(row, values, prefix, text, label, check):
    source_type = row[prefix + 'source_type']
    check(source_type in {'ai_generated', 'existing_metadata', 'unknown', 'not_supplied'},
          label + ': invalid description source type')
    check((not text.strip()) == (source_type == 'not_supplied'),
          label + ': description availability disagrees with its source type')
    provenance = values[prefix + 'provenance_json']
    check(isinstance(provenance, dict) and provenance.get('source_type') == source_type,
          label + ': provenance source_type disagrees with its description')
    if 'description_pointer' in provenance:
        check(provenance['description_pointer'] == row[prefix + 'source_pointer'],
              label + ': description pointer disagrees with its provenance')
    if 'source_reference' in provenance:
        check(cell(provenance['source_reference']) == row[prefix + 'source_reference'],
              label + ': description reference disagrees with its provenance')


def _coverage(row, values, check):
    original = values['original_record_json']
    provenance = values['provenance_json']
    check(isinstance(original, dict) and isinstance(provenance, dict),
          'Original record and provenance must be objects')
    base = provenance.get('input_pointer')
    check(isinstance(base, str) and base.startswith('/'), 'Original record needs an exact input pointer')
    expected = {base + path: (path, value) for path, value in walk(original)}
    coverage = values['input_property_map_json']
    check(isinstance(coverage, list), 'Input property coverage must be an array')
    check(len(coverage) == len(expected), 'Input property coverage omits or invents original JSON nodes')
    seen = set()
    for item in coverage:
        check(isinstance(item, dict), 'Input property coverage entries must be objects')
        source_pointer = item.get('input_pointer')
        check(isinstance(source_pointer, str) and source_pointer in expected and source_pointer not in seen,
              'Duplicate or unsupported original input pointer')
        seen.add(source_pointer)
        relative, original_value = expected[source_pointer]
        check(item.get('value_type') == jtype(original_value), 'Input property value_type changed')
        destinations = item.get('destinations')
        check(isinstance(destinations, list) and bool(destinations), 'Input property has no preserving destination')
        check({'column': 'original_record_json', 'json_pointer': relative} in destinations,
              'Every input property must retain its exact original_record_json destination')
        destination_keys = set()
        kinds = set()
        for destination in destinations:
            check(isinstance(destination, dict) and set(destination) == {'column', 'json_pointer'},
                  'Unsupported input property destination')
            column, path = destination['column'], destination['json_pointer']
            check(isinstance(column, str) and column in row and isinstance(path, str),
                  'Input property destination column/pointer is invalid')
            destination_key = column, path
            check(destination_key not in destination_keys, 'Duplicate input property destination')
            destination_keys.add(destination_key)
            if column in values:
                actual = pointer(values[column], path)
                check(equal(actual, original_value), 'Input property destination no longer preserves the input value')
                if column != 'original_record_json':
                    kinds.add('structured')
            else:
                check(path == '', 'A scalar property destination cannot have a nested pointer')
                actual = row[column]
                escaping = provenance.get('csv_text_escaping', {}).get(column)
                if escaping:
                    check(escaping.get('method') == 'one_apostrophe_prefix'
                          and escaping.get('escaped_prefix_count') == 1
                          and actual == "'" + escaping.get('original_value', ''),
                          'CSV formula escaping metadata does not resolve')
                    actual = escaping['original_value']
                check(actual == cell(original_value), 'Visible input property projection changed without a coverage update')
                kinds.add('visible')
        state = 'verified_visible' if 'visible' in kinds else 'verified_structured' if kinds else 'verified_raw'
        check(item.get('coverage_state') == state, 'Input property coverage_state overstates its preserving destinations')
    return len(expected)


def _validate_tables(tables, check):
    required = {
        'asset_registry.csv': ASSET_COLUMNS, 'field_catalog.csv': FIELD_COLUMNS,
        'data_dictionary.csv': parse_json(COLUMNS.read_text(encoding='utf-8')) + ADDED_MAPPING_COLUMNS,
    }
    for name, table in tables.items():
        check(set(required[name]) <= set(table.headers), name + ': missing required contract columns')
        seen = set()
        for row in table.rows:
            check(all(nonempty(row[column]) for column in ('graph_id', 'snapshot_id', ID_COLUMNS[name])),
                  name + ': empty scoped identity')
            key = scoped(row, ID_COLUMNS[name])
            check(key not in seen, name + ': duplicate scoped identity')
            seen.add(key)
    assets, fields, mappings = (tables[name] for name in CSV_FILES)
    a_map, f_map, m_map = (table.index() for table in (assets, fields, mappings))
    scopes = [{(row['graph_id'], row['snapshot_id']) for row in table.rows}
              for table in (assets, fields, mappings)]
    check(scopes[0] == scopes[1] == scopes[2], 'The three files contain different graph/snapshot sets')

    def fk(index, row, identity, label):
        key = row['graph_id'], row['snapshot_id'], identity
        check(nonempty(identity) and key in index, label + ': missing or cross-scope ID ' + str(identity))
        return index[key]

    expected_up, expected_down, incidents = defaultdict(set), defaultdict(set), defaultdict(set)
    asset_up, asset_down, counts, membership = defaultdict(set), defaultdict(set), Counter(), defaultdict(set)
    for row, values in zip(fields.rows, fields.json_rows):
        key = scoped(row, 'field_id')
        fk(a_map, row, row['asset_id'], 'Field asset')
        asset_key = row['graph_id'], row['snapshot_id'], row['asset_id']
        counts[asset_key] += 1
        membership[asset_key].add(row['field_id'])
        original = values['original_field_json']
        check(isinstance(original, dict) and original.get('field_id') == row['field_id'],
              'Invalid canonical field object')
        for column, property_name in (
            ('field_name', 'field_name'), ('field_kind', 'field_kind'), ('source_system', 'system'),
            ('layer', 'stage'), ('data_type', 'data_type'), ('description', 'description'),
            ('description_origin', 'description_origin'), ('business_definition', 'business_definition'),
        ):
            if property_name in original:
                check(row[column] == cell(original[property_name]),
                      'Canonical field scalar disagrees with original_field_json: ' + column)
        _description(row, values, 'description_', row['description'], row['field_id'], check)
        for column in ('upstream_field_ids_json', 'downstream_field_ids_json'):
            for identity in _ids(values[column], column, check):
                fk(f_map, row, identity, 'Field adjacency')
        check(isinstance(values['transformation_logic_json'], list), 'Field transformation logic must be an array')
        if row['source_system'] == 'Ultracs':
            check(not row['source_file'] and row['physical_binding_status'] == 'file_binding_not_supplied',
                  'A BASIC record context must not be promoted to a physical Ultracs file')
            if row['record_key_reference']:
                check(not row['attribute_position'], '@ID must not become attribute zero')

    operations, operation_rows = {}, defaultdict(set)
    source_definitions, archived, mapping_pairs = {}, {}, set()
    represented_fields = set()
    raw_nodes = 0
    for row, values in zip(mappings.rows, mappings.json_rows):
        scope = row['graph_id'], row['snapshot_id']
        entry = row['dictionary_entry_id']
        source_key = scope + (row['source_entry_id'],)
        check(nonempty(row['source_entry_id']), 'Dictionary row has no source_entry_id')
        definition = {column: values.get(column, row.get(column)) for column in SOURCE_INVARIANTS
                      if column in row}
        check(source_key not in source_definitions or equal(source_definitions[source_key], definition),
              'Conflicting metadata for a repeated source mapping')
        source_definitions[source_key] = definition
        pair = scope + (row['source_field_id'], row['target_field_id'])
        check(pair not in mapping_pairs, 'Duplicate source/target association')
        mapping_pairs.add(pair)
        for field_column, asset_column in (
            ('source_field_id', 'source_asset_id'), ('hvr_field_id', 'hvr_asset_id'),
            ('target_field_id', 'target_asset_id'),
        ):
            if field_column == 'target_field_id' and not row[field_column] and row['row_kind'] == 'no_documented_target':
                continue
            field_row, _ = fk(f_map, row, row[field_column], 'Dictionary field')
            fk(a_map, row, row[asset_column], 'Dictionary asset')
            check(field_row['asset_id'] == row[asset_column], 'Dictionary field/asset join disagrees')
        for prefix, field_id, column in (
            ('source_', row['source_field_id'], 'source_description'),
            ('snowflake_', row['target_field_id'], 'snowflake_description'),
        ):
            _description(row, values, prefix + 'description_', row[column], entry, check)
            if not field_id and row['row_kind'] == 'no_documented_target':
                continue
            canonical_row, canonical_values = fk(f_map, row, field_id, 'Description mirror')
            check(row[column] == canonical_row['description'], 'Dictionary description disagrees with its canonical field')
            origins = {canonical_row['description_origin']}
            if canonical_row.get('description_generation_status') != 'draft':
                origins.add('recorded_input' if row[column] else 'unknown')
            check(row[prefix + 'description_origin'] in origins,
                  'Dictionary description origin disagrees with its canonical field')
            for description_column in DESCRIPTION_COLUMNS:
                name = prefix + description_column
                check(equal(values[name], canonical_values[description_column])
                      if name in values else row[name] == canonical_row[description_column],
                      'Dictionary description provenance mirror disagrees: ' + name)
            if prefix == 'source_':
                for enrichment_column in ENRICHMENT_COLUMNS:
                    name = 'source_' + enrichment_column
                    if name in row or enrichment_column in canonical_row:
                        check(name in row and enrichment_column in canonical_row,
                              'Enrichment columns must exist in both canonical and source mirrors')
                        check(equal(values[name], canonical_values[enrichment_column])
                              if name in values else row[name] == canonical_row[enrichment_column],
                              'Source description assessment mirror disagrees')
        catalog = values['field_catalog_json']
        check(isinstance(catalog, list), 'Embedded field catalog must be an array')
        local_fields = {}
        for node in catalog:
            check(isinstance(node, dict) and nonempty(node.get('field_id')), 'Invalid embedded canonical field')
            identity = node['field_id']
            check(identity not in local_fields, 'Duplicate embedded canonical field ID')
            _, canonical = fk(f_map, row, identity, 'Embedded canonical field')
            check(equal(node, canonical['original_field_json']), 'Embedded canonical field disagrees with Field Catalog')
            local_fields[identity] = node
            represented_fields.add(scope + (identity,))
        if row['target_field_id']:
            check(row['target_field_id'] in local_fields, 'Target field is absent from its embedded catalog')
            target = local_fields[row['target_field_id']]
            for column, property_name in (
                ('snowflake_table', 'object'), ('snowflake_column', 'field_name'), ('snowflake_stage', 'stage'),
            ):
                check(row[column] == cell(target[property_name]), 'Target metadata disagrees with canonical identity')
        details = values['description_details_json']
        check(isinstance(details, list), 'Description details must be an array')
        detail_ids = []
        for detail in details:
            check(isinstance(detail, dict) and detail.get('field_id') in local_fields,
                  'Description detail references a missing canonical field')
            identity = detail['field_id']
            detail_ids.append(identity)
            canonical_row, canonical = fk(f_map, row, identity, 'Description detail')
            check(cell(detail.get('description')) == canonical_row['description'],
                  'Description detail text disagrees with its canonical field')
            if canonical_row.get('description_generation_status') == 'draft':
                check(detail.get('origin') == 'ai_generated', 'AI description detail has the wrong origin')
                provenance = detail.get('description_provenance')
                check(isinstance(provenance, dict)
                      and equal(provenance.get('description_assessment'), canonical['description_confidence_json']),
                      'Description detail assessment disagrees with its canonical field')
                field_provenance = canonical['description_provenance_json']
                check(provenance.get('source_type') == 'ai_generated'
                      and provenance.get('generator') == field_provenance.get('generator')
                      and provenance.get('generated_at') == field_provenance.get('generated_at')
                      and provenance.get('source_reference') == description_reference(canonical_row)
                      and provenance.get('is_approved_business_definition') is False,
                      'Description detail provenance misattributes the generated prose')
                check(equal(detail.get('source_refs_json'), [{
                    'file': 'field_catalog.csv', 'graph_id': canonical_row['graph_id'],
                    'snapshot_id': canonical_row['snapshot_id'], 'field_id': canonical_row['field_id'],
                    'column': 'description', 'evidence_role': 'ai_draft_output',
                }]), 'Generated detail must reference its actual output, not relabel old source claims')
        check(len(detail_ids) == len(set(detail_ids)) and set(detail_ids) == set(local_fields),
              'Description detail coverage must match all embedded canonical fields')

        ids = _ids(values['process_relationship_ids'], 'process_relationship_ids', check)
        process = values['process_details_json']
        output_scope = values['operation_output_scope_json']
        check(isinstance(process, list) and isinstance(output_scope, dict), 'Invalid process details/output scope')
        local_ops = {}
        for operation in process:
            check(isinstance(operation, dict) and nonempty(operation.get('relationship_id')), 'Invalid operation object')
            identity = operation['relationship_id']
            op_key = scope + (identity,)
            check(identity not in local_ops, 'Duplicate operation ID in one mapping')
            check(op_key not in operations or equal(operation, operations[op_key]),
                  'Conflicting shared operation definitions')
            check(operation.get('snapshot_id', row['snapshot_id']) == row['snapshot_id'],
                  'Operation belongs to a different snapshot')
            inputs = _ids(operation.get('source_field_ids'), 'Operation inputs', check)
            outputs = _ids(operation.get('target_field_ids'), 'Operation outputs', check)
            check(bool(outputs), 'Operation has no output fields')
            check(set(inputs + outputs) <= set(local_fields), 'Dangling operation endpoints in embedded catalog')
            score, state = operation.get('confidence_score_10'), operation.get('confidence_state')
            check(score is None or (type(score) in (int, float) and math.isfinite(score) and 0 <= score <= 10),
                  'Operation confidence score must be null or a finite number in 0-10')
            check(state in {'scored', 'unscored'} and ((score is None) == (state == 'unscored')),
                  'Operation confidence score/state disagree')
            for column, allowed_ids in (('input_roles_json', inputs), ('output_expressions_json', outputs),
                                        ('output_input_bindings_json', outputs)):
                value = operation.get(column)
                check(value is None or isinstance(value, dict), column + ' must be an object or null')
                if isinstance(value, dict):
                    check(set(value) <= set(allowed_ids), column + ' references unknown endpoints')
            roles = operation.get('input_roles_json')
            if isinstance(roles, dict):
                for role_list in roles.values():
                    _ids(role_list, 'Operation input roles', check)
            bindings = operation.get('output_input_bindings_json')
            if isinstance(bindings, dict):
                check(set(bindings) == set(outputs), 'Missing output bindings; explicitly use null if unresolved')
                for binding_list in bindings.values():
                    check(binding_list is None or isinstance(binding_list, list), 'Output bindings must be arrays or null')
                    for binding in binding_list or []:
                        check(isinstance(binding, dict) and binding.get('field_id') in inputs,
                              'Binding references an unknown operation input')
                        if 'roles' in binding:
                            _ids(binding['roles'], 'Binding roles', check)
            operations[op_key] = operation
            operation_rows[op_key].add(entry)
            local_ops[identity] = operation
        check(set(ids) == set(local_ops) == set(output_scope), 'Operation IDs, definitions and output scopes disagree')
        for identity, outputs in output_scope.items():
            if outputs is not None:
                check(set(_ids(outputs, 'Operation output scope', check)) <= set(local_ops[identity]['target_field_ids']),
                      'Output scope includes fields not produced by the operation')
        confidence = values['relationship_confidence_json']
        check(isinstance(confidence, list) and len(confidence) == len(ids), 'Relationship assessment coverage disagrees')
        for identity, summary in zip(ids, confidence):
            check(isinstance(summary, dict) and summary.get('relationship_id') == identity,
                  'Relationship assessment order/identity disagrees')
            for column in ('confidence_score_10', 'confidence_state', 'confidence_method',
                           'confidence_rationale', 'confidence_assessment_json'):
                check(equal(summary.get(column), local_ops[identity].get(column)), 'Relationship confidence mirror changed')
        paths = values['path_details_json']
        check(paths is None or isinstance(paths, list), 'Path details must be an array or null')
        for path in paths or []:
            check(isinstance(path, dict), 'Invalid path object')
            path_ops = _ids(path.get('relationship_ids', []), 'Path operations', check)
            path_fields = _ids(path.get('field_ids', []), 'Path fields', check)
            check(set(path_ops) <= set(local_ops) and set(path_fields) <= set(local_fields), 'Dangling path references')
            check(not path.get('target_field_id') or path['target_field_id'] == row['target_field_id'],
                  'Path points at another mapping target')
            if path_fields and path_ops:
                check(len(path_fields) == len(path_ops) + 1, 'Path field/operation lengths disagree')
                for index, identity in enumerate(path_ops):
                    operation = local_ops[identity]
                    check(path_fields[index] in operation['source_field_ids']
                          and path_fields[index + 1] in operation['target_field_ids'],
                          'Path sequence is not supported by its operations')
        raw_nodes += _coverage(row, values, check)
        original_id = values['original_record_json'].get('field_id')
        check(nonempty(original_id), 'Original mapping record has no field_id')
        archive_key = scope + (original_id,)
        check(archive_key not in archived or equal(archived[archive_key], values['original_record_json']),
              'Repeated original records disagree')
        archived[archive_key] = values['original_record_json']
    check(represented_fields == set(f_map), 'Field Catalog includes unrepresented fields')

    for key, operation in operations.items():
        scope = key[:2]
        check(set(_ids(operation.get('dictionary_entry_ids'), 'Operation dictionary associations', check))
              == operation_rows[key], 'Operation-to-mapping associations are incomplete or invented')
        for identity in operation['source_field_ids']:
            field_key = scope + (identity,)
            incidents[field_key].add((operation['relationship_id'], 'input'))
            for target in operation['target_field_ids']:
                target_key = scope + (target,)
                expected_down[field_key].add(target)
                expected_up[target_key].add(identity)
                first, second = f_map[field_key][0]['asset_id'], f_map[target_key][0]['asset_id']
                if first != second:
                    asset_down[scope + (first,)].add(second)
                    asset_up[scope + (second,)].add(first)
        for identity in operation['target_field_ids']:
            incidents[scope + (identity,)].add((operation['relationship_id'], 'output'))
    for row, values in zip(fields.rows, fields.json_rows):
        key = scoped(row, 'field_id')
        check(set(values['upstream_field_ids_json']) == expected_up[key]
              and set(values['downstream_field_ids_json']) == expected_down[key],
              'Field topology disagrees with recorded operations')
        actual = set()
        for incident in values['transformation_logic_json']:
            check(isinstance(incident, dict) and incident.get('field_role') in {'input', 'output'},
                  'Invalid incident operation')
            definition = {name: value for name, value in incident.items() if name != 'field_role'}
            op_key = key[:2] + (incident.get('relationship_id'),)
            check(op_key in operations and equal(definition, operations[op_key]),
                  'Field incident operation disagrees with dictionary operation')
            actual.add((incident['relationship_id'], incident['field_role']))
        check(len(actual) == len(values['transformation_logic_json']) and actual == incidents[key],
              'Field incident operation coverage is incomplete')
    for row, values in zip(assets.rows, assets.json_rows):
        key = scoped(row, 'asset_id')
        check(row['field_count'].isdigit() and int(row['field_count']) == counts[key], 'Asset field_count disagrees')
        for column in ('upstream_asset_ids_json', 'downstream_asset_ids_json'):
            for identity in _ids(values[column], column, check):
                fk(a_map, row, identity, 'Asset adjacency')
        check(set(values['upstream_asset_ids_json']) == asset_up[key]
              and set(values['downstream_asset_ids_json']) == asset_down[key],
              'Asset topology disagrees with recorded operations')
        metadata = values['metadata_json']
        check(isinstance(metadata, dict), 'Asset metadata must be an object')
        if 'field_ids' in metadata:
            check(set(_ids(metadata['field_ids'], 'Asset field membership', check)) == membership[key],
                  'Asset metadata field membership disagrees')
    return {'operations': len(operations), 'input_records': len(archived),
            'original_json_nodes_checked': raw_nodes, 'scopes': [list(scope) for scope in sorted(scopes[0])]}


def _field_previous(row, values):
    return {column: copy.deepcopy(values[column] if column in values else row[column])
            for column in DESCRIPTION_SURFACES + ['original_field_json']}


def _preservation(tables, baseline, check):
    check(tables['asset_registry.csv'].sha256 == baseline['asset_registry.csv'].sha256,
          'Asset Registry bytes must remain unchanged during description enrichment')
    old_fields = baseline['field_catalog.csv'].index()
    new_fields = tables['field_catalog.csv'].index()
    changed = set()
    for name in CSV_FILES[1:]:
        current, old = tables[name], baseline[name]
        check(current.headers[:len(old.headers)] == old.headers, name + ': original header order changed')
        allowed_added = ENRICHMENT_COLUMNS if name == 'field_catalog.csv' else ['source_' + col for col in ENRICHMENT_COLUMNS]
        check(not set(current.headers[len(old.headers):]) - set(allowed_added), name + ': unsupported added columns')
        check([scoped(row, ID_COLUMNS[name]) for row in current.rows] ==
              [scoped(row, ID_COLUMNS[name]) for row in old.rows], name + ': row order/identity changed')
    field_table, old_table = tables['field_catalog.csv'], baseline['field_catalog.csv']
    for row, values, old_row, old_values in zip(field_table.rows, field_table.json_rows,
                                                old_table.rows, old_table.json_rows):
        key = scoped(row, 'field_id')
        allowed = set(ENRICHMENT_COLUMNS)
        is_draft = eligible(old_row) and row.get('description_generation_status') == 'draft'
        if is_draft:
            changed.add(key)
            allowed.update(DESCRIPTION_SURFACES + ['original_field_json'])
            provenance = values['description_provenance_json']
            check(equal(provenance.get('previous'), _field_previous(old_row, old_values)),
                  'Generated provenance must archive exact previous description surfaces and canonical object')
            old_node, new_node = copy.deepcopy(old_values['original_field_json']), copy.deepcopy(values['original_field_json'])
            check(new_node.get('description') == row['description'] and new_node.get('description_origin') == 'ai_generated',
                  'Enriched canonical description/origin disagrees')
            check(isinstance(new_node.get('metadata'), dict)
                  and isinstance(new_node['metadata'].get('ai_description_enrichment'), dict),
                  'Enriched canonical object must identify explicit AI provenance')
            new_node['description'] = old_node.get('description')
            if 'description_origin' in old_node:
                new_node['description_origin'] = old_node['description_origin']
            else:
                new_node.pop('description_origin', None)
            new_node['metadata'].pop('ai_description_enrichment')
            check(equal(new_node, old_node), 'Enrichment changed unrelated canonical field properties')
        for column in old_table.headers:
            if column not in allowed or not eligible(old_row):
                check(row[column] == old_row[column], 'Protected/unrelated Field Catalog cell changed: ' + column)
        for column in set(field_table.headers) - set(old_table.headers):
            if not eligible(old_row):
                check(row[column] == ('null' if column.endswith('_json') else ''),
                      'New enrichment columns must be blank/null for protected and out-of-scope fields')
        if eligible(old_row) and not is_draft:
            check(row['description'] == old_row['description']
                  and values['original_field_json'] == old_values['original_field_json'],
                  'needs_evidence must not fabricate prose or alter canonical metadata')

    table, old_table = tables['data_dictionary.csv'], baseline['data_dictionary.csv']
    allowed = {'source_description', 'source_description_origin', 'field_catalog_json',
               'description_details_json', 'input_property_map_json'}
    allowed.update('source_' + column for column in DESCRIPTION_COLUMNS + ENRICHMENT_COLUMNS)
    for row, values, old_row, old_values in zip(table.rows, table.json_rows, old_table.rows, old_table.json_rows):
        for column in old_table.headers:
            if column not in allowed:
                check(row[column] == old_row[column], 'Unrelated dictionary cell changed: ' + column)
        source_key = row['graph_id'], row['snapshot_id'], row['source_field_id']
        if source_key not in changed:
            for column in ['source_description', 'source_description_origin'] + ['source_' + col for col in DESCRIPTION_COLUMNS]:
                check(row[column] == old_row[column], 'Protected source description mirror changed')
        if not eligible(old_fields[source_key][0]):
            for column in ['source_' + col for col in ENRICHMENT_COLUMNS]:
                check(row.get(column, 'null' if column.endswith('_json') else '') ==
                      old_row.get(column, 'null' if column.endswith('_json') else ''),
                      'Protected source assessment changed')
        check([node['field_id'] for node in values['field_catalog_json']] ==
              [node['field_id'] for node in old_values['field_catalog_json']], 'Embedded canonical field order changed')
        details, old_details = values['description_details_json'], old_values['description_details_json']
        check([detail['field_id'] for detail in details] == [detail['field_id'] for detail in old_details],
              'Description detail order/identities changed')
        for detail, previous in zip(details, old_details):
            key = row['graph_id'], row['snapshot_id'], detail['field_id']
            if key not in changed:
                check(equal(detail, previous), 'Protected/unselected description detail changed')
            else:
                check(equal(detail.get('previous_description_metadata'), previous),
                      'Generated detail must archive its exact prior metadata')
                for column in set(previous) - {'description', 'origin', 'source_refs_json'}:
                    check(equal(detail.get(column), previous[column]), 'Unrelated description detail metadata changed')
        old_coverage, coverage = old_values['input_property_map_json'], values['input_property_map_json']
        check([entry['input_pointer'] for entry in coverage] == [entry['input_pointer'] for entry in old_coverage],
              'Original property coverage order/pointers changed')
    return changed


def _assessments(tables, baseline, check):
    fields = tables['field_catalog.csv']
    baseline_fields = baseline['field_catalog.csv'].index() if baseline is not None else {}
    count = resolved = 0
    for row, values in zip(fields.rows, fields.json_rows):
        status = row.get('description_generation_status', '')
        assessment = values.get('description_confidence_json')
        provenance = values['description_provenance_json']
        if not status:
            check(assessment is None and provenance.get('description_assessment') is None,
                  'Untouched fields must not acquire a description assessment')
            continue
        check(status in {'draft', 'needs_evidence'}, 'Unsupported description generation status')
        check(row['source_system'] == 'Ultracs' and row['layer'] == 'source',
              'Description enrichment is limited to Ultracs source fields')
        check(row.get('description_confidence_method') == RUBRIC_ID, 'Unsupported description rubric')
        check(nonempty(row.get('description_confidence_rationale')), 'Enrichment requires a rationale or open questions')
        if status == 'needs_evidence':
            check(not row['description'].strip() and not row.get('description_confidence_score_10') and assessment is None,
                  'needs_evidence must keep missing text and a null/unscored assessment')
            continue
        validate_sentences(row['description'])
        check(row['description_source_type'] == row['description_origin'] == 'ai_generated',
              'A generated draft must explicitly identify AI origin')
        source = baseline
        key = scoped(row, 'field_id')
        if source is not None and key in baseline_fields:
            old_row, old_values = baseline_fields[key]
            if equal(assessment, old_values.get('description_confidence_json')):
                source = None
        score = validate_assessment(assessment, tables=source, field=row)
        check(row.get('description_confidence_score_10') == str(score), 'Description score column disagrees with assessment')
        check(row['description_confidence_rationale'] == assessment['rationale'],
              'Description rationale column disagrees with assessment')
        check(equal(provenance.get('description_assessment'), assessment), 'Provenance assessment mirror disagrees')
        check(provenance.get('source_type') == 'ai_generated' and provenance.get('status') == 'draft'
              and provenance.get('verification_mode') == 'supplied_csv_only'
              and provenance.get('is_approved_business_definition') is False,
              'AI draft provenance misstates verification or business approval')
        check(row['description_generator'] == provenance.get('generator') == assessment['assessed_by']
              and provenance.get('model') == assessment.get('model')
              and provenance.get('generated_at') == assessment['assessed_at'],
              'AI draft generator/model/time disagree with its assessment')
        check(row['description_source_reference'] == description_reference(row)
              and not row['description_source_pointer'],
              'AI prose must reference its output CSV cell, not an input/source-file pointer')
        input_hashes = provenance.get('input_sha256')
        check(isinstance(input_hashes, dict) and set(input_hashes) == set(CSV_FILES)
              and all(isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value)
                      for value in input_hashes.values()),
              'AI provenance must retain all three exact input hashes')
        check(all(reference['input_sha256'] == input_hashes[reference['file']]
                  for reference in assessment['evidence_refs'].values()),
              'Assessment evidence hashes disagree with generated provenance')
        node_metadata = values['original_field_json'].get('metadata', {}).get('ai_description_enrichment')
        check(isinstance(node_metadata, dict)
              and node_metadata.get('source_type') == 'ai_generated'
              and node_metadata.get('status') == 'draft'
              and node_metadata.get('generator') == provenance['generator']
              and node_metadata.get('generated_at') == provenance['generated_at']
              and node_metadata.get('run_id') == provenance.get('enrichment_run_id')
              and node_metadata.get('source_reference') == description_reference(row)
              and node_metadata.get('assessment_reference') == description_reference(row, 'description_confidence_json')
              and node_metadata.get('rubric_id') == RUBRIC_ID
              and node_metadata.get('description_confidence_score_10') == score
              and node_metadata.get('is_approved_business_definition') is False,
              'Canonical AI metadata disagrees with the canonical description assessment/provenance')
        if source is not None:
            check(provenance.get('input_sha256') == {name: table.sha256 for name, table in source.items()},
                  'Generated provenance input hashes disagree with the supplied baseline')
        previous = provenance.get('previous')
        check(isinstance(previous, dict)
              and set(previous) == set(DESCRIPTION_SURFACES + ['original_field_json'])
              and not cell(previous.get('description')).strip()
              and previous.get('description_source_type') == 'not_supplied'
              and isinstance(previous.get('original_field_json'), dict)
              and previous['original_field_json'].get('field_id') == row['field_id'],
              'AI draft must retain a previously missing description, not replace protected text')
        count += 1
        resolved += source is not None
    return count, resolved


def validate_bundle(bundle_dir: Path, baseline_dir: Path | None = None) -> dict:
    """Validate contracts without modifying files; reject unsupported data."""
    bundle_dir = Path(bundle_dir).resolve()
    tables = read_tables(bundle_dir)
    check = Checks()
    metadata = _validate_tables(tables, check)
    baseline = None
    changed = set()
    if baseline_dir is not None:
        baseline = read_tables(Path(baseline_dir).resolve())
        _validate_tables(baseline, check)
        changed = _preservation(tables, baseline, check)
    descriptions, resolved = _assessments(tables, baseline, check)
    outputs = {name: {'sha256': table.sha256, 'rows': len(table.rows), 'columns': len(table.headers)}
               for name, table in tables.items()}
    return {
        'status': 'passed', 'bundle_directory': str(bundle_dir), 'checks_passed': check.count,
        'outputs': outputs, 'counts': {name.removesuffix('.csv'): len(table.rows) for name, table in tables.items()},
        **metadata, 'description_drafts': descriptions, 'description_assessments_resolved': resolved,
        'changed_eligible_descriptions': len(changed),
        'maximum_cell_characters': {name: table.maximum_cell_characters for name, table in tables.items()},
        'description_evidence_verification': (
            'Exact input CSV references resolved for changed drafts; preserved historical assessments are retained.'
            if baseline is not None else
            'Assessment structure/arithmetic checked; supply the original baseline to resolve historical evidence hashes.'),
        'browser_import_verified': False,
        'scope': 'Reported CSV claims, preservation and structural consistency only; no source, runtime or business-meaning verification.',
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--baseline', type=Path)
    args = parser.parse_args(argv)
    print(json.dumps(validate_bundle(args.input, args.baseline), indent=2))


if __name__ == '__main__':
    main()
