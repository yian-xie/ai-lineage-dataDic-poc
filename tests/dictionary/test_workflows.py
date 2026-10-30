import copy
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from lineage_poc.dictionary.io import CSV_FILES, digest_file, equal, read_tables
from lineage_poc.dictionary.workflow import generate_bundle
from lineage_poc.enrichment.contracts import ENRICHMENT_COLUMNS, eligible
from lineage_poc.enrichment.workflow import apply_drafts, prepare_context, record_drafts
from lineage_poc.paths import INPUT_ROOT
from lineage_poc.validation.bundle import DESCRIPTION_SURFACES, validate_bundle
from lineage_poc.validation.descriptions import validate_reference
from lineage_poc.viewers.dictionary.build_viewer import build

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / '.github' / 'skills' / 'ai-description-enrichment' / 'references'


def save_drafts(path, payload):
    path.write_bytes(json.dumps(payload, ensure_ascii=False).encode('utf-8'))
    return path


def test_full_generation_is_csv_only_and_byte_exact(reference, work):
    input_path = INPUT_ROOT / 'column_lineage.json'
    before = digest_file(input_path)
    summary = generate_bundle(input_path, work / 'csv')
    assert [summary[key] for key in ('assets', 'fields', 'dictionary_rows')] == [7, 464, 179]
    assert {path.name for path in (work / 'csv').iterdir()} == set(CSV_FILES)
    for name in CSV_FILES:
        assert (work / 'csv' / name).read_bytes() == (reference / 'baseline' / name).read_bytes()
    assert digest_file(input_path) == before
    assert summary['validation']['bundle_directory'] == str((work / 'csv').resolve())
    assert summary['validation']['operations'] == 369
    json.dumps(summary)


def test_full_saved_bundles_validate_without_rewriting(reference):
    before = {str(path): digest_file(path) for directory in ('baseline', 'ai-enriched')
              for path in (reference / directory).glob('*.csv')}
    baseline = validate_bundle(reference / 'baseline')
    enriched = validate_bundle(reference / 'ai-enriched', reference / 'baseline')
    assert baseline['counts'] == {'asset_registry': 7, 'field_catalog': 464, 'data_dictionary': 179}
    assert [value['columns'] for value in baseline['outputs'].values()] == [25, 47, 106]
    assert [value['columns'] for value in enriched['outputs'].values()] == [25, 52, 111]
    assert enriched['description_drafts'] == enriched['description_assessments_resolved'] == 87
    assert enriched['changed_eligible_descriptions'] == 87
    assert enriched['maximum_cell_characters']['data_dictionary.csv'] <= 32767
    assert not enriched['browser_import_verified']
    assert before == {path: digest_file(Path(path)) for path in before}


def test_record_assistant_drafts_preserves_exact_bytes_without_applying(small_bundle, drafts, work):
    before = {name: digest_file(small_bundle / name) for name in CSV_FILES}
    pending = save_drafts(work / 'assistant-drafts.json', drafts)
    original = pending.read_bytes()
    result = record_drafts(small_bundle, pending, work / 'recorded')
    assert result['status'] == 'passed' and result['drafts_recorded'] == 1
    assert result['external_AI_invoked'] is False
    assert (work / 'recorded' / 'drafts.json').read_bytes() == original
    assert pending.read_bytes() == original
    assert set(path.name for path in (work / 'recorded').iterdir()) == {'drafts.json'}
    assert before == {name: digest_file(small_bundle / name) for name in CSV_FILES}


def test_record_rejects_stale_assistant_drafts_before_delivery(small_bundle, drafts, work):
    drafts['input_hashes']['field_catalog.csv'] = '0' * 64
    pending = save_drafts(work / 'assistant-drafts.json', drafts)
    with pytest.raises(ValueError, match='Stale input hashes'):
        record_drafts(small_bundle, pending, work / 'recorded')
    assert not (work / 'recorded' / 'drafts.json').exists()


def test_record_keeps_protected_descriptions_and_rejects_in_place_drafts(small_bundle, drafts, work):
    pending = save_drafts(work / 'assistant-drafts.json', drafts)
    record_drafts(small_bundle, pending, work / 'recorded')
    accepted = work / 'recorded' / 'drafts.json'
    with pytest.raises(ValueError, match='separate pending draft'):
        record_drafts(small_bundle, accepted, accepted.parent)
    protected = next(row for row in read_tables(small_bundle)['field_catalog.csv'].rows
                     if row['source_system'] == 'Snowflake' and row['description'])
    drafts['results'][0]['field_id'] = protected['field_id']
    save_drafts(pending, drafts)
    with pytest.raises(ValueError, match='Protected or out-of-scope'):
        record_drafts(small_bundle, pending, work / 'protected-rejected')
    assert not (work / 'protected-rejected' / 'drafts.json').exists()


def test_prepare_context_binds_hashes_and_excludes_protected(reference, work):
    result = prepare_context(reference / 'baseline', work / 'context')
    assert result['status'] == 'awaiting_assistant_drafts'
    assert result['eligible_fields'] == 87
    assert result['protected_ultracs_descriptions'] == 8
    assert {path.name for path in (work / 'context').iterdir()} == {'context.json'}
    context = json.loads(Path(result['context_file']).read_bytes())
    tables = read_tables(reference / 'baseline')
    assert context['input_hashes'] == {name: table.sha256 for name, table in tables.items()}
    eligible_ids = {tuple(item[key] for key in ('graph_id', 'snapshot_id', 'field_id'))
                    for item in context['eligible_ids']}
    assert len(eligible_ids) == 87
    assert not eligible_ids & {tuple(item[key] for key in ('graph_id', 'snapshot_id', 'field_id'))
                              for item in context['protected_ids']}
    for field in context['fields']:
        assert 'description' not in field
        assert len(field['evidence_refs']) <= context['bounds']['maximum_references_per_field']
        canonical = tables['field_catalog.csv'].index()[(field['graph_id'], field['snapshot_id'], field['field_id'])][0]
        for reference_object in field['evidence_refs'].values():
            validate_reference(reference_object, tables=tables, field=canonical)
            assert len(json.dumps(reference_object['value'], ensure_ascii=False, sort_keys=True,
                                  separators=(',', ':'))) <= 2048
    json.dumps(result)


def test_full_archived_drafts_round_trip_every_saved_value(reference, work):
    saved = read_tables(reference / 'ai-enriched')
    inputs = read_tables(reference / 'baseline')
    rows = [(row, values) for row, values in zip(saved['field_catalog.csv'].rows,
                                                saved['field_catalog.csv'].json_rows)
            if row.get('description_generation_status') == 'draft']
    provenance = rows[0][1]['description_provenance_json']
    payload = {
        'schema_version': 'description-drafts-v1', 'rubric_id': 'description-evidence-v1',
        'input_hashes': {name: table.sha256 for name, table in inputs.items()},
        'run_id': provenance['enrichment_run_id'], 'generator': provenance['generator'],
        'model': provenance['model'], 'generated_at': provenance['generated_at'],
        'results': [{
            'graph_id': row['graph_id'], 'snapshot_id': row['snapshot_id'], 'field_id': row['field_id'],
            'status': 'draft', 'description': row['description'],
            'assessment': values['description_confidence_json'],
        } for row, values in rows],
    }
    result = apply_drafts(reference / 'baseline', save_drafts(work / 'drafts.json', payload), work / 'applied')
    assert result['drafts_applied'] == 87
    assert result['protected_ultracs_descriptions'] == 8
    assert result['validation']['description_assessments_resolved'] == 87
    actual = read_tables(work / 'applied')
    for name in CSV_FILES:
        assert actual[name].headers == saved[name].headers
        assert len(actual[name].rows) == len(saved[name].rows)
        for row, values, expected, expected_values in zip(
            actual[name].rows, actual[name].json_rows, saved[name].rows, saved[name].json_rows,
        ):
            for column in actual[name].headers:
                if column in values:
                    assert equal(values[column], expected_values[column]), (name, column)
                else:
                    assert row[column] == expected[column], (name, column)
    assert (work / 'applied' / 'asset_registry.csv').read_bytes() == (reference / 'baseline' / 'asset_registry.csv').read_bytes()
    assert {path.name for path in (work / 'applied').iterdir()} == set(CSV_FILES)
    json.dumps(result)


def test_applying_changes_only_eligible_description_surfaces(small_bundle, drafts, work):
    before = read_tables(small_bundle)
    hashes = {name: table.sha256 for name, table in before.items()}
    result = apply_drafts(small_bundle, save_drafts(work / 'drafts.json', drafts), work / 'enriched')
    after = read_tables(work / 'enriched')
    assert result['drafts_applied'] == 1
    assert {name: digest_file(small_bundle / name) for name in CSV_FILES} == hashes
    allowed_field = set(DESCRIPTION_SURFACES + ['original_field_json'])
    changed = None
    for row, old in zip(after['field_catalog.csv'].rows, before['field_catalog.csv'].rows):
        for column in before['field_catalog.csv'].headers:
            if not eligible(old) or column not in allowed_field:
                assert row[column] == old[column]
        if eligible(old):
            changed = row['field_id']
        else:
            for column in ENRICHMENT_COLUMNS:
                assert row[column] == ('null' if column.endswith('_json') else '')
    assert changed is not None
    allowed_mapping = {'source_description', 'source_description_origin', 'field_catalog_json',
                       'description_details_json', 'input_property_map_json'}
    allowed_mapping.update('source_' + column for column in DESCRIPTION_SURFACES if column != 'description')
    for row, old in zip(after['data_dictionary.csv'].rows, before['data_dictionary.csv'].rows):
        for column in before['data_dictionary.csv'].headers:
            if column not in allowed_mapping:
                assert row[column] == old[column]
    assert (small_bundle / 'asset_registry.csv').read_bytes() == (work / 'enriched' / 'asset_registry.csv').read_bytes()
    assert validate_bundle(work / 'enriched', small_bundle)['changed_eligible_descriptions'] == 1


def test_needs_evidence_does_not_fabricate_or_relabel(small_bundle, needs_drafts, work):
    result = apply_drafts(small_bundle, save_drafts(work / 'needs.json', needs_drafts), work / 'needs')
    assert result['drafts_applied'] == 0 and result['needs_evidence'] == 1
    old, new = read_tables(small_bundle), read_tables(work / 'needs')
    for name in CSV_FILES:
        for before, after in zip(old[name].rows, new[name].rows):
            assert all(after[column] == before[column] for column in old[name].headers)
    source = next(row for row in new['field_catalog.csv'].rows if row['source_system'] == 'Ultracs')
    assert source['description_generation_status'] == 'needs_evidence'
    assert source['description_confidence_json'] == 'null'
    assert source['description_confidence_score_10'] == ''
    assert needs_drafts['results'][0]['open_questions'][0] in source['description_confidence_rationale']
    context = prepare_context(work / 'needs', work / 'context')
    assert context['eligible_fields'] == 1


def test_existing_ai_drafts_are_protected_and_round_trip(small_bundle, drafts, work):
    apply_drafts(small_bundle, save_drafts(work / 'drafts.json', drafts), work / 'first')
    context = prepare_context(work / 'first', work / 'context')
    assert context['status'] == 'no_eligible_fields' and context['eligible_fields'] == 0
    assert context['protected_ultracs_descriptions'] == 1
    payload = copy.deepcopy(drafts)
    payload['input_hashes'] = {name: digest_file(work / 'first' / name) for name in CSV_FILES}
    payload['results'] = []
    result = apply_drafts(work / 'first', save_drafts(work / 'empty.json', payload), work / 'second')
    assert result['drafts_applied'] == result['needs_evidence'] == 0
    for name in CSV_FILES:
        assert (work / 'first' / name).read_bytes() == (work / 'second' / name).read_bytes()
    forbidden = copy.deepcopy(drafts)
    forbidden['input_hashes'] = payload['input_hashes']
    with pytest.raises(ValueError, match='Protected'):
        apply_drafts(work / 'first', save_drafts(work / 'forbidden.json', forbidden), work / 'forbidden')


def test_html_build_is_explicit_atomic_and_deterministic(small_bundle, work):
    before = {name: digest_file(small_bundle / name) for name in CSV_FILES}
    target = work / 'chosen' / 'index.html'
    assert build(small_bundle, target, verbose=False) == target.resolve()
    contents = target.read_bytes()
    assert contents.startswith(b'<!DOCTYPE html>') or contents.startswith(b'<!doctype html>')
    assert build(small_bundle, target, verbose=False).read_bytes() == contents
    assert not (work / 'index.html').exists()
    assert not (small_bundle / 'index.html').exists()
    assert {name: digest_file(small_bundle / name) for name in CSV_FILES} == before
    assert [path.name for path in target.parent.iterdir()] == ['index.html']
    assert b'@@V3_' not in contents
    validation = validate_bundle(small_bundle)
    build(small_bundle, target, manifest={'outputs': validation['outputs']}, verbose=False)
    bad_manifest = copy.deepcopy(validation['outputs'])
    bad_manifest['field_catalog.csv']['sha256'] = '0' * 64
    original = target.read_bytes()
    with pytest.raises(ValueError, match='Manifest'):
        build(small_bundle, target, manifest={'outputs': bad_manifest}, verbose=False)
    assert target.read_bytes() == original
    with pytest.raises(ValueError, match='input CSV'):
        build(small_bundle, small_bundle / 'asset_registry.csv', verbose=False)


def test_module_interfaces_without_path_hacks(small_bundle, work):
    commands = [
        [sys.executable, '-m', 'lineage_poc.dictionary.generate', '--input',
         str(EXAMPLES / 'sample-input.json'), '--output', str(work / 'csv')],
        [sys.executable, '-m', 'lineage_poc.enrichment.workflow', 'prepare', '--input',
         str(small_bundle), '--output', str(work / 'context')],
        [sys.executable, '-m', 'lineage_poc.validation.bundle', '--input', str(small_bundle)],
        [sys.executable, '-m', 'lineage_poc.viewers.dictionary.build_viewer', '--output-dir',
         str(small_bundle), '--destination', str(work / 'viewer.html')],
    ]
    for command in commands:
        completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=True)
        output = json.loads(completed.stdout)
        assert output.get('status') in {None, 'passed', 'awaiting_assistant_drafts'}
    assert (work / 'viewer.html').is_file()


@pytest.mark.browser
def test_actual_javascript_importer_on_reference_bundles(reference):
    node = shutil.which('node')
    if node is None:
        pytest.skip('Node is unavailable; actual browser importer still requires browser verification')
    assets = ROOT / 'src' / 'lineage_poc' / 'viewers' / 'dictionary' / 'assets'
    javascript = r"""
const fs=require('fs'),vm=require('vm'),path=require('path');
const sandbox={window:{}};vm.createContext(sandbox);
for(const name of ['viewer_core.js','bundle_core.js']){
  vm.runInContext(fs.readFileSync(path.join(process.argv[1],name),'utf8'),sandbox);
}
for(const directory of process.argv.slice(2)){
  const files={};for(const name of ['asset_registry.csv','field_catalog.csv','data_dictionary.csv']){
    files[name]=fs.readFileSync(path.join(directory,name),'utf8');
  }
  const bundle=sandbox.window.V3Bundle.prepareBundle(files,{});
  console.log(JSON.stringify({assets:bundle.assets.rows.length,fields:bundle.fields.rows.length,
    mappings:bundle.dictionary.rows.length,operations:bundle.operationCount}));
}
"""
    completed = subprocess.run([node, '-e', javascript, str(assets), str(reference / 'baseline'),
                                str(reference / 'ai-enriched')], cwd=ROOT,
                               capture_output=True, text=True, check=True)
    assert [json.loads(line) for line in completed.stdout.splitlines()] == [
        {'assets': 7, 'fields': 464, 'mappings': 179, 'operations': 369},
        {'assets': 7, 'fields': 464, 'mappings': 179, 'operations': 369},
    ]
