"""Validate the explicit description-evidence-v1 assessment, not model certainty."""
from __future__ import annotations

import re
from datetime import datetime, timedelta

from lineage_poc.dictionary.io import ID_COLUMNS, equal, pointer, require, scoped
from lineage_poc.dictionary.legacy_projection import js
from lineage_poc.enrichment.contracts import (
    CRITERIA, MAX_DESCRIPTION_CHARACTERS, MAX_EVIDENCE_REFS, RUBRIC_ID,
)

REFERENCE_KEYS = {'file', 'input_sha256', 'graph_id', 'snapshot_id', 'row_id_column',
                  'row_id', 'column', 'json_pointer', 'value'}
ASSESSMENT_KEYS = {
    'assessment_scope', 'assessment_origin', 'rubric_id', 'verification_mode',
    'score_10', 'components', 'evidence_refs', 'calculation', 'rationale',
    'limitations', 'open_questions', 'assessed_by', 'model', 'assessed_at',
    'human_review_status', 'is_probability',
}


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def utc_time(value, label):
    require(nonempty(value), label + ' must be a UTC timestamp')
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError as error:
        raise ValueError(label + ' must be an ISO-8601 UTC timestamp') from error
    require(parsed.tzinfo is not None and parsed.utcoffset() == timedelta(0),
            label + ' must have an explicit UTC offset')
    return parsed


def validate_sentences(description):
    require(nonempty(description) and description == description.strip(),
            'Draft description must be nonempty text without surrounding whitespace')
    require(len(description) <= MAX_DESCRIPTION_CHARACTERS,
            'Draft description is not concise (maximum 1000 characters)')
    count = len(re.findall(r'[.!?]+(?=\s|$)', description))
    require(count in (1, 2) and description[-1] in '.!?',
            'Draft description must contain one or two complete sentences')
    return count


def _linked_evidence(tables, field):
    scope = field['graph_id'], field['snapshot_id']
    field_ids = {field['field_id']}
    mapping_ids = set()
    for row, values in zip(tables['data_dictionary.csv'].rows,
                           tables['data_dictionary.csv'].json_rows):
        if (row['graph_id'], row['snapshot_id']) != scope:
            continue
        catalog = values['field_catalog_json']
        if any(node['field_id'] == field['field_id'] for node in catalog):
            field_ids.update(node['field_id'] for node in catalog)
            mapping_ids.add(row['dictionary_entry_id'])
    asset_ids = {row['asset_id'] for row in tables['field_catalog.csv'].rows
                 if (row['graph_id'], row['snapshot_id']) == scope and row['field_id'] in field_ids}
    return {'field_catalog.csv': field_ids, 'data_dictionary.csv': mapping_ids,
            'asset_registry.csv': asset_ids}


def validate_reference(reference, *, tables=None, field=None, linked=None):
    require(isinstance(reference, dict) and set(reference) == REFERENCE_KEYS,
            'Evidence reference must contain the exact documented CSV reference keys')
    name = reference['file']
    require(isinstance(name, str) and name in ID_COLUMNS, 'Unsupported evidence file: ' + str(name))
    require(reference['row_id_column'] == ID_COLUMNS[name], 'Unsupported evidence row identity column')
    for key in ('graph_id', 'snapshot_id', 'row_id', 'column'):
        require(nonempty(reference[key]), 'Evidence ' + key + ' must be nonempty text')
    require(isinstance(reference['input_sha256'], str)
            and re.fullmatch('[0-9a-f]{64}', reference['input_sha256']) is not None,
            'Evidence requires an exact SHA256')
    require(reference['json_pointer'] is None or isinstance(reference['json_pointer'], str),
            'Evidence JSON pointer must be a string or null')
    if reference['json_pointer'] is not None:
        path = reference['json_pointer']
        require((not path or path.startswith('/')) and not re.search(r'~(?![01])', path),
                'Evidence contains an invalid JSON pointer')
    require(len(js(reference['value'])) <= 8192, 'Evidence value is too large; cite a bounded JSON pointer')
    require(not (reference['column'].startswith(('description_confidence', 'source_description_confidence'))
                 or reference['column'] in {'description_generation_status', 'source_description_generation_status'}
                 or 'description_provenance' in reference['column']),
            'Generated description assessments/provenance cannot be evidence for themselves')
    if field is not None:
        require((reference['graph_id'], reference['snapshot_id']) ==
                (field['graph_id'], field['snapshot_id']), 'Evidence belongs to a different graph/snapshot')
    if tables is None:
        return
    table = tables[name]
    require(reference['input_sha256'] == table.sha256, 'Stale evidence input hash for ' + name)
    identity = reference['graph_id'], reference['snapshot_id'], reference['row_id']
    require(identity in table.index(), 'Evidence row does not exist: ' + reference['row_id'])
    row, values = table.index()[identity]
    column = reference['column']
    require(column in table.headers, 'Unsupported evidence column: ' + column)
    if field is not None:
        linked = _linked_evidence(tables, field) if linked is None else linked
        require(reference['row_id'] in linked[name], 'Evidence is unrelated to this canonical field')
    path = reference['json_pointer']
    if path is None:
        require(column not in values, 'JSON evidence requires a JSON pointer (empty string means its root)')
        actual = row[column]
    else:
        require(column in values, 'Scalar evidence must use a null JSON pointer')
        actual = pointer(values[column], path)
    require(equal(actual, reference['value']), 'Evidence value does not match its exact input CSV cell/pointer')


def validate_assessment(assessment, *, tables=None, field=None):
    require(isinstance(assessment, dict) and not set(assessment) - ASSESSMENT_KEYS,
            'Unsupported description assessment object or scoring fields')
    for key, expected in {
        'assessment_scope': 'description_evidence',
        'assessment_origin': 'ai_self_assessment', 'rubric_id': RUBRIC_ID,
        'verification_mode': 'supplied_csv_only', 'human_review_status': 'not_reviewed',
    }.items():
        require(assessment.get(key) == expected, 'Unsupported description assessment ' + key)
    require(assessment.get('is_probability', False) is False,
            'Description evidence score is not a probability')
    require(nonempty(assessment.get('assessed_by')), 'Assessment must identify the active assistant')
    require(assessment.get('model') is None or nonempty(assessment['model']),
            'Assessment model must be the actual identifier or null')
    utc_time(assessment.get('assessed_at'), 'assessed_at')
    require(nonempty(assessment.get('rationale')), 'Assessment requires a field-specific rationale')
    require(isinstance(assessment.get('limitations'), list)
            and assessment['limitations'] and all(nonempty(item) for item in assessment['limitations']),
            'Assessment requires explicit supplied-evidence limitations')
    if 'open_questions' in assessment:
        require(isinstance(assessment['open_questions'], list)
                and all(nonempty(item) for item in assessment['open_questions']),
                'Assessment open_questions must be a text array')
    references = assessment.get('evidence_refs')
    require(isinstance(references, dict) and 0 < len(references) <= MAX_EVIDENCE_REFS,
            'Assessment requires a bounded evidence_refs object')
    linked = _linked_evidence(tables, field) if tables is not None and field is not None else None
    for identity, reference in references.items():
        require(nonempty(identity), 'Evidence reference IDs must be nonempty strings')
        validate_reference(reference, tables=tables, field=field, linked=linked)
    components = assessment.get('components')
    require(isinstance(components, list) and len(components) == len(CRITERIA),
            'Assessment must contain exactly the five description-evidence-v1 criteria')
    points = []
    used = set()
    for expected, component in zip(CRITERIA, components):
        require(isinstance(component, dict)
                and not set(component) - {'criterion', 'points', 'maximum', 'reason', 'evidence_refs', 'limitations'},
                'Unsupported assessment component')
        require(component.get('criterion') == expected,
                'Assessment criterion order/IDs must match description-evidence-v1')
        value = component.get('points')
        require(type(value) is int and value in (0, 1, 2), 'Criterion points must be integers in {0,1,2}')
        require(component.get('maximum', 2) == 2, 'Invented criterion weights are unsupported')
        require(nonempty(component.get('reason')), 'Every criterion requires a field-specific reason')
        refs = component.get('evidence_refs')
        require(isinstance(refs, list) and all(isinstance(ref, str) and ref in references for ref in refs)
                and len(refs) == len(set(refs)), 'Criterion references must identify documented evidence_refs')
        require(value == 0 or bool(refs), 'Every positive criterion award requires verifiable evidence')
        if 'limitations' in component:
            require(isinstance(component['limitations'], list)
                    and all(nonempty(item) for item in component['limitations']),
                    'Criterion limitations must be a text array')
        points.append(value)
        used.update(refs)
    require(used == set(references), 'Assessment contains unused evidence references')
    score = sum(points)
    require(type(assessment.get('score_10')) is int and assessment['score_10'] == score,
            'Description score arithmetic does not equal the five criterion points')
    calculation = ' + '.join(map(str, points)) + f' = {score} / 10'
    require(assessment.get('calculation') == calculation, 'Description calculation does not match rubric arithmetic')
    return score
