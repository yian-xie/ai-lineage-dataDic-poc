"""Prepare evidence for the active assistant, then validate/apply its drafts.

These prepare/apply APIs make no model calls. Explicit Copilot authoring lives
in enrichment.copilot; no sentence templates or implicit HTML builds are used.
"""
from __future__ import annotations

import argparse
import copy
import json
import shutil
from pathlib import Path

from lineage_poc.dictionary.description_provenance import DESCRIPTION_COLUMNS
from lineage_poc.dictionary.io import (
    CSV_FILES, ID_COLUMNS, atomic_write, commit_outputs, digest_file, equal,
    parse_json, pointer, read_tables, require, scoped, staging_directory, write_table,
)
from lineage_poc.dictionary.legacy_projection import cell, js
from lineage_poc.validation.bundle import DESCRIPTION_SURFACES, validate_bundle
from lineage_poc.validation.descriptions import (
    nonempty, utc_time, validate_assessment, validate_sentences,
)
from .contracts import (
    CONTEXT_VERSION, DRAFTS_VERSION, ENRICHMENT_COLUMNS, RUBRIC_ID, description_reference, eligible,
)

CONTEXT_MAX_REFERENCES = 32
CONTEXT_MAX_VALUE_CHARACTERS = 2048
CONTEXT_MAX_MAPPING_ROWS = 3
GENERATION_METHOD = (
    'Field-specific descriptions and criterion judgements authored by the active AI after reviewing '
    'bounded CSV contexts; local code verifies evidence and computes the sum.'
)


def _snapshot(input_dir):
    validation = validate_bundle(input_dir)
    tables = read_tables(input_dir)
    require(all(table.sha256 == validation['outputs'][name]['sha256'] for name, table in tables.items()),
            'Input bundle changed during validation; prepare a fresh context')
    return tables, validation


def _reference(table, row, values, column, path=None):
    value = row[column] if path is None else pointer(values[column], path)
    return {'file': table.name, 'input_sha256': table.sha256,
            'graph_id': row['graph_id'], 'snapshot_id': row['snapshot_id'],
            'row_id_column': ID_COLUMNS[table.name], 'row_id': row[ID_COLUMNS[table.name]],
            'column': column, 'json_pointer': path, 'value': copy.deepcopy(value)}


def _bounded_context(field, tables):
    references, omissions = {}, []
    field_table = tables['field_catalog.csv']
    _, field_values = field_table.index()[scoped(field, 'field_id')]

    def add(table, row, values, column, path=None):
        if column not in row:
            return
        reference = _reference(table, row, values, column, path)
        if (len(js(reference['value'])) > CONTEXT_MAX_VALUE_CHARACTERS
                or len(references) >= CONTEXT_MAX_REFERENCES):
            omissions.append({'file': table.name, 'row_id': row[ID_COLUMNS[table.name]],
                              'column': column, 'json_pointer': path,
                              'reason': 'Bounded context limit; inspect the unchanged CSV if needed.'})
            return
        if any(equal(reference, previous) for previous in references.values()):
            return
        references['E' + str(len(references) + 1)] = reference

    for column in ('field_id', 'field_name', 'business_name', 'source_locator',
                   'record_reference', 'attribute_position', 'value_position',
                   'subvalue_position', 'physical_binding_status', 'description'):
        add(field_table, field, field_values, column)
    for column in ('notes_json', 'evidence_json'):
        add(field_table, field, field_values, column, '')
    for property_name in ('identity_resolution_status', 'basic_expression', 'source_references'):
        if property_name in field_values['metadata_json']:
            add(field_table, field, field_values, 'metadata_json', '/' + property_name)
    mappings = tables['data_dictionary.csv']
    matched = [(row, values) for row, values in zip(mappings.rows, mappings.json_rows)
               if (row['graph_id'], row['snapshot_id'], row['source_field_id']) ==
               (field['graph_id'], field['snapshot_id'], field['field_id'])]
    for row, values in matched[:CONTEXT_MAX_MAPPING_ROWS]:
        for column in ('extract_column', 'extract_file', 'extract_position', 'basic_expression',
                       'basic_transformation', 'basic_comment', 'original_mapping_notes',
                       'snowflake_column', 'snowflake_description', 'target_source_expression',
                       'target_projection_expression'):
            add(mappings, row, values, column)
        add(mappings, row, values, 'review_notes_json', '')
    return {
        'graph_id': field['graph_id'], 'snapshot_id': field['snapshot_id'], 'field_id': field['field_id'],
        'field_name': field['field_name'], 'business_name': field['business_name'],
        'description_missing': True, 'evidence_refs': references,
        'mapping_rows_available': len(matched),
        'mapping_rows_included': min(len(matched), CONTEXT_MAX_MAPPING_ROWS), 'omitted_evidence': omissions,
    }


def prepare_context(input_dir: Path, output_dir: Path) -> dict:
    """Write hash-bound, bounded context for eligible fields, without generating prose."""
    input_dir, output_dir = Path(input_dir).resolve(), Path(output_dir).resolve()
    require(input_dir != output_dir, 'Context output must be separate from the input bundle')
    tables, validation = _snapshot(input_dir)
    fields = tables['field_catalog.csv'].rows
    selected = [row for row in fields if eligible(row)]
    protected = [row for row in fields if row['source_system'] == 'Ultracs' and row['layer'] == 'source'
                 and row['description'].strip()]
    payload = {
        'schema_version': CONTEXT_VERSION, 'drafts_schema_version': DRAFTS_VERSION,
        'rubric_id': RUBRIC_ID, 'verification_mode': 'supplied_csv_only',
        'input_hashes': {name: table.sha256 for name, table in tables.items()},
        'eligible_ids': [dict(zip(('graph_id', 'snapshot_id', 'field_id'), scoped(row, 'field_id')))
                         for row in selected],
        'protected_ids': [dict(zip(('graph_id', 'snapshot_id', 'field_id'), scoped(row, 'field_id')))
                          for row in protected],
        'bounds': {'maximum_references_per_field': CONTEXT_MAX_REFERENCES,
                   'maximum_reference_value_characters': CONTEXT_MAX_VALUE_CHARACTERS,
                   'maximum_mapping_rows_per_field': CONTEXT_MAX_MAPPING_ROWS,
                   'policy': 'Omit whole oversized evidence values; never truncate or alter cited input.'},
        'fields': [_bounded_context(row, tables) for row in selected],
        'next_action': 'The active AI assistant must author drafts.json using description-evidence-v1; '
                       'Python does not generate descriptions or criterion judgments.',
    }
    context_path = output_dir / 'context.json'
    _unchanged_inputs(input_dir, payload['input_hashes'])
    atomic_write(context_path, (json.dumps(payload, ensure_ascii=False, indent=2) + '\n').encode('utf-8'))
    return {'status': 'awaiting_assistant_drafts' if selected else 'no_eligible_fields',
            'input_directory': str(input_dir), 'output_directory': str(output_dir),
            'context_file': str(context_path), 'context_sha256': digest_file(context_path),
            'input_hashes': payload['input_hashes'], 'eligible_fields': len(selected),
            'protected_ultracs_descriptions': len(protected), 'rubric_id': RUBRIC_ID,
            'validation': validation}


def _unchanged_inputs(input_dir, hashes):
    require(all(digest_file(input_dir / name) == digest for name, digest in hashes.items()),
            'Input bundle changed; stale hashes require fresh context and assistant drafts')


def _drafts(payload, tables, *, expected_ids=None):
    keys = {'schema_version', 'rubric_id', 'input_hashes', 'run_id', 'generator', 'model',
            'generated_at', 'results'}
    require(isinstance(payload, dict) and set(payload) == keys, 'Unsupported drafts.json top-level contract')
    require(payload['schema_version'] == DRAFTS_VERSION, 'Unsupported drafts schema_version')
    require(payload['rubric_id'] == RUBRIC_ID, 'Unsupported description rubric; no invented rubric is accepted')
    hashes = {name: table.sha256 for name, table in tables.items()}
    require(payload['input_hashes'] == hashes, 'Stale input hashes: prepare fresh context and assistant drafts')
    require(nonempty(payload['run_id']) and nonempty(payload['generator']),
            'Drafts must record the actual run_id and active assistant generator')
    require(payload['model'] is None or nonempty(payload['model']), 'Draft model must be an actual identifier or null')
    utc_time(payload['generated_at'], 'generated_at')
    require(isinstance(payload['results'], list), 'Draft results must be an array')
    all_fields = tables['field_catalog.csv'].index()
    expected = {key for key, (row, _) in all_fields.items() if eligible(row)}
    if expected_ids is not None:
        require(isinstance(expected_ids, set) and expected_ids <= expected,
                'Batch identities must refer only to eligible missing Ultracs fields')
        expected = expected_ids
    results = {}
    for result in payload['results']:
        require(isinstance(result, dict), 'Each draft result must be an object')
        identity_keys = ('graph_id', 'snapshot_id', 'field_id')
        require(all(nonempty(result.get(key)) for key in identity_keys), 'Draft result needs its canonical scoped ID')
        key = tuple(result[name] for name in identity_keys)
        require(key not in results, 'Duplicate draft field ID')
        require(key in all_fields, 'Unknown draft field ID')
        require(key in expected, 'Protected or out-of-scope field ID cannot receive a draft')
        status = result.get('status')
        if status == 'draft':
            require(set(result) == set(identity_keys) | {'status', 'description', 'assessment'},
                    'Unsupported draft result properties')
            validate_sentences(result['description'])
            assessment = result['assessment']
            validate_assessment(assessment, tables=tables, field=all_fields[key][0])
            require(assessment['assessed_by'] == payload['generator']
                    and assessment.get('model') == payload['model']
                    and assessment['assessed_at'] == payload['generated_at'],
                    'Draft generator/model/time must agree with its assessment attribution')
        elif status == 'needs_evidence':
            require(set(result) == set(identity_keys) |
                    {'status', 'description', 'assessment', 'reason', 'open_questions'},
                    'Unsupported needs_evidence result properties')
            require(result['description'] is None and result['assessment'] is None,
                    'needs_evidence must not contain fabricated prose or an assessment')
            require(nonempty(result['reason']) and isinstance(result['open_questions'], list)
                    and result['open_questions'] and all(nonempty(question) for question in result['open_questions']),
                    'needs_evidence requires a reason and explicit open questions')
        else:
            raise ValueError('Draft status must be draft or needs_evidence')
        results[key] = result
    require(set(results) == expected, 'Drafts require exactly one result for every eligible missing Ultracs field')
    return results


def _fill_field(row, values, result, payload):
    row['description_generation_status'] = result['status']
    row['description_confidence_method'] = RUBRIC_ID
    if result['status'] == 'needs_evidence':
        row['description_confidence_rationale'] = result['reason'] + ' Open questions: ' + ' '.join(result['open_questions'])
        return
    description, assessment = result['description'], copy.deepcopy(result['assessment'])
    score = sum(component['points'] for component in assessment['components'])
    assessment['score_10'] = score
    previous = {column: copy.deepcopy(values[column] if column in values else row[column])
                for column in DESCRIPTION_SURFACES + ['original_field_json']}
    reference = description_reference(row)
    provenance = {
        'source_type': 'ai_generated', 'status': 'draft', 'enrichment_run_id': payload['run_id'],
        'generator': payload['generator'], 'model': payload['model'], 'author': None,
        'generated_at': payload['generated_at'], 'method': GENERATION_METHOD,
        'verification_mode': 'supplied_csv_only', 'source_reference': reference,
        'input_sha256': payload['input_hashes'], 'previous': previous,
        'description_assessment': assessment, 'is_approved_business_definition': False,
    }
    node = copy.deepcopy(values['original_field_json'])
    require(isinstance(node.get('metadata'), dict), 'Unsupported canonical metadata for enrichment')
    node['description'], node['description_origin'] = description, 'ai_generated'
    node['metadata']['ai_description_enrichment'] = {
        'source_type': 'ai_generated', 'status': 'draft', 'run_id': payload['run_id'],
        'generator': payload['generator'], 'generated_at': payload['generated_at'],
        'source_reference': reference, 'rubric_id': RUBRIC_ID,
        'description_confidence_score_10': score,
        'assessment_reference': description_reference(row, 'description_confidence_json'),
        'is_approved_business_definition': False,
    }
    row.update(description=description, description_origin='ai_generated',
               description_source_type='ai_generated', description_author='',
               description_generator=payload['generator'], description_source_reference=reference,
               description_source_pointer='', description_provenance_json=js(provenance),
               original_field_json=js(node), description_confidence_score_10=str(score),
               description_confidence_rationale=assessment['rationale'], description_confidence_json=js(assessment))
    values.update(description_provenance_json=provenance, original_field_json=node,
                  description_confidence_json=assessment)


def _fill_detail(detail, field, values, payload):
    previous = copy.deepcopy(detail)
    detail.update(description=field['description'], origin='ai_generated',
                  source_refs_json=[{'file': 'field_catalog.csv', 'graph_id': field['graph_id'],
                                     'snapshot_id': field['snapshot_id'], 'field_id': field['field_id'],
                                     'column': 'description', 'evidence_role': 'ai_draft_output'}],
                  previous_description_metadata=previous,
                  description_provenance={
                      'source_type': 'ai_generated', 'generator': payload['generator'],
                      'generated_at': payload['generated_at'], 'source_reference': description_reference(field),
                      'description_assessment': copy.deepcopy(values['description_confidence_json']),
                      'is_approved_business_definition': False,
                  })


def _reconcile_coverage(row, values):
    coverage = copy.deepcopy(values['input_property_map_json'])
    base = values['provenance_json']['input_pointer']
    escaping = values['provenance_json'].get('csv_text_escaping', {})
    for item in coverage:
        original = pointer(values['original_record_json'], item['input_pointer'][len(base):])
        destinations, kinds = [], set()
        for destination in item['destinations']:
            column, path = destination['column'], destination['json_pointer']
            if column in values:
                actual = pointer(values[column], path)
                preserves = equal(actual, original)
                kind = 'structured' if column != 'original_record_json' else None
            else:
                actual = escaping.get(column, {}).get('original_value', row[column])
                preserves = not path and actual == cell(original)
                kind = 'visible'
            if preserves:
                destinations.append(destination)
                if kind:
                    kinds.add(kind)
        require(any(destination['column'] == 'original_record_json' for destination in destinations),
                'Original input property archive was lost')
        item['destinations'] = destinations
        item['coverage_state'] = ('verified_visible' if 'visible' in kinds
                                  else 'verified_structured' if kinds else 'verified_raw')
    row['input_property_map_json'] = js(coverage)
    values['input_property_map_json'] = coverage


def apply_drafts(input_dir: Path, drafts_path: Path, output_dir: Path) -> dict:
    """Validate complete assistant decisions, apply only eligible description surfaces."""
    input_dir, output_dir = Path(input_dir).resolve(), Path(output_dir).resolve()
    drafts_path = Path(drafts_path).resolve()
    require(input_dir != output_dir, 'Enrichment output must be a separate bundle; input files are immutable')
    require(drafts_path not in {output_dir / name for name in CSV_FILES},
            'CSV output must not replace the drafts input file')
    tables, _ = _snapshot(input_dir)
    drafts_hash = digest_file(drafts_path)
    payload = parse_json(drafts_path.read_text(encoding='utf-8-sig'))
    results = _drafts(payload, tables)
    fields = tables['field_catalog.csv']
    field_index = fields.index()
    for column in ENRICHMENT_COLUMNS:
        if column not in fields.headers:
            fields.headers.append(column)
            for row, values in zip(fields.rows, fields.json_rows):
                row[column] = 'null' if column.endswith('_json') else ''
                if column.endswith('_json'):
                    values[column] = None
    for identity, result in results.items():
        row, values = field_index[identity]
        _fill_field(row, values, result, payload)
    changed = {identity for identity, result in results.items() if result['status'] == 'draft'}
    mappings = tables['data_dictionary.csv']
    for column in ENRICHMENT_COLUMNS:
        name = 'source_' + column
        if name not in mappings.headers:
            mappings.headers.append(name)
            for row, values in zip(mappings.rows, mappings.json_rows):
                row[name] = 'null' if name.endswith('_json') else ''
                if name.endswith('_json'):
                    values[name] = None
    for row, values in zip(mappings.rows, mappings.json_rows):
        scope = row['graph_id'], row['snapshot_id']
        source_key = scope + (row['source_field_id'],)
        if source_key in results:
            field, field_values = field_index[source_key]
            for column in ENRICHMENT_COLUMNS:
                row['source_' + column] = field[column]
                if column.endswith('_json'):
                    values['source_' + column] = field_values[column]
            if source_key in changed:
                row['source_description'], row['source_description_origin'] = field['description'], field['description_origin']
                for column in DESCRIPTION_COLUMNS:
                    row['source_' + column] = field[column]
                    if column.endswith('_json'):
                        values['source_' + column] = field_values[column]
        local_changed = any(scope + (node['field_id'],) in changed for node in values['field_catalog_json'])
        if local_changed:
            values['field_catalog_json'] = [
                copy.deepcopy(field_index[scope + (node['field_id'],)][1]['original_field_json'])
                if scope + (node['field_id'],) in changed else node for node in values['field_catalog_json']
            ]
            row['field_catalog_json'] = js(values['field_catalog_json'])
            for detail in values['description_details_json']:
                identity = scope + (detail['field_id'],)
                if identity in changed:
                    _fill_detail(detail, *field_index[identity], payload)
            row['description_details_json'] = js(values['description_details_json'])
            _reconcile_coverage(row, values)
    with staging_directory(output_dir, 'enrichment') as staged:
        shutil.copyfile(input_dir / 'asset_registry.csv', staged / 'asset_registry.csv')
        write_table(staged / fields.name, fields.headers, fields.rows)
        write_table(staged / mappings.name, mappings.headers, mappings.rows)
        validation = validate_bundle(staged, input_dir)
        _unchanged_inputs(input_dir, payload['input_hashes'])
        require(digest_file(drafts_path) == drafts_hash, 'Drafts changed during application')
        commit_outputs(staged, output_dir, CSV_FILES)
    validation['bundle_directory'] = str(output_dir)
    return {'status': 'passed', 'input_directory': str(input_dir), 'output_directory': str(output_dir),
            'drafts_file': str(drafts_path), 'drafts_sha256': drafts_hash,
            'input_hashes': payload['input_hashes'], 'run_id': payload['run_id'], 'rubric_id': RUBRIC_ID,
            'drafts_applied': len(changed), 'needs_evidence': len(results) - len(changed),
            'protected_ultracs_descriptions': sum(row['source_system'] == 'Ultracs' and row['layer'] == 'source'
                                                and scoped(row, 'field_id') not in results for row in fields.rows),
            'outputs': validation['outputs'], 'validation': validation}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    for command in ('prepare', 'apply'):
        subparser = commands.add_parser(command)
        subparser.add_argument('--input', type=Path, required=True)
        subparser.add_argument('--output', type=Path, required=True)
        if command == 'apply':
            subparser.add_argument('--drafts', type=Path, required=True)
    args = parser.parse_args(argv)
    result = (prepare_context(args.input, args.output) if args.command == 'prepare'
              else apply_drafts(args.input, args.drafts, args.output))
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
