"""Deterministic column-description provenance; no authorship or AI inference.

Only a scoped, explicit description origin/type claim can establish AI-generated
or existing metadata. A description supplied in JSON is not thereby confirmed to
come from an existing repository or from AI. Claims are reported, not verified.
"""
from __future__ import annotations

import copy
import json

DESCRIPTION_COLUMNS = [
    'description_source_type', 'description_author', 'description_generator',
    'description_source_reference', 'description_source_pointer', 'description_provenance_json',
]
ORIGIN_TYPES = {
    'ai_generated': 'ai_generated', 'ai': 'ai_generated',
    'llm_generated': 'ai_generated', 'model_generated': 'ai_generated',
    'existing_metadata': 'existing_metadata', 'existing': 'existing_metadata',
    'repository': 'existing_metadata', 'documentation': 'existing_metadata',
    'human_authored': 'existing_metadata',
}
CLAIM_KEYS = [
    'description_origin', 'description_provenance', 'description_source_type',
    'description_author', 'description_generated_by', 'description_source_reference',
]


def normalize_origin(value):
    if not isinstance(value, str):
        return 'unknown'
    normalized = value.strip().lower().replace('-', '_').replace(' ', '_')
    return ORIGIN_TYPES.get(normalized, 'unknown')


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def resolve_description(column, *, input_file, input_sha256, input_pointer,
                        description=None, reported_source_path=None):
    """Return the six scalar/JSON projection columns for one exact source object.

    ``description`` is the exact canonical field text. Supplying it explicitly
    prevents inheriting another field's description via asset/route metadata.
    ``column`` contains only that column's own optional provenance claims.
    """
    column = column if isinstance(column, dict) else {}
    scoped = column.get('description_provenance')
    scoped = scoped if isinstance(scoped, dict) else {}
    claims = {key: copy.deepcopy(column[key]) for key in CLAIM_KEYS if key in column}
    origin_claims = []
    for key in ['description_origin', 'description_source_type']:
        if key in column:
            origin_claims.append({'input_property': key, 'value': copy.deepcopy(column[key]),
                                  'normalized_source_type': normalize_origin(column[key])})
    if 'origin' in scoped:
        origin_claims.append({'input_property': 'description_provenance.origin',
                              'value': copy.deepcopy(scoped['origin']),
                              'normalized_source_type': normalize_origin(scoped['origin'])})
    explicit_types = {claim['normalized_source_type'] for claim in origin_claims
                      if claim['normalized_source_type'] in {'ai_generated', 'existing_metadata'}}
    conflicts = []
    if len(explicit_types) > 1:
        conflicts.append({'kind': 'description_origin_conflict',
                          'reason': 'Scoped explicit claims disagree between AI-generated and existing metadata.',
                          'claimed_source_types': sorted(explicit_types)})
    present = isinstance(description, str) and bool(description.strip())
    if not present:
        source_type, basis = 'not_supplied', 'No non-empty description is supplied for this exact field.'
    elif len(explicit_types) == 1:
        source_type = next(iter(explicit_types))
        basis = 'Reported explicit column-scoped description origin/type claim; not independently verified.'
    elif len(explicit_types) > 1:
        source_type, basis = 'unknown', 'Conflicting explicit description origin/type claims; no source type was chosen.'
    else:
        source_type, basis = 'unknown', 'Description text is supplied, but its authorship/source type is not established by an explicit recognized origin/type claim.'

    def resolve_alias(alias, nested, label):
        candidates = []
        if alias in column:
            candidates.append({'input_property': alias, 'value': copy.deepcopy(column[alias])})
        if nested in scoped:
            candidates.append({'input_property': 'description_provenance.' + nested,
                               'value': copy.deepcopy(scoped[nested])})
        nonempty = [candidate for candidate in candidates if candidate['value'] not in (None, '')]
        unique = {canonical(candidate['value']) for candidate in nonempty}
        if len(unique) == 1:
            return copy.deepcopy(nonempty[0]['value'])
        if len(unique) > 1:
            conflicts.append({'kind': label + '_conflict', 'claims': candidates,
                              'reason': 'Conflicting explicit values are retained; no single value was chosen.'})
        return ''

    author = resolve_alias('description_author', 'author', 'description_author')
    generator = resolve_alias('description_generated_by', 'generated_by', 'description_generator')
    reference = resolve_alias('description_source_reference', 'source_reference', 'description_source_reference')
    pointer = input_pointer + '/description' if 'description' in column else ''
    reference_basis = 'reported_explicit_description_reference' if reference != '' else 'immediate_input_json_description_value'
    # The imported JSON is the immediate source of the supplied text. A parent
    # BASIC/YAML/source_path supports mapping context, not description authorship.
    # Keep that path separately as context-only metadata, never as the default
    # description-specific source reference.
    if reference == '':
        reference = input_file + '#' + pointer if pointer else input_file
        if not pointer:
            reference_basis = 'immediate_input_json_context_no_description_property'
    provenance = {
        'source_type': source_type, 'classification_basis': basis,
        'input_file': input_file, 'input_sha256': input_sha256,
        'input_pointer': input_pointer, 'description_pointer': pointer,
        'description_present': present, 'description_property_present': 'description' in column,
        'reported_context_source_reference': reported_source_path or None,
        'reported_context_source_reference_basis': 'reported_parent_source_path_context_only_not_description_origin',
        'source_reference': copy.deepcopy(reference), 'source_reference_basis': reference_basis,
        'author': copy.deepcopy(author), 'generator': copy.deepcopy(generator),
        'origin_claims': origin_claims, 'input_claims': claims, 'conflicts': conflicts,
        'verification_mode': 'reported_json_only',
    }
    return {
        'description_source_type': source_type, 'description_author': author,
        'description_generator': generator, 'description_source_reference': reference,
        'description_source_pointer': pointer, 'description_provenance_json': provenance,
    }
