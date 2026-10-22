#!/usr/bin/env python3
"""Generate three linked CSVs and a standalone HTML dictionary from the input JSON.

Standard library only. This is a deterministic, evidence-preserving projection;
it does not execute lineage, infer physical files, score confidence, or call AI.
"""
from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
import re
import shutil
import sys
import tempfile
from collections import Counter, defaultdict
from contextlib import ExitStack
from pathlib import Path

from legacy_projection import project, js, uid, cell, walk, unique_object, reject_nonfinite
from description_provenance import DESCRIPTION_COLUMNS, resolve_description
from build_viewer import build, latest_html_path, output_lock, publish_latest_snapshot

VERSION = '3.0.1'
DATA_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = DATA_ROOT / '01-input' / 'column_lineage.json'
DEFAULT_OUTPUT = DATA_ROOT / '03-output' / '01-baseline'
ASSET_COLUMNS = [
    'graph_id', 'snapshot_id', 'asset_id', 'asset_name', 'asset_kind', 'source_system',
    'layer', 'domain', 'owner', 'steward', 'description', 'update_frequency',
    'approximate_row_count', 'lineage_reference', 'pii_status', 'sensitivity', 'status',
    'physical_asset_name', 'physical_binding_status', 'field_count',
    'upstream_asset_ids_json', 'downstream_asset_ids_json', 'evidence_json', 'notes_json', 'metadata_json',
]
FIELD_COLUMNS = [
    'graph_id', 'snapshot_id', 'field_id', 'asset_id', 'field_name', 'business_name',
    'field_kind', 'source_system', 'layer', 'data_type', 'description', 'description_origin',
    'business_definition', 'definition_status', 'business_review_json', 'source_file',
    'record_reference', 'record_key_reference', 'attribute_position', 'value_position',
    'subvalue_position', 'source_locator', 'physical_binding_status', 'extract_file',
    'extract_position', 'hvr_header', 'upstream_field_ids_json', 'downstream_field_ids_json',
    'transformation_logic_json', 'sample_values_json', 'allowed_values_json', 'nullable',
    'is_pii', 'is_primary_key', 'foreign_key_reference', 'business_rules_json',
    'last_verified_date', 'notes_json', 'evidence_json', 'metadata_json', 'original_field_json',
] + DESCRIPTION_COLUMNS
ADDED_MAPPING_COLUMNS = [
    'graph_id', 'source_field_id', 'source_asset_id', 'hvr_field_id', 'hvr_asset_id',
    'target_asset_id', 'source_file', 'source_record_reference', 'source_record_key_reference',
    'source_attribute_position', 'source_value_position', 'source_subvalue_position',
    'source_file_binding_status',
] + ['source_' + name for name in DESCRIPTION_COLUMNS] + ['snowflake_' + name for name in DESCRIPTION_COLUMNS]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest_file(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_input(path):
    """Validate only the supported exported mapping-list contract, never guess formats."""
    records = json.loads(path.read_bytes(), object_pairs_hook=unique_object,
                         parse_constant=reject_nonfinite)
    require(isinstance(records, list) and records,
            'Unsupported input: expected a non-empty POC mapping-record JSON array, not a generic nodes/edges graph.')
    required = {'business_field', 'field_id', 'ultracs_position', 'ultracs_program',
                'extract_file', 'param_column', 'hvr_parameter', 'snowflake_table',
                'snowflake_column', 'confidence', 'source_path', 'notes', 'ultracs',
                'cdp', 'dbt_targets', 'ingestion_route'}
    ultracs_required = {'program', 'source_path', 'source_locator', 'source_references',
                        'description', 'transformation', 'basic_expression', 'basic_comment',
                        'basic_source_line', 'extract_file', 'position', 'param_column'}
    route_required = {'hvr_channels', 's3_paths', 'airflow_dag', 'airflow_tasks',
                      'raw_relation', 'dbt_input'}
    ids = set()
    for index, record in enumerate(records):
        context = f'Input record {index}'
        require(isinstance(record, dict), context + ' must be an object.')
        require(required <= record.keys(), context + ' is missing contract keys: ' +
                ', '.join(sorted(required - record.keys())))
        require(isinstance(record['field_id'], str) and record['field_id'], context + ' requires a non-empty field_id.')
        require(record['field_id'] not in ids, context + ': duplicate mapping field_id.')
        ids.add(record['field_id'])
        confidence = record['confidence']
        require(isinstance(confidence, str) and confidence.strip()
                and not re.fullmatch(r'\s*[+-]?(?:\d+(?:\.\d*)?|\.\d+)\s*%?\s*', confidence),
                context + ': only categorical mapping confidence labels are supported; numeric or structured assessments require an explicit adapter.')
        for pointer, value in walk(record):
            if not isinstance(value, dict):
                continue
            for key in value:
                normalized = key.lower().replace('-', '_').replace(' ', '_')
                if normalized == 'confidence' and pointer == '':
                    continue
                require(not ('confidence' in normalized or normalized in {'score', 'score_10', 'score_100', 'scoring_method', 'scoring_rationale', 'rubric', 'assessment', 'relationship_assessments'}),
                        context + ': unsupported assessment metadata at ' + pointer + '/' + key + '. No supplied score will be silently replaced with Unscored; add an explicit adapter.')
        u, h, route = record['ultracs'], record['hvr_parameter'], record['ingestion_route']
        require(isinstance(u, dict) and ultracs_required <= u.keys(), context + ': unsupported ultracs contract.')
        require(isinstance(h, dict) and {'name', 'type', 'obfuscate', 'cleanup'} <= h.keys(), context + ': unsupported hvr_parameter contract.')
        require(isinstance(h['cleanup'], dict) and {'enabled', 'remove_chars'} <= h['cleanup'].keys(), context + ': unsupported HVR cleanup contract.')
        require(isinstance(route, dict) and route_required <= route.keys(), context + ': unsupported ingestion_route contract.')
        for name in ['program', 'source_path', 'transformation', 'basic_expression', 'extract_file', 'param_column']:
            require(isinstance(u[name], str), context + ': ultracs.' + name + ' must be a string.')
        require(u['source_locator'] is None or isinstance(u['source_locator'], str), context + ': locator must be a string or null.')
        require(isinstance(u['source_references'], list) and all(isinstance(s, str) for s in u['source_references']), context + ': source_references must be a string array.')
        require(isinstance(record['ultracs_position'], int) and not isinstance(record['ultracs_position'], bool)
                and record['ultracs_position'] > 0, context + ': extract position must be a positive integer.')
        for left, right in [('ultracs_program', 'program'), ('extract_file', 'extract_file'),
                            ('ultracs_position', 'position'), ('param_column', 'param_column')]:
            require(record[left] == u[right], context + f': conflicting {left} and ultracs.{right}; cannot pick silently.')
        require(record['param_column'] == h['name'], context + ': HVR header name conflicts with param_column.')
        require(isinstance(record['dbt_targets'], list) and record['dbt_targets'], context + ': dbt_targets must contain supported targets.')
        for j, target in enumerate(record['dbt_targets']):
            required_target = {'stage', 'model', 'model_id', 'relation', 'column', 'source_path'}
            require(isinstance(target, dict) and required_target <= target.keys(), context + f': invalid target {j}.')
            require(target['stage'] in ('internal', 'public'), context + ': only declared internal/public targets are supported.')
            keys = {'source_expression'} if target['stage'] == 'internal' else {'source_model', 'source_column', 'projection_expression'}
            require(keys <= target.keys(), context + ': missing stage-specific expression/binding.')
        require(any(t['relation'] == record['snowflake_table'] and t['column'] == record['snowflake_column']
                    for t in record['dbt_targets']), context + ': primary target is absent from dbt_targets.')
    return records


def normalize_locator(raw):
    """Parse only a complete simple locator. Never interpret a record variable as a file."""
    result = {'record_reference': '', 'record_key_reference': '', 'attribute_position': '',
              'value_position': '', 'subvalue_position': '', 'normalization_status': 'not_supplied'}
    if raw is None or raw == '':
        return result
    locator = re.fullmatch(r'([A-Za-z_][A-Za-z0-9_]*)<([1-9]\d*)(?:,([1-9]\d*))?(?:,([1-9]\d*))?>', raw)
    if locator:
        result.update(record_reference=locator[1], attribute_position=int(locator[2]),
                      value_position=int(locator[3]) if locator[3] else '',
                      subvalue_position=int(locator[4]) if locator[4] else '',
                      normalization_status='parsed_record_attribute_reference')
        return result
    key = re.fullmatch(r'([A-Za-z_][A-Za-z0-9_]*)\s+(@ID)', raw)
    if key:
        result.update(record_reference=key[1], record_key_reference=key[2],
                      normalization_status='parsed_record_key_reference')
        return result
    result['normalization_status'] = 'not_normalized_complex_reference'
    return result


def unique_json(items):
    return [json.loads(value) for value in sorted({js(item) for item in items})]


def group_evidence(items):
    """Group asset evidence pointers; complete per-field evidence stays in the catalog."""
    groups = {}
    for item in items:
        data = dict(item)
        pointer = data.pop('input_pointer', None)
        key = js(data)
        if key not in groups:
            groups[key] = dict(data, input_pointers=[])
        if pointer is not None:
            groups[key]['input_pointers'].append(pointer)
    for data in groups.values():
        data['input_pointers'] = sorted(set(data['input_pointers']))
    return [groups[key] for key in sorted(groups)]


def node_description(projection, node):
    """Resolve one node against its exact input object, never adjacent metadata."""
    reference = node.get('source_refs_json', [{}])[0]
    pointer = reference.get('input_pointer', '')
    value = projection['records']
    for token in pointer.split('/')[1:]:
        token = token.replace('~1', '/').replace('~0', '~')
        value = value[int(token)] if isinstance(value, list) else value[token]
    if node['field_kind'] == 'json_path':
        # ingestion_route is route/asset context, not metadata for this RAW key.
        # An unrelated route description must not be promoted to a field claim.
        value = {}
    return resolve_description(value, input_file=reference.get('input_file', ''),
        input_sha256=projection['input_sha256'], input_pointer=pointer,
        description=node.get('description'),
        reported_source_path=value.get('source_path') if isinstance(value, dict) else None)


def build_catalogs(projection, graph_id):
    snapshot = projection['snapshot_id']
    nodes, ops = {}, {}
    for row in projection['rows']:
        for node in row['field_catalog_json']:
            fid = node['field_id']
            require(fid not in nodes or nodes[fid] == node, 'Conflicting repeated catalog field: ' + fid)
            nodes[fid] = node
        for operation in row['process_details_json']:
            rid = operation['relationship_id']
            require(rid not in ops or ops[rid] == operation, 'Conflicting repeated relationship: ' + rid)
            ops[rid] = operation
    require(nodes == projection['nodes'], 'Some generated fields are not represented in the output mappings.')
    require(ops == projection['operations'], 'Some generated operations are not represented in the output mappings.')
    original_by_source = {projection['sources'][r['field_id']]['source_id']: r for r in projection['records']}
    upstream, downstream, incidents = defaultdict(set), defaultdict(set), defaultdict(list)
    for rid, operation in ops.items():
        inputs, outputs = operation['source_field_ids'], operation['target_field_ids']
        require(all(fid in nodes for fid in inputs + outputs), 'Relationship endpoint is absent from field catalog: ' + rid)
        for fid in inputs:
            downstream[fid].update(outputs)
            incidents[fid].append(dict(operation, field_role='input'))
        for fid in outputs:
            upstream[fid].update(inputs)
            incidents[fid].append(dict(operation, field_role='output'))
    assets, field_assets = {}, {}
    for fid, node in nodes.items():
        kind = node['field_kind']
        if node['system'] == 'Ultracs':
            asset_kind, identity, physical_status = 'multivalue_source_context', node['object'], 'file_binding_not_supplied'
            name = identity + ' (source file not supplied)'
        elif kind == 'extract_slot':
            asset_kind, identity, physical_status = 'extract_file', node['object'], 'reported_extract_file'
            name = identity
        else:
            asset_kind, identity, physical_status = 'snowflake_relation', node['object'], 'reported_relation'
            name = identity.removeprefix('snowflake:relation:')
        aid = uid('asset', graph_id, snapshot, asset_kind, identity)
        field_assets[fid] = aid
        if aid not in assets:
            assets[aid] = dict.fromkeys(ASSET_COLUMNS, '')
            assets[aid].update(graph_id=graph_id, snapshot_id=snapshot, asset_id=aid,
                asset_name=name, asset_kind=asset_kind, source_system=node['system'], layer=node['stage'],
                physical_asset_name='' if asset_kind == 'multivalue_source_context' else identity,
                physical_binding_status=physical_status, field_count=0,
                upstream_asset_ids_json=[], downstream_asset_ids_json=[], evidence_json=[], notes_json=[],
                metadata_json={'reported_object': identity, 'verification_mode': 'reported_json_only',
                               'field_ids': [], 'declared_model_names': [], 'declared_model_descriptions': []})
            if asset_kind == 'multivalue_source_context':
                assets[aid]['notes_json'].append('This is a program-scoped source context, not a confirmed physical multi-value file. Record variables, source locators and original mapping identifiers do not establish file binding.')
            if asset_kind == 'extract_file':
                assets[aid]['notes_json'].append('This asset is the reported extract file. No HVR physical table name was supplied; none was inferred.')
            if node['stage'] == 'raw':
                assets[aid]['notes_json'].append('Catalog fields in this asset are reported logical DATA JSON paths, not asserted physical Snowflake columns.')
        asset = assets[aid]
        asset['field_count'] += 1
        asset['metadata_json']['field_ids'].append(fid)
        asset['evidence_json'].extend(node.get('source_refs_json', []))
        metadata = node.get('metadata', {})
        if metadata.get('model'):
            asset['metadata_json']['declared_model_names'].append(metadata['model'])
        if metadata.get('model_description'):
            asset['metadata_json']['declared_model_descriptions'].append(metadata['model_description'])
    asset_up, asset_down = defaultdict(set), defaultdict(set)
    for fid, predecessors in upstream.items():
        current = field_assets[fid]
        for predecessor in predecessors:
            previous = field_assets[predecessor]
            if current != previous:
                asset_up[current].add(previous)
                asset_down[previous].add(current)
    for aid, asset in assets.items():
        asset['upstream_asset_ids_json'] = sorted(asset_up[aid])
        asset['downstream_asset_ids_json'] = sorted(asset_down[aid])
        asset['evidence_json'] = group_evidence(asset['evidence_json'])
        metadata = asset['metadata_json']
        for key in ['field_ids', 'declared_model_names', 'declared_model_descriptions']:
            metadata[key] = sorted(set(metadata[key]))
        descriptions = metadata['declared_model_descriptions']
        if len(descriptions) == 1:
            asset['description'] = descriptions[0]
            metadata['description_origin'] = 'recorded_input_model_description'
        elif len(descriptions) > 1:
            asset['notes_json'].append('Conflicting declared model descriptions are preserved in metadata; no single description was chosen.')
        metadata['governance_state'] = 'not_supplied'
        metadata['sensitivity_note'] = 'Column-level classification is retained on fields; no asset-level sensitivity or PII claim is inferred.'
        metadata['lineage_graph_id'] = graph_id
    fields = []
    for fid, node in nodes.items():
        field = dict.fromkeys(FIELD_COLUMNS, '')
        aid = field_assets[fid]
        physical = assets[aid]['physical_binding_status']
        field.update(graph_id=graph_id, snapshot_id=snapshot, field_id=fid, asset_id=aid,
            field_name=node['field_name'], field_kind=node['field_kind'], source_system=node['system'],
            layer=node['stage'], data_type=node.get('data_type'), description=node.get('description'),
            description_origin=node.get('description_origin', 'recorded_input' if node.get('description') else 'unknown'),
            business_definition=node.get('business_definition'), definition_status='unknown',
            business_review_json={'status': 'unknown', 'reviewer': None, 'reviewed_at': None,
                                  'description_is_approved_definition': False},
            physical_binding_status=physical, upstream_field_ids_json=sorted(upstream[fid]),
            downstream_field_ids_json=sorted(downstream[fid]),
            transformation_logic_json=sorted(incidents[fid], key=lambda o: (o['relationship_id'], o['field_role'])),
            sample_values_json=None, allowed_values_json=None, business_rules_json=None,
            notes_json=[], evidence_json=node.get('source_refs_json', []),
            metadata_json={'identity_resolution_status': node.get('identity_resolution_status'),
                           'classification': node.get('classification'), 'verification_mode': 'reported_json_only',
                           'original_metadata': node.get('metadata', {}),
                           'confidence_scope': 'Confidence is assessed per relationship in transformation_logic_json; no field-level aggregate score is assigned.'},
            original_field_json=node)
        if node['system'] == 'Ultracs':
            record = original_by_source[fid]
            norm = normalize_locator(record['ultracs'].get('source_locator'))
            field.update(business_name=record['business_field'],
                record_reference=norm['record_reference'], record_key_reference=norm['record_key_reference'],
                attribute_position=norm['attribute_position'], value_position=norm['value_position'],
                subvalue_position=norm['subvalue_position'], source_locator=record['ultracs'].get('source_locator'))
            field['metadata_json'].update(locator_normalization_status=norm['normalization_status'],
                business_name_origin='reported_business_field_label_not_reviewed_definition',
                original_mapping_id=record['field_id'], source_program=record['ultracs']['program'],
                basic_expression=record['ultracs']['basic_expression'],
                source_references=record['ultracs']['source_references'])
            field['notes_json'].append('The record reference is a BASIC record variable/context; the physical Ultracs file and key binding were not supplied.')
            if record['notes']:
                field['notes_json'].append(record['notes'])
        elif node['field_kind'] == 'extract_slot':
            field.update(extract_file=node['object'], extract_position=node['locator']['position'],
                         hvr_header=node['field_name'])
            field['notes_json'].append('Extract position is an output slot and is separate from an Ultracs attribute/value/subvalue position.')
        elif node['field_kind'] == 'json_path':
            field['notes_json'].append('This is a logical JSON path in the reported RAW relation, not an asserted physical column.')
        field.update(node_description(projection, node))
        fields.append(field)
    return sorted(assets.values(), key=lambda a: (a['source_system'], a['layer'], a['asset_name'])), sorted(fields, key=lambda f: f['field_id']), field_assets, nodes, ops


def enrich_mappings(projection, graph_id, field_assets):
    rows = []
    for original in projection['rows']:
        row = copy.deepcopy(original)
        record = row['original_record_json']
        source = projection['sources'][record['field_id']]
        fid, hvr = source['source_id'], source['extract_id']
        norm = normalize_locator(record['ultracs'].get('source_locator'))
        row.update(graph_id=graph_id, source_field_id=fid, source_asset_id=field_assets[fid],
            hvr_field_id=hvr, hvr_asset_id=field_assets[hvr], target_asset_id=field_assets[row['target_field_id']],
            source_file='', source_record_reference=norm['record_reference'],
            source_record_key_reference=norm['record_key_reference'],
            source_attribute_position=norm['attribute_position'], source_value_position=norm['value_position'],
            source_subvalue_position=norm['subvalue_position'], source_file_binding_status='file_binding_not_supplied')
        for prefix, node_id in [('source_', fid), ('snowflake_', row['target_field_id'])]:
            row.update({prefix + key: value for key, value in node_description(projection, projection['nodes'][node_id]).items()})
        rows.append(row)
    return rows


def write_csv(path, columns, rows):
    """Serialize exact scalar values and canonical JSON; preserve legacy protection."""
    with path.open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, lineterminator='\r\n')
        writer.writeheader()
        for row in rows:
            require(set(row) == set(columns), 'Output columns disagree with schema for ' + path.name)
            writer.writerow({key: cell(row[key]) for key in columns})


def read_csv(path):
    with path.open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        return reader.fieldnames, list(reader)


def validate(projection, graph_id, assets, fields, mappings, nodes, ops, output):
    """Round-trip every serialized cell plus references and every original JSON node."""
    checks = 0
    def check(condition, message):
        nonlocal checks
        checks += 1
        require(condition, 'Validation failed: ' + message)
    asset_ids = {a['asset_id'] for a in assets}
    field_ids = {f['field_id'] for f in fields}
    row_ids = {r['dictionary_entry_id'] for r in mappings}
    fields_by_id = {field['field_id']: field for field in fields}
    check(len(asset_ids) == len(assets), 'unique asset IDs')
    check(len(field_ids) == len(fields), 'unique field IDs')
    check(len(row_ids) == len(mappings), 'unique dictionary row IDs')
    for asset in assets:
        check(asset['graph_id'] == graph_id and asset['snapshot_id'] == projection['snapshot_id'], 'asset scope')
        check(set(asset['upstream_asset_ids_json'] + asset['downstream_asset_ids_json']) <= asset_ids, 'asset adjacency foreign keys')
        check(asset['field_count'] == sum(f['asset_id'] == asset['asset_id'] for f in fields), 'asset field count')
        check(asset['approximate_row_count'] == '', 'no invented row count')
        check(all(asset[k] == '' for k in ['owner', 'steward', 'domain', 'status', 'pii_status', 'sensitivity', 'update_frequency']), 'no invented governance metadata')
    for field in fields:
        check(field['asset_id'] in asset_ids, 'field-to-asset foreign key')
        check(set(field['upstream_field_ids_json'] + field['downstream_field_ids_json']) <= field_ids, 'field adjacency foreign keys')
        check(field['original_field_json'] == nodes[field['field_id']], 'original canonical field retained')
        check(field['description'] == nodes[field['field_id']].get('description'), 'exact own description text retained without inheritance')
        check(field['description_source_type'] in {'ai_generated', 'existing_metadata', 'unknown', 'not_supplied'}, 'description source type enum')
        check(field['description_provenance_json']['description_pointer'] == field['description_source_pointer'], 'description pointer consistency')
        check(field['description_provenance_json']['input_sha256'] == projection['input_sha256'], 'description provenance input identity')
        description_pointer = field['description_source_pointer']
        if description_pointer:
            pointed = projection['records']
            for token in description_pointer.split('/')[1:]:
                token = token.replace('~1', '/').replace('~0', '~')
                pointed = pointed[int(token)] if isinstance(pointed, list) else pointed[token]
            check(pointed == field['description'], 'description pointer resolves to its exact original input value')
        else:
            check(not field['description_provenance_json']['description_property_present'], 'absent description has no invented JSON pointer')
        if field['source_system'] == 'Ultracs':
            check(field['source_file'] == '' and field['physical_binding_status'] == 'file_binding_not_supplied', 'physical source file not guessed')
            if field['record_key_reference']:
                check(field['attribute_position'] == '', '@ID is not an attribute zero')
    expected_by_id = {r['field_id']: r for r in projection['records']}
    reconstructed = {}
    for row, old in zip(mappings, projection['rows']):
        check(all(row[h] == old[h] for h in projection['headers']), 'all original 81 mapping columns unchanged')
        check(row['source_field_id'] in field_ids and row['hvr_field_id'] in field_ids and row['target_field_id'] in field_ids, 'mapping field foreign keys')
        check(all(row[key] in asset_ids for key in ['source_asset_id', 'hvr_asset_id', 'target_asset_id']), 'mapping asset foreign keys')
        for prefix, field_id in [('source_', row['source_field_id']), ('snowflake_', row['target_field_id'])]:
            check(all(row[prefix + key] == fields_by_id[field_id][key] for key in DESCRIPTION_COLUMNS), 'description provenance catalog-to-dictionary join')
        original = row['original_record_json']
        check(original == expected_by_id[original['field_id']], 'original mapping payload retained')
        reconstructed[original['field_id']] = original
        check(all(rid in ops for rid in row['process_relationship_ids']), 'mapping relationship IDs')
        check(len(row['relationship_confidence_json']) == len(row['process_relationship_ids']), 'one confidence record per represented relationship')
    check(reconstructed == expected_by_id, 'all original mapping records reconstruct exactly')
    node_count = sum(1 for record in projection['records'] for _ in walk(record))
    for rid, operation in ops.items():
        check(set(operation['source_field_ids'] + operation['target_field_ids']) <= field_ids, 'operation endpoints')
        check(set(operation['dictionary_entry_ids']) <= row_ids, 'operation-to-mapping foreign keys')
        check(operation['confidence_score_10'] is None and operation['confidence_state'] == 'unscored', 'no numeric confidence invented')
    schema_rows = [('asset_registry.csv', ASSET_COLUMNS, assets), ('field_catalog.csv', FIELD_COLUMNS, fields),
                   ('data_dictionary.csv', projection['headers'] + ADDED_MAPPING_COLUMNS, mappings)]
    max_cells = {}
    for filename, headers, expected in schema_rows:
        actual_headers, actual_rows = read_csv(output / filename)
        check(actual_headers == headers and len(actual_rows) == len(expected), filename + ' serialized shape')
        maximum = 0
        for original, actual in zip(expected, actual_rows):
            for key in headers:
                value = cell(original[key])
                check(actual[key] == value, filename + ' cell round trip: ' + key)
                maximum = max(maximum, len(actual[key]))
                if isinstance(original[key], (list, dict)):
                    check(json.loads(actual[key]) == original[key], filename + ' JSON cell round trip: ' + key)
        max_cells[filename] = maximum
        check(maximum <= 32767, filename + ' Excel text cell limit; refuse truncation')
    return {'status': 'passed', 'checks_passed': checks, 'errors': [], 'input_records': len(projection['records']),
            'asset_rows': len(assets), 'field_rows': len(fields), 'dictionary_rows': len(mappings),
            'atomic_relationships': len(ops), 'original_json_nodes_preserved': node_count,
            'original_payload_round_trip': 'all records, nested objects, arrays and values match parsed input',
            'original_mapping_columns_preserved': len(projection['headers']),
            'field_description_source_types': dict(Counter(field['description_source_type'] for field in fields)),
            'source_mapping_description_source_types': dict(Counter(row['source_description_source_type'] for row in mappings)),
            'target_mapping_description_source_types': dict(Counter(row['snowflake_description_source_type'] for row in mappings)),
            'maximum_cell_characters': max_cells,
            'scope': 'Checks validate the deterministic projection and preservation of reported input. They do not verify repositories, production execution, physical source file binding, or business meaning.'}


def commit_outputs(staged, destination, filenames):
    """Restore the previous complete snapshot if a normal replacement fails."""
    backup = Path(tempfile.mkdtemp(prefix='datadic-backup-'))
    previous, replaced = {}, []
    keep_backup = False
    try:
        for name in filenames:
            target = destination / name
            require(not target.is_symlink() and (not target.exists() or target.is_file()),
                    'Output target must be a regular file: ' + str(target))
            previous[name] = target.exists()
            if previous[name]:
                shutil.copy2(target, backup / name)
        try:
            for name in filenames:
                (staged / name).replace(destination / name)
                replaced.append(name)
        except BaseException as error:
            failures = []
            for name in reversed(replaced):
                try:
                    if previous[name]:
                        # The backup may be on another filesystem or Windows drive.
                        # Copy locally before the atomic destination replacement.
                        with tempfile.NamedTemporaryFile(dir=destination, prefix='.restore-',
                                                         delete=False) as handle:
                            recovery = Path(handle.name)
                        try:
                            shutil.copy2(backup / name, recovery)
                            recovery.replace(destination / name)
                        finally:
                            recovery.unlink(missing_ok=True)
                    else:
                        (destination / name).unlink(missing_ok=True)
                except OSError as recovery_error:
                    failures.append(str(recovery_error))
            if failures:
                keep_backup = True
                raise OSError('Output restoration was interrupted; previous files are retained at '
                              + str(backup) + '. ' + '; '.join(failures)) from error
            raise
    finally:
        if not keep_backup:
            shutil.rmtree(backup, ignore_errors=True)


def _generate(args, graph_id):
    load_input(args.input)
    projection = project(args.input)
    assets, fields, field_assets, nodes, ops = build_catalogs(projection, graph_id)
    mappings = enrich_mappings(projection, graph_id, field_assets)
    destination = args.output
    destination.mkdir(parents=True, exist_ok=True)
    latest = latest_html_path(destination)
    # Fully generate, serialize, and validate in isolation before replacing any
    # delivered CSV. A rejected projection leaves the previous bundle intact.
    with tempfile.TemporaryDirectory(dir=destination, prefix='.generation-') as staging:
        output = Path(staging)
        write_csv(output / 'asset_registry.csv', ASSET_COLUMNS, assets)
        write_csv(output / 'field_catalog.csv', FIELD_COLUMNS, fields)
        write_csv(output / 'data_dictionary.csv', projection['headers'] + ADDED_MAPPING_COLUMNS, mappings)
        validation = validate(projection, graph_id, assets, fields, mappings, nodes, ops, output)
        manifest = {'generator_version': VERSION, 'input_file': args.input.name, 'input_sha256': projection['input_sha256'],
            'graph_id': graph_id, 'snapshot_id': projection['snapshot_id'], 'input_contract': 'POC exported mapping-record array',
            'outputs': {name: {'sha256': digest_file(output / name), 'rows': count, 'columns': len(columns)}
                        for name, count, columns in [('asset_registry.csv', len(assets), ASSET_COLUMNS),
                                                    ('field_catalog.csv', len(fields), FIELD_COLUMNS),
                                                    ('data_dictionary.csv', len(mappings), projection['headers'] + ADDED_MAPPING_COLUMNS)]},
            'counts': {'input_mapping_records': len(projection['records']), 'assets': len(assets), 'fields': len(fields),
                       'dictionary_rows': len(mappings), 'atomic_relationships': len(ops),
                       'target_stages': dict(Counter(r['snowflake_stage'] for r in mappings)),
                       'scored_relationships': sum(o['confidence_state'] == 'scored' for o in ops.values()),
                   'field_description_source_types': dict(Counter(field['description_source_type'] for field in fields))},
            'interpretation': {'source_asset': 'Program-scoped multi-value source context; actual physical Ultracs file not supplied.',
                'source_coordinates': 'Only strict attribute/value/subvalue locators are normalized. @ID is a record-key reference. Variables are not physical file names.',
                'hvr_asset': 'Reported extract file and header/slot metadata, not an inferred HVR table.',
                'confidence': 'Input contains categorical mapping labels only. Each atomic relationship remains Unscored; labels are preserved at their original mapping scope.',
                'path_complete': 'Legacy mapping flag means structural continuity of the recorded locator/reference association. It does not establish physical source file binding or runtime correctness.',
                'description_provenance': 'Descriptions remain exact input text. Only explicit recognized per-column origin/type claims distinguish AI-generated from existing metadata; supplied text without those claims has unknown provenance. Missing descriptions are not_supplied. Input paths and author names alone do not establish origin.',
            'governance': 'Missing owner, steward, domain, update frequency, PII, row count and reviewed business definition remain blank/unknown.',
                'preservation': 'Original JSON retained semantically in original_record_json; whitespace and file byte formatting are represented by the immutable input SHA256, not preserved as CSV formatting.'}}
        # Build the HTML from the same checked snapshot before replacing any output.
        # Snapshot metadata stays embedded; no standalone audit/report files are created.
        build(output, manifest=manifest, verbose=False)
        filenames = ['asset_registry.csv', 'field_catalog.csv', 'data_dictionary.csv']
        if latest is None:
            filenames.append('index.html')
        commit_outputs(output, destination, filenames)
        if latest is not None:
            publish_latest_snapshot(output / 'index.html', destination)
    output = destination
    html = latest if latest is not None else destination / 'index.html'
    print(json.dumps({'status': 'passed', 'output_directory': str(output.resolve()), **manifest['counts'], 'checks_passed': validation['checks_passed'], 'html': str(html.resolve()), 'latest_html': str(latest) if latest is not None else None}, indent=2))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=DEFAULT_INPUT, help='POC mapping-record JSON array')
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT, help='CSV bundle directory; direct 03-output subfolders publish HTML to 03-output/index.html')
    parser.add_argument('--graph-id', help='Stable graph identifier; defaults to input filename stem')
    args = parser.parse_args(argv)
    graph_id = args.graph_id if args.graph_id is not None else args.input.stem
    require(isinstance(graph_id, str) and bool(graph_id.strip()), '--graph-id must not be empty.')
    directories = {args.output.resolve()}
    latest = latest_html_path(args.output)
    if latest is not None:
        directories.add(latest.parent.resolve())
    with ExitStack() as locks:
        for directory in sorted(directories, key=str):
            locks.enter_context(output_lock(directory))
        _generate(args, graph_id)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, KeyError, AssertionError, TypeError, OSError) as error:
        print('Generation failed: ' + str(error), file=sys.stderr)
        sys.exit(1)
