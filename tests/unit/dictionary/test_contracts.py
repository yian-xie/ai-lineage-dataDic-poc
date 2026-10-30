import copy
import json
from pathlib import Path

import pytest

from lineage_poc.dictionary.description_provenance import resolve_description
from lineage_poc.dictionary.generate import normalize_locator
from lineage_poc.dictionary.io import pointer
from lineage_poc.validation.descriptions import validate_assessment, validate_sentences

ROOT = Path(__file__).resolve().parents[3]
EXAMPLES = ROOT / '.github' / 'skills' / 'ai-description-enrichment' / 'references'


@pytest.mark.parametrize('text,record,key,attribute,value,subvalue,status', [
    (None, '', '', '', '', '', 'not_supplied'),
    ('', '', '', '', '', '', 'not_supplied'),
    ('AREC<19>', 'AREC', '', 19, '', '', 'parsed_record_attribute_reference'),
    ('AREC<19,2>', 'AREC', '', 19, 2, '', 'parsed_record_attribute_reference'),
    ('AREC<19,2,3>', 'AREC', '', 19, 2, 3, 'parsed_record_attribute_reference'),
    ('AREC @ID', 'AREC', '@ID', '', '', '', 'parsed_record_key_reference'),
    ('VALUE', '', '', '', '', '', 'not_normalized_complex_reference'),
    ('AREC<0>', '', '', '', '', '', 'not_normalized_complex_reference'),
    ('AREC<1> + BREC<2>', '', '', '', '', '', 'not_normalized_complex_reference'),
    (' AREC<1> ', '', '', '', '', '', 'not_normalized_complex_reference'),
])
def test_locator_normalization_does_not_guess_physical_binding(text, record, key, attribute, value, subvalue, status):
    assert normalize_locator(text) == {
        'record_reference': record, 'record_key_reference': key, 'attribute_position': attribute,
        'value_position': value, 'subvalue_position': subvalue, 'normalization_status': status,
    }


def provenance(column, description):
    return resolve_description(column, input_file='input.json', input_sha256='a' * 64,
                               input_pointer='/0/ultracs', description=description,
                               reported_source_path='reported-program.bas')


def test_description_origin_requires_an_exact_scoped_claim():
    result = provenance({'description': 'Existing exact text.', 'author': 'Someone'}, 'Existing exact text.')
    assert result['description_source_type'] == 'unknown'
    assert result['description_source_reference'] == 'input.json#/0/ultracs/description'
    assert result['description_provenance_json']['reported_context_source_reference'] == 'reported-program.bas'
    assert result['description_provenance_json']['reported_context_source_reference_basis'].endswith('not_description_origin')
    assert provenance({'description': ''}, '')['description_source_type'] == 'not_supplied'
    assert provenance({'description': 'Exact.', 'description_origin': 'human_authored'}, 'Exact.')['description_source_type'] == 'existing_metadata'
    assert provenance({'description': 'Exact.', 'description_provenance': {'origin': 'llm_generated'}}, 'Exact.')['description_source_type'] == 'ai_generated'


def test_conflicting_description_claims_are_retained_without_a_winner():
    column = {'description': 'Exact.', 'description_origin': 'repository',
              'description_provenance': {'origin': 'ai_generated'}}
    original = copy.deepcopy(column)
    result = provenance(column, column['description'])
    assert result['description_source_type'] == 'unknown'
    assert result['description_provenance_json']['conflicts'][0]['kind'] == 'description_origin_conflict'
    assert column == original


@pytest.mark.parametrize('text,count', [('One sentence.', 1), ('First. Second.', 2),
                                       ('The value 1.25 is reported. Binding is unresolved.', 2)])
def test_description_sentence_bounds(text, count):
    assert validate_sentences(text) == count


@pytest.mark.parametrize('text', ['', 'Incomplete', 'First. Second. Third.', ' Leading space.',
                                 'Trailing space. ', 'X' * 1001 + '.'])
def test_description_sentence_rejections(text):
    with pytest.raises(ValueError):
        validate_sentences(text)


def test_archived_assessment_uses_exact_rubric_and_recalculated_sum():
    payload = json.loads((EXAMPLES / 'drafts.example.json').read_bytes())
    assessment = payload['results'][0]['assessment']
    assert validate_assessment(assessment) == sum(component['points'] for component in assessment['components'])
    assert assessment['rubric_id'] == 'description-evidence-v1'
    assert assessment['verification_mode'] == 'supplied_csv_only'


def test_json_pointer_preserves_null_empty_and_container_distinctions():
    value = {'a/b': {'~': [None, '', {}, []]}, 'numeric': {'0': False}}
    assert pointer(value, '/a~1b/~0/0') is None
    assert pointer(value, '/a~1b/~0/1') == ''
    assert pointer(value, '/a~1b/~0/2') == {}
    assert pointer(value, '/a~1b/~0/3') == []
    assert pointer(value, '/numeric/0') is False
    for path in ('not-a-pointer', '/a~2b', '/a~1b/~0/01', '/absent'):
        with pytest.raises(ValueError):
            pointer(value, path)
