"""The supported description-only enrichment contract."""
from urllib.parse import urlencode

RUBRIC_ID = 'description-evidence-v1'
CONTEXT_VERSION = 'description-context-v1'
DRAFTS_VERSION = 'description-drafts-v1'
CRITERIA = ('identity_grounding', 'meaning_support', 'transformation_support',
            'corroboration', 'uncertainty_handling')
ENRICHMENT_COLUMNS = [
    'description_generation_status', 'description_confidence_score_10',
    'description_confidence_method', 'description_confidence_rationale',
    'description_confidence_json',
]
MAX_EVIDENCE_REFS = 48
MAX_DESCRIPTION_CHARACTERS = 1000


def eligible(row):
    return (row['source_system'] == 'Ultracs' and row['layer'] == 'source'
            and not row['description'].strip())


def description_reference(row, column='description'):
    return 'field_catalog.csv#' + urlencode({
        'graph_id': row['graph_id'], 'snapshot_id': row['snapshot_id'],
        'field_id': row['field_id'], 'column': column,
    })
