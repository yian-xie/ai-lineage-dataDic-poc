import copy
import json
import shutil
from pathlib import Path

import pytest

from lineage_poc.dictionary.generate import load_input
from lineage_poc.dictionary.io import CSV_FILES, commit_outputs, digest_file, read_tables, write_table
from lineage_poc.dictionary.legacy_projection import js
from lineage_poc.dictionary.workflow import generate_bundle
from lineage_poc.enrichment.workflow import apply_drafts
from lineage_poc.validation.bundle import validate_bundle
from lineage_poc.viewers.dictionary.build_viewer import build

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / '.github' / 'skills' / 'ai-description-enrichment' / 'references'


def save(path, payload):
    path.write_bytes(json.dumps(payload, ensure_ascii=False).encode('utf-8'))
    return path


@pytest.mark.parametrize('case', [
    'stale-hashes', 'duplicate-id', 'unknown-id', 'protected-id', 'missing-result',
    'invented-rubric', 'assessment-rubric', 'arithmetic', 'calculation',
    'boolean-points', 'missing-criterion', 'duplicate-criterion', 'invented-weight',
    'positive-no-reference', 'unused-reference', 'evidence-hash', 'evidence-value',
    'evidence-file', 'evidence-column', 'evidence-pointer', 'scalar-pointer',
    'evidence-row', 'evidence-scope', 'self-evidence', 'extra-top-key', 'extra-result-key',
    'no-sentence', 'three-sentences', 'too-long', 'non-utc-time', 'wrong-generator',
    'needs-fabricated-prose', 'needs-scored', 'needs-no-questions',
])
def test_rejects_invalid_drafts_before_writing(case, small_bundle, drafts, needs_drafts, work):
    payload = copy.deepcopy(needs_drafts if case.startswith('needs-') else drafts)
    result = payload['results'][0]
    assessment = result['assessment']
    component = assessment['components'][0] if assessment is not None else None
    ref = assessment['evidence_refs']['E1'] if assessment is not None else None
    if case == 'stale-hashes':
        payload['input_hashes']['field_catalog.csv'] = '0' * 64
    elif case == 'duplicate-id':
        payload['results'].append(copy.deepcopy(result))
    elif case == 'unknown-id':
        result['field_id'] = 'unknown:field'
    elif case == 'protected-id':
        result['field_id'] = next(row['field_id'] for row in read_tables(small_bundle)['field_catalog.csv'].rows
                                  if row['source_system'] == 'Snowflake' and row['description'])
    elif case == 'missing-result':
        payload['results'] = []
    elif case == 'invented-rubric':
        payload['rubric_id'] = 'name-confidence-v99'
    elif case == 'assessment-rubric':
        assessment['rubric_id'] = 'invented'
    elif case == 'arithmetic':
        assessment['score_10'] += 1
    elif case == 'calculation':
        assessment['calculation'] = '7 / 10'
    elif case == 'boolean-points':
        component['points'] = True
    elif case == 'missing-criterion':
        assessment['components'].pop()
    elif case == 'duplicate-criterion':
        assessment['components'][1]['criterion'] = assessment['components'][0]['criterion']
    elif case == 'invented-weight':
        component['maximum'] = 10
    elif case == 'positive-no-reference':
        component['evidence_refs'] = []
    elif case == 'unused-reference':
        assessment['evidence_refs']['unused'] = copy.deepcopy(ref)
    elif case == 'evidence-hash':
        ref['input_sha256'] = '0' * 64
    elif case == 'evidence-value':
        ref['value'] = 'invented value'
    elif case == 'evidence-file':
        ref['file'] = 'repository.sql'
    elif case == 'evidence-column':
        ref['column'] = 'unsupported_column'
    elif case == 'evidence-pointer':
        ref = assessment['evidence_refs']['E8']
        ref['json_pointer'] = '/missing'
    elif case == 'scalar-pointer':
        ref['json_pointer'] = ''
    elif case == 'evidence-row':
        ref['row_id'] = 'unknown:row'
    elif case == 'evidence-scope':
        ref['snapshot_id'] = 'other-snapshot'
    elif case == 'self-evidence':
        ref['column'] = 'description_confidence_json'
    elif case == 'extra-top-key':
        payload['silent_defaults'] = True
    elif case == 'extra-result-key':
        result['replace_existing'] = True
    elif case == 'no-sentence':
        result['description'] = 'Unfinished text'
    elif case == 'three-sentences':
        result['description'] = 'First. Second. Third.'
    elif case == 'too-long':
        result['description'] = 'X' * 1001 + '.'
    elif case == 'non-utc-time':
        payload['generated_at'] = '2026-10-20T10:00:00+13:00'
    elif case == 'wrong-generator':
        payload['generator'] = 'Unattributed template engine'
    elif case == 'needs-fabricated-prose':
        result['description'] = 'Invented prose.'
    elif case == 'needs-scored':
        result['assessment'] = {'score_10': 0}
    elif case == 'needs-no-questions':
        result['open_questions'] = []
    output = work / 'output'
    output.mkdir()
    sentinel = output / 'keep.txt'
    sentinel.write_bytes(b'unchanged')
    before = {name: digest_file(small_bundle / name) for name in CSV_FILES}
    with pytest.raises(ValueError):
        apply_drafts(small_bundle, save(work / 'drafts.json', payload), output)
    assert sentinel.read_bytes() == b'unchanged'
    assert list(output.iterdir()) == [sentinel]
    assert {name: digest_file(small_bundle / name) for name in CSV_FILES} == before


@pytest.mark.parametrize('case', [
    'duplicate-header', 'ragged-row', 'duplicate-json-key', 'nonfinite-json', 'overflow-json',
    'empty-new-json', 'cell-limit', 'scope', 'field-join', 'canonical-mirror',
    'embedded-mirror', 'detail-mirror', 'source-repeat', 'operation-endpoint',
    'operation-output-scope', 'operation-binding', 'operation-confidence',
    'operation-association', 'field-topology', 'asset-topology', 'field-incident',
    'coverage-pointer', 'coverage-destination', 'coverage-state', 'raw-record',
])
def test_rejects_bad_bundle_without_repair(case, small_bundle, work):
    bundle = work / 'bad'
    shutil.copytree(small_bundle, bundle)
    tables = read_tables(bundle)
    fields, mappings, assets = (tables[name] for name in
                               ('field_catalog.csv', 'data_dictionary.csv', 'asset_registry.csv'))
    field, field_values = fields.rows[0], fields.json_rows[0]
    row, values = mappings.rows[0], mappings.json_rows[0]
    changed = fields
    if case == 'duplicate-header':
        path = bundle / fields.name
        text = path.read_bytes().decode('utf-8-sig')
        path.write_bytes(text.replace('graph_id,snapshot_id', 'graph_id,graph_id', 1).encode('utf-8-sig'))
        changed = None
    elif case == 'ragged-row':
        path = bundle / fields.name
        path.write_bytes(path.read_bytes() + b'one,extra\r\n')
        changed = None
    elif case == 'duplicate-json-key':
        field['notes_json'] = '{"duplicate":1,"duplicate":2}'
    elif case == 'nonfinite-json':
        field['notes_json'] = '[NaN]'
    elif case == 'overflow-json':
        field['notes_json'] = '[1e999]'
    elif case == 'empty-new-json':
        fields.headers.append('description_confidence_json')
        for field in fields.rows:
            field['description_confidence_json'] = ''
    elif case == 'cell-limit':
        field['description'] = 'X' * 32768
    elif case == 'scope':
        field['graph_id'] = 'other-graph'
    elif case == 'field-join':
        field['asset_id'] = 'missing:asset'
    elif case == 'canonical-mirror':
        field_values['original_field_json']['description'] = 'Changed canonical description.'
        field['original_field_json'] = js(field_values['original_field_json'])
    elif case == 'embedded-mirror':
        values['field_catalog_json'][0]['field_name'] = 'changed'
        row['field_catalog_json'] = js(values['field_catalog_json'])
        changed = mappings
    elif case == 'detail-mirror':
        values['description_details_json'][0]['description'] = 'Changed detail.'
        row['description_details_json'] = js(values['description_details_json'])
        changed = mappings
    elif case == 'source-repeat':
        mappings.rows[1]['business_field_label'] = 'conflicting source label'
        changed = mappings
    elif case.startswith('operation-'):
        operation = values['process_details_json'][0]
        if case == 'operation-endpoint':
            operation['source_field_ids'] = ['missing:field']
        elif case == 'operation-output-scope':
            values['operation_output_scope_json'][operation['relationship_id']] = ['missing:field']
            row['operation_output_scope_json'] = js(values['operation_output_scope_json'])
        elif case == 'operation-binding':
            operation['output_input_bindings_json'][operation['target_field_ids'][0]] = [{'field_id': 'missing'}]
        elif case == 'operation-confidence':
            operation['confidence_score_10'] = 11
        elif case == 'operation-association':
            operation['dictionary_entry_ids'] = ['missing:mapping']
        row['process_details_json'] = js(values['process_details_json'])
        changed = mappings
    elif case == 'field-topology':
        field = next(row for row in fields.rows if json.loads(row['upstream_field_ids_json']))
        field['upstream_field_ids_json'] = '[]'
    elif case == 'asset-topology':
        asset = next(row for row in assets.rows if json.loads(row['downstream_asset_ids_json']))
        asset['downstream_asset_ids_json'] = '[]'
        changed = assets
    elif case == 'field-incident':
        field_values['transformation_logic_json'][0]['expression'] = 'altered'
        field['transformation_logic_json'] = js(field_values['transformation_logic_json'])
    elif case.startswith('coverage-'):
        coverage = values['input_property_map_json']
        if case == 'coverage-pointer':
            coverage[0]['input_pointer'] = '/unknown'
        elif case == 'coverage-destination':
            coverage[0]['destinations'] = [{'column': 'source_description', 'json_pointer': ''}]
        else:
            coverage[0]['coverage_state'] = 'verified_visible'
        row['input_property_map_json'] = js(coverage)
        changed = mappings
    elif case == 'raw-record':
        values['original_record_json']['notes'] = 'modified input archive'
        row['original_record_json'] = js(values['original_record_json'])
        changed = mappings
    if changed is not None:
        write_table(bundle / changed.name, changed.headers, changed.rows)
    before = {name: digest_file(bundle / name) for name in CSV_FILES}
    with pytest.raises(ValueError):
        validate_bundle(bundle)
    assert {name: digest_file(bundle / name) for name in CSV_FILES} == before
    assert {path.name for path in bundle.iterdir()} == set(CSV_FILES)


def test_baseline_comparison_protects_unrelated_metadata(small_bundle, drafts, work):
    apply_drafts(small_bundle, save(work / 'drafts.json', drafts), work / 'enriched')
    fields = read_tables(work / 'enriched')['field_catalog.csv']
    row = next(row for row in fields.rows if row['source_system'] != 'Ultracs')
    row['business_name'] = 'unrelated change'
    write_table(work / 'enriched' / fields.name, fields.headers, fields.rows)
    validate_bundle(work / 'enriched')
    with pytest.raises(ValueError, match='Protected/unrelated'):
        validate_bundle(work / 'enriched', small_bundle)


def test_unknown_original_columns_are_preserved(small_bundle, drafts, work):
    bundle = work / 'input'
    shutil.copytree(small_bundle, bundle)
    fields = read_tables(bundle)['field_catalog.csv']
    fields.headers += ['custom_scalar', 'custom_json']
    for row in fields.rows:
        row.update(custom_scalar='kept verbatim', custom_json='{"nested":[null,true,""]}')
    write_table(bundle / fields.name, fields.headers, fields.rows)
    hashes = {name: digest_file(bundle / name) for name in CSV_FILES}
    drafts['input_hashes'] = hashes
    for result in drafts['results']:
        for ref in result['assessment']['evidence_refs'].values():
            ref['input_sha256'] = hashes[ref['file']]
    apply_drafts(bundle, save(work / 'drafts.json', drafts), work / 'enriched')
    after = read_tables(work / 'enriched')['field_catalog.csv']
    assert after.headers[:len(fields.headers)] == fields.headers
    assert all(row['custom_scalar'] == 'kept verbatim'
               and row['custom_json'] == '{"nested":[null,true,""]}' for row in after.rows)


def test_invalid_input_contracts_are_not_guessed(work):
    original = json.loads((EXAMPLES / 'sample-input.json').read_bytes())
    bad = [
        {'nodes': [], 'edges': []},
        [],
        original + copy.deepcopy(original),
    ]
    for confidence in (8, '80%', {'score_10': 8}):
        records = copy.deepcopy(original)
        records[0]['confidence'] = confidence
        bad.append(records)
    records = copy.deepcopy(original)
    records[0]['ultracs']['confidence_score_10'] = 8
    bad.append(records)
    records = copy.deepcopy(original)
    records[0]['ultracs']['position'] += 1
    bad.append(records)
    for index, payload in enumerate(bad):
        with pytest.raises(ValueError):
            load_input(save(work / f'bad-{index}.json', payload))
    for text in ('[{"field_id":"one","field_id":"two"}]', '[NaN]'):
        path = work / 'nonstandard.json'
        path.write_bytes(text.encode('utf-8'))
        with pytest.raises(ValueError):
            load_input(path)


def test_bundle_transaction_rolls_back_on_replacement_failure(work, monkeypatch):
    output, staging = work / 'out', work / 'stage'
    output.mkdir()
    staging.mkdir()
    for name in ('one', 'two'):
        (output / name).write_bytes(('old-' + name).encode())
        (staging / name).write_bytes(('new-' + name).encode())
    replace = Path.replace

    def fail_second(path, destination):
        if path == staging / 'two':
            raise OSError('injected replacement failure')
        return replace(path, destination)

    monkeypatch.setattr(Path, 'replace', fail_second)
    with pytest.raises(OSError, match='injected'):
        commit_outputs(staging, output, ('one', 'two'))
    assert (output / 'one').read_bytes() == b'old-one'
    assert (output / 'two').read_bytes() == b'old-two'
    assert not list(output.glob('.backup-*'))


def test_interrupted_rollback_retains_previous_bundle(work, monkeypatch):
    output, staging = work / 'out', work / 'stage'
    output.mkdir()
    staging.mkdir()
    for name in ('one', 'two'):
        (output / name).write_bytes(('old-' + name).encode())
        (staging / name).write_bytes(('new-' + name).encode())
    replace = Path.replace
    replacements = []

    def fail_and_block_restore(path, destination):
        replacements.append(path.name)
        if path.name == 'two' or replacements.count('one') > 1:
            raise OSError('injected interruption')
        return replace(path, destination)

    monkeypatch.setattr(Path, 'replace', fail_and_block_restore)
    with pytest.raises(OSError, match='previous files are retained'):
        commit_outputs(staging, output, ('one', 'two'))
    backup = next(output.glob('.backup-*'))
    assert (backup / 'one').read_bytes() == b'old-one'
    assert (backup / 'two').read_bytes() == b'old-two'


def test_html_failure_keeps_existing_destination(small_bundle, work, monkeypatch):
    target = work / 'viewer.html'
    target.write_bytes(b'previous completed HTML')
    replace = Path.replace

    def fail_html(path, destination):
        if Path(destination) == target.resolve():
            raise OSError('injected HTML replacement failure')
        return replace(path, destination)

    monkeypatch.setattr(Path, 'replace', fail_html)
    with pytest.raises(OSError, match='injected HTML'):
        build(small_bundle, target, verbose=False)
    assert target.read_bytes() == b'previous completed HTML'
    assert list(work.iterdir()) == [target]


def test_outputs_cannot_replace_input_files(small_bundle, drafts, work):
    path = work / 'asset_registry.csv'
    original = (EXAMPLES / 'sample-input.json').read_bytes()
    path.write_bytes(original)
    with pytest.raises(ValueError, match='input JSON'):
        generate_bundle(path, work)
    assert path.read_bytes() == original
    save(path, drafts)
    before = path.read_bytes()
    with pytest.raises(ValueError, match='drafts input'):
        apply_drafts(small_bundle, path, work)
    assert path.read_bytes() == before
    with pytest.raises(ValueError, match='separate bundle'):
        apply_drafts(small_bundle, path, small_bundle)
