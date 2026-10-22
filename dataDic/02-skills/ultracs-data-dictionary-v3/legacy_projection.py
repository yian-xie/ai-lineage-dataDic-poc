#!/usr/bin/env python3
"""Project the supplied mapping inventory into the agreed single-CSV contract.

Uses recorded JSON claims only. Does not execute expressions, consult a model,
read repositories or assign numeric confidence. Original JSON is retained intact.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

COLUMNS = Path(__file__).resolve().parent / 'assets' / 'mapping_columns.json'


def js(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def uid(kind, *parts):
    return kind + ':' + hashlib.sha256(js(parts).encode()).hexdigest()[:24]


def ptr_token(value):
    return str(value).replace('~', '~0').replace('/', '~1')


def walk(value, pointer=''):
    yield pointer, value
    if isinstance(value, dict):
        for key, child in value.items():
            yield from walk(child, pointer + '/' + ptr_token(key))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from walk(child, pointer + '/' + str(index))


def jtype(value):
    if value is None: return 'null'
    if isinstance(value, bool): return 'boolean'
    if isinstance(value, dict): return 'object'
    if isinstance(value, list): return 'array'
    if isinstance(value, str): return 'string'
    return 'number'


def unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError('Duplicate JSON object key cannot be silently normalized: ' + key)
        value[key] = item
    return value


def reject_nonfinite(token):
    raise ValueError('Nonstandard JSON number cannot be silently normalized: ' + token)


def basic_operation_type(expression, summary, references):
    """Classify only syntax/operations actually supplied, not the variable name."""
    text = expression.strip()
    if text in references:
        return 'direct'
    if re.match(r'^\s*If\b', summary, re.I) and re.search(r'\botherwise\b', summary, re.I):
        return 'conditional'
    # Ignore record-slice delimiters and quoted formatting literals when looking
    # for arithmetic. OCONV can contain an arithmetic operand as well as format conversion.
    unquoted = re.sub(r"'[^']*'|\"[^\"]*\"", '', text)
    if re.search(r'[+*/-]', unquoted):
        return 'calculation'
    if re.match(r'^OCONV\(', text, re.I):
        return 'cast'
    if re.search(r'\bFIELD\s*\(|\bLEN\s*\(|transaction adjustments', summary, re.I):
        return 'calculation'
    # A bare precomputed variable says nothing about how it was produced.
    return 'unknown'


def cell(value):
    if isinstance(value, (dict, list)): return js(value)
    if value is None: return ''
    if isinstance(value, bool): return str(value).lower()
    return str(value)


def project(input_path):
    """Return the original 81-column projection without writing any files."""
    from types import SimpleNamespace
    args = SimpleNamespace(input=Path(input_path))
    blob = args.input.read_bytes()
    digest = hashlib.sha256(blob).hexdigest()
    records = json.loads(blob, object_pairs_hook=unique_object, parse_constant=reject_nonfinite)
    assert isinstance(records, list) and records
    assert len({r['field_id'] for r in records}) == len(records), 'Duplicate original mapping identities'
    snapshot = 'sha256:' + digest
    headers = json.loads(COLUMNS.read_text(encoding='utf-8'))
    assert headers and len(headers) == len(set(headers))
    nodes, ops, sources, target_index = {}, {}, {}, defaultdict(list)
    rows, build_issues = [], []

    def ref(pointer, role='mapping', **claims):
        return {'input_file': args.input.name, 'input_sha256': digest, 'input_pointer': pointer,
                'evidence_role': role, 'verification_mode': 'reported_json_only', **claims}

    def node(fid, system, stage, obj, name, kind, **metadata):
        data = {'field_id': fid, 'system': system, 'stage': stage, 'object': obj,
                'field_name': name, 'field_kind': kind, **metadata}
        if fid in nodes:
            assert nodes[fid] == data, ('Conflicting field identity', fid)
        else:
            nodes[fid] = data
        return fid

    def operation(kind, context, inputs, outputs, expr, typ, status, evidence, group,
                  mapping_id, granularity, route=None, reviews=None, dependency_role='value'):
        rid = uid('operation', snapshot, kind, context, inputs, outputs, expr)
        data = {
            'relationship_id': rid, 'snapshot_id': snapshot,
            'dictionary_entry_ids': [], 'source_entry_ids': [group],
            'source_field_ids': inputs, 'target_field_ids': outputs,
            'process_name': kind + ': ' + context,
            'operation_type': typ, 'dependency_role': dependency_role,
            'input_roles_json': {fid: [dependency_role] for fid in inputs}, 'expression': expr,
            'output_expressions_json': {fid: expr for fid in outputs},
            'output_input_bindings_json': {fid: [{'field_id': src, 'roles': [dependency_role]}
                                                   for src in inputs] for fid in outputs},
            'status': status, 'granularity': granularity,
            'original_assessments_json': [{'label': context_record[mapping_id]['confidence'],
                                          'scope': 'mapping_record', 'mapping_id': mapping_id,
                                          'input_pointer': context_pointer[mapping_id] + '/confidence'}],
            'confidence_score_10': None, 'confidence_state': 'unscored',
            'confidence_method': None, 'confidence_rationale': None,
            'confidence_assessment_json': None,
            'evidence_json': evidence, 'source_mapping_ids': [mapping_id],
            'source_refs_json': evidence, 'route_context_json': route or {},
            'needs_review': bool(reviews), 'review_notes_json': reviews or [],
        }
        if rid in ops:
            assert ops[rid] == data, ('Conflicting operation', rid)
        else:
            ops[rid] = data
        return rid

    context_record = {r['field_id']: r for r in records}
    context_pointer = {r['field_id']: '/' + str(i) for i, r in enumerate(records)}
    for i, r in enumerate(records):
        p = '/' + str(i)
        u, h, route = r['ultracs'], r['hvr_parameter'], r['ingestion_route']
        group = uid('source-entry', snapshot, r['field_id'])
        raw_key = re.fullmatch(r'DATA:([A-Za-z_][A-Za-z0-9_]*)', route['dbt_input'], re.I)
        assert raw_key, ('Unsupported declared logical RAW key', r['field_id'])
        key = raw_key.group(1)
        source_resolved = bool(u.get('source_locator') and len(u.get('source_references', [])) == 1
                               and re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*<\d+(?:,\d+)*>', u['source_locator'])
                               and re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*<\d+(?:,\d+)*>', u['source_references'][0]))
        direct_claim = re.match(r'\s*Direct output from\s+([A-Za-z_][A-Za-z0-9_]*<\d+(?:,\d+)*>)',
                                u['transformation'], re.I)
        source_conflict = bool(direct_claim and direct_claim.group(1) != u['basic_expression'].strip())
        # Different BASIC record variables are not proven aliases merely
        # because their locators share syntactically valid positions.
        locator_variable = (u.get('source_locator') or '').split('<', 1)[0]
        basic_variable = u['source_references'][0].split('<', 1)[0] if source_resolved else ''
        unconfirmed_record_binding = bool(source_resolved and not source_conflict
                                         and locator_variable != basic_variable)
        source_resolved = source_resolved and not source_conflict and not unconfirmed_record_binding
        source_id = uid('source-field', snapshot, r['field_id'], u.get('source_locator'), u['basic_expression'])
        node(source_id, 'Ultracs', 'source', u['program'],
             u.get('source_locator') or u['basic_expression'],
             'source_locator' if source_resolved else 'expression_ref',
             identity_resolution_status='reported_locator' if source_resolved else 'unresolved',
             locator=u.get('source_locator'), source_references=u.get('source_references', []),
             description=u.get('description'), description_origin='recorded_input',
             data_type=None, classification=None, business_definition=None,
             metadata={'original_mapping_id': r['field_id'], 'basic_expression': u['basic_expression'],
                       'physical_binding_basis': 'declared locator/reference association in input' if source_resolved
                                                 else 'Record-variable alias binding is not supplied' if unconfirmed_record_binding
                                                 else 'Incomplete locator/reference or operand binding',
                       'verification_mode': 'reported_json_only'},
             source_refs_json=[ref(p + '/ultracs')])
        extract_id = uid('extract-field', snapshot, u['program'], r['extract_file'], r['ultracs_position'])
        node(extract_id, 'HVR extract', 'extract', r['extract_file'], r['param_column'], 'extract_slot',
             identity_resolution_status='reported', locator={'position': r['ultracs_position']},
             description=h.get('description'), data_type=h['type'], classification=None,
             metadata={'parameter': h, 'parameter_source_path': r['source_path']},
             source_refs_json=[ref(p + '/hvr_parameter'), ref(p + '/ultracs_position')])
        raw_id = uid('raw-field', snapshot, route['raw_relation'], 'DATA', key)
        node(raw_id, 'Snowflake', 'raw', route['raw_relation'], 'DATA:' + key, 'json_path',
             identity_resolution_status='reported_logical_path', locator=None, description=None,
             data_type=None, classification=None, metadata={'is_physical_column': False},
             source_refs_json=[ref(p + '/ingestion_route')])
        missing_source = []
        if not source_resolved:
            missing_source = [{'code': 'UNRESOLVED_SOURCE_BINDING', 'affected_field_id': source_id,
                               'reason': 'A complete physical locator/reference/operand binding is not supplied.',
                               'source_reference': p + '/ultracs'}]
        if unconfirmed_record_binding:
            missing_source.append({'code': 'UNCONFIRMED_RECORD_VARIABLE_BINDING', 'affected_field_id': source_id,
                                   'reason': 'The reported source locator uses ' + locator_variable
                                             + ', while its concrete BASIC reference uses ' + basic_variable
                                             + '. Their record-variable alias binding is not supplied; retain both claims without treating the source as resolved.',
                                   'source_reference': p + '/ultracs',
                                   'unconfirmed_input_pointers': [p + '/ultracs/source_locator',
                                                                  p + '/ultracs/source_references'],
                                   'reported_source_locator': u['source_locator'],
                                   'reported_basic_references': u['source_references']})
        if source_conflict:
            missing_source.append({'code': 'CONFLICTING_BASIC_REFERENCE', 'affected_field_id': source_id,
                                   'reason': 'BASIC expression/source_references identify ' + u['basic_expression']
                                             + ', but the supplied transformation summary claims ' + direct_claim.group(1)
                                             + '. Preserve both; do not choose a source silently.',
                                   'source_reference': p + '/ultracs',
                                   'conflicting_input_pointers': [p + '/ultracs/basic_expression',
                                                                p + '/ultracs/source_references', p + '/ultracs/transformation']})
        basic_op = operation('BASIC extraction', r['field_id'], [source_id], [extract_id],
                             u['basic_expression'], basic_operation_type(u['basic_expression'], u['transformation'], u.get('source_references', [])),
                             'evidence_supported' if source_resolved else 'unresolved',
                             [ref(p + '/ultracs', reported_path=u['source_path'],
                                  reported_line=u['basic_source_line'],
                                  expression=u['basic_expression'], transformation=u['transformation'],
                                  classification_basis='reported_transformation_summary' if
                                      re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', u['basic_expression'])
                                      and basic_operation_type(u['basic_expression'], u['transformation'], u.get('source_references', [])) != 'unknown'
                                      else 'reported_expression_syntax_or_unknown')],
                             group, r['field_id'], 'reported-source-to-extract' if source_resolved
                             else 'symbolic-expression-to-extract', reviews=missing_source,
                             dependency_role='unknown' if unconfirmed_record_binding else 'value')
        raw_op = operation('Declared logical RAW mapping', r['field_id'], [extract_id], [raw_id],
                           route['dbt_input'], 'direct', 'evidence_supported',
                           [ref(p + '/ingestion_route', role='declared_ingestion_association')],
                           group, r['field_id'], 'extract-to-logical-JSON-key', route=route)
        if h['cleanup']['enabled'] == 'Y':
            # Attach reported settings to the existing logical association. The
            # input does not establish an execution event or a serial step order.
            ops[raw_op]['reported_hvr_cleanup_json'] = h['cleanup']
            ops[raw_op]['hvr_cleanup_context_json'] = {
                'scope': 'reported HVR parameter configuration associated with this extract header',
                'execution_verified': False, 'execution_order': 'not_supplied',
                'operation_type_scope': 'direct identifies the declared extract-header to RAW-key association, not all ingestion processing',
                'evidence_json': [ref(p + '/hvr_parameter/cleanup', role='reported_cleanup_configuration',
                                      reported_parameter_path=r['source_path'])]}
        sources[r['field_id']] = dict(group=group, source_id=source_id, extract_id=extract_id,
                                     raw_id=raw_id, basic_op=basic_op, raw_op=raw_op,
                                     source_resolved=source_resolved, source_gaps=missing_source,
                                     unconfirmed_record_binding=unconfirmed_record_binding,
                                     record_index=i)
        for j, t in enumerate(r.get('dbt_targets', [])):
            fid = uid('snowflake-field', snapshot, t['relation'], t['column'])
            tp = p + '/dbt_targets/' + str(j)
            node(fid, 'Snowflake', t['stage'], t['relation'], t['column'], 'physical_column',
                 identity_resolution_status='reported', locator=None,
                 description=t.get('description'), description_origin='recorded_input',
                 data_type=t.get('data_type'), classification=t.get('classification'),
                 metadata=t, source_refs_json=[ref(tp)])
            target_index[(t['model'], t['column'])].append((r['field_id'], j, fid))

    target_ops, internal_upstream, op_paths = {}, {}, {}
    for r in records:
        s = sources[r['field_id']]
        p = context_pointer[r['field_id']]
        for j, t in enumerate(r['dbt_targets']):
            if t['stage'] != 'internal': continue
            tp = p + '/dbt_targets/' + str(j)
            tid = uid('snowflake-field', snapshot, t['relation'], t['column'])
            expr = t['source_expression']
            keys = list(dict.fromkeys(re.findall(r'\bDATA:([A-Za-z_][A-Za-z0-9_]*)', expr, re.I)))
            # Matching the DATA alias ignores case; matching the JSON key does not.
            raw_inputs = []
            for key in keys:
                matching = [rr for rr in records if rr['ingestion_route']['raw_relation'] == r['ingestion_route']['raw_relation']
                            and rr['ingestion_route']['dbt_input'].split(':', 1)[1] == key]
                assert len(matching) == 1, ('Missing/ambiguous input JSON key', tp, key)
                raw_inputs.append(sources[matching[0]['field_id']]['raw_id'])
            assert raw_inputs, ('No structured DATA key could be resolved', tp)
            location_review = []
            if t.get('source_path', '').endswith(('.yml', '.yaml')):
                location_review.append({'code': 'UNRESOLVED_CROSS_ARTIFACT_LOCATION',
                                        'reason': 'The input reports a YAML path alongside an SQL expression/line; the actual SQL location was not supplied.',
                                        'affected_field_id': tid, 'source_reference': tp})
            if '{{' in expr:
                location_review.append({'code': 'MACRO_IMPLEMENTATION_NOT_SUPPLIED',
                                        'reason': 'The dependency and macro call are recorded; the macro body and runtime result were not verified.',
                                        'affected_field_id': tid, 'source_reference': tp + '/source_expression'})
            rid = operation('dbt internal mapping', t['model'] + '.' + t['column'], raw_inputs, [tid],
                            expr, 'cast' if '::' in expr else 'unknown',
                            'evidence_supported', [ref(tp, reported_path=t['source_path'],
                                                       reported_line=t.get('source_line'), expression=expr)],
                            s['group'], r['field_id'], 'logical-JSON-key-to-physical-column',
                            reviews=location_review)
            target_ops[tid] = rid
            internal_upstream[tid] = raw_inputs
            op_paths[tid] = [s['basic_op'], s['raw_op'], rid]
    for r in records:
        s = sources[r['field_id']]
        p = context_pointer[r['field_id']]
        for j, t in enumerate(r['dbt_targets']):
            if t['stage'] != 'public': continue
            tp = p + '/dbt_targets/' + str(j)
            tid = uid('snowflake-field', snapshot, t['relation'], t['column'])
            matches = target_index[(t['source_model'], t['source_column'])]
            assert len(matches) == 1, ('Missing/ambiguous public predecessor', tp)
            source_map, source_j, predecessor = matches[0]
            assert nodes[predecessor]['stage'] == 'internal'
            expr = t['projection_expression']
            rid = operation('dbt public projection', t['model'] + '.' + t['column'], [predecessor], [tid],
                            expr, 'direct' if t['column'] == t['source_column'] else 'rename',
                            'evidence_supported', [ref(tp, reported_path=t['source_path'],
                                                       reported_projection_line=t.get('projection_line'), expression=expr)],
                            s['group'], r['field_id'], 'physical-column-to-physical-column')
            target_ops[tid] = rid
            op_paths[tid] = op_paths[predecessor] + [rid]

    def issue(code, reason, pointer, affected=None):
        return {'code': code, 'reason': reason, 'source_reference': pointer,
                'affected_field_id': affected}

    for i, r in enumerate(records):
        s, u, h, route = sources[r['field_id']], r['ultracs'], r['hvr_parameter'], r['ingestion_route']
        p = '/' + str(i)
        primary = (r['snowflake_table'], r['snowflake_column'])
        primary_id = uid('snowflake-field', snapshot, *primary)
        for j, t in enumerate(r['dbt_targets']):
            tp = p + '/dbt_targets/' + str(j)
            tid = uid('snowflake-field', snapshot, t['relation'], t['column'])
            entry = uid('dictionary-row', snapshot, s['group'], tid)
            process_ids = op_paths[tid]
            for rid in process_ids: ops[rid]['dictionary_entry_ids'].append(entry)
            field_ids = list(dict.fromkeys(fid for rid in process_ids
                                           for fid in ops[rid]['source_field_ids'] + ops[rid]['target_field_ids']))
            reviews = list(s['source_gaps'])
            if not u.get('description'):
                reviews.append(issue('SOURCE_DESCRIPTION_MISSING', 'No source-side description is supplied.', p + '/ultracs/description', s['source_id']))
            reviews.append(issue('BUSINESS_DEFINITION_NOT_REVIEWED', 'No reviewed source business definition, reviewer or review date is supplied.', p, s['source_id']))
            for k in ('description', 'model_description', 'data_type', 'classification'):
                if not t.get(k): reviews.append(issue('TARGET_' + k.upper() + '_MISSING', 'Target ' + k + ' is not supplied.', tp, tid))
            for rid in process_ids: reviews.extend(ops[rid]['review_notes_json'])
            if r['confidence'] == 'inferred':
                reviews.append(issue('ORIGINAL_MAPPING_INFERRED', r['notes'], p + '/confidence', s['source_id']))
            if r['param_column'].startswith('MissingColumn'):
                reviews.append(issue('PLACEHOLDER_FIELD_NAME', 'The original placeholder name is preserved; its business meaning is unknown.', p + '/param_column', s['extract_id']))
            renames, observations, descriptions = [], [], []
            for rid in process_ids:
                op = ops[rid]
                source_node, target_node = nodes[op['source_field_ids'][0]], nodes[op['target_field_ids'][0]]
                if source_node['field_name'] != target_node['field_name']:
                    renames.append({'relationship_id': rid, 'from_field_id': source_node['field_id'],
                                    'to_field_id': target_node['field_id'], 'from_name': source_node['field_name'],
                                    'to_name': target_node['field_name'], 'from_object': source_node['object'],
                                    'to_object': target_node['object'],
                                    'change_kind': 'source_to_extract_label' if rid == s['basic_op'] else
                                                   'logical_JSON_key' if rid == s['raw_op'] else 'projection_or_transformation_alias',
                                    'operation_type': op['operation_type'], 'evidence_json': op['evidence_json']})
            for fid in field_ids:
                n = nodes[fid]
                observations.append({'field_id': fid, 'stage': n['stage'], 'declared_type': n['data_type'],
                                     'classification': n['classification'], 'source_refs_json': n['source_refs_json']})
                descriptions.append({'field_id': fid, 'stage': n['stage'], 'description': n.get('description'),
                                     'origin': 'recorded_input' if n.get('description') else 'unknown',
                                     'author': None, 'business_review_status': 'unknown',
                                     'source_refs_json': n['source_refs_json']})
            for rid in process_ids:
                cast_types = re.findall(r'::([A-Za-z_][A-Za-z0-9_]*(?:\([^)]*\))?)', ops[rid]['expression'])
                for cast_type in cast_types:
                    observations.append({'relationship_id': rid, 'expression_cast': cast_type,
                                         'target_field_ids': ops[rid]['target_field_ids'], 'verification_mode': 'reported_json_only'})
                    declared = nodes[ops[rid]['target_field_ids'][0]].get('data_type')
                    if declared and ((cast_type == 'STRING' and re.match(r'NUMBER|FLOAT|DECIMAL|INT', declared)) or
                                     (cast_type == 'NUMBER' and re.match(r'VARCHAR|STRING', declared))):
                        reviews.append(issue('DECLARED_TYPE_CAST_DIFFERENCE',
                                             'Recorded SQL cast ' + cast_type + ' differs from declared type ' + declared + '; retain both for review.',
                                             ops[rid]['evidence_json'][0]['input_pointer'], ops[rid]['target_field_ids'][0]))
            all_source = ', '.join(u.get('source_references', [])) or u['basic_expression']
            process_text = ('BASIC: ' + u['transformation'] + ' [expression: ' + u['basic_expression'] + ']. '
                            + 'Declared extract ' + r['extract_file'] + '[' + str(r['ultracs_position']) + '] ' + r['param_column']
                            + ' -> ' + route['raw_relation'] + '.' + route['dbt_input'] + '. ')
            for rid in process_ids[2:]:
                target_node = nodes[ops[rid]['target_field_ids'][0]]
                process_text += target_node['object'] + '.' + target_node['field_name'] + ' using ' + ops[rid]['expression'] + ' '
            if h['cleanup']['enabled'] == 'Y':
                process_text += 'Reported HVR parameter cleanup configuration: ' + js(h['cleanup']) + '. Execution and its position within the ingestion route are not verified. '
            if s['unconfirmed_record_binding']:
                process_text += 'Record-variable alias binding is not supplied; do not treat this as a fully resolved origin.'
            elif not s['source_resolved']:
                process_text += 'Physical source/operand binding is incomplete; do not treat this as a fully resolved origin.'
            path_fields = [ops[process_ids[0]]['source_field_ids'][0]] + [ops[rid]['target_field_ids'][0] for rid in process_ids]
            row = {
                'dictionary_entry_id': entry, 'source_entry_id': s['group'], 'snapshot_id': snapshot,
                'row_kind': 'source_target', 'ultracs_field_id': r['field_id'],
                'ultracs_field_name': r['param_column'], 'source_name_origin': 'extract_parameter_label',
                'business_field_label': r['business_field'], 'identity_scope': 'extract_mapping',
                'source_locator': u.get('source_locator'), 'source_references_json': u.get('source_references', []),
                'source_program': u['program'], 'ultracs_source_path': u['source_path'],
                'hvr_parameter_source_path': r['source_path'],
                'source_description': u.get('description'), 'source_description_origin': 'recorded_input' if u.get('description') else 'unknown',
                'business_definition': None, 'definition_status': 'unknown',
                'business_review_json': {'status': 'unknown', 'author': None, 'reviewer': None, 'reviewed_at': None, 'evidence': []},
                'extract_file': r['extract_file'], 'extract_column': r['param_column'],
                'extract_position': r['ultracs_position'], 'basic_expression': u['basic_expression'],
                'basic_transformation': u['transformation'], 'basic_comment': u.get('basic_comment'),
                'basic_source_line': u['basic_source_line'], 'hvr_type': h['type'], 'hvr_obfuscation': h['obfuscate'],
                'hvr_cleanup_json': h['cleanup'], 'hvr_cleanup_enabled': h['cleanup']['enabled'],
                'hvr_cleanup_remove_chars_json': h['cleanup']['remove_chars'],
                'original_mapping_notes': r['notes'], 'target_field_id': tid,
                'is_primary_target': (t['relation'], t['column']) == primary,
                'primary_target_field_id': primary_id,
                'source_primary_target_json': {'table': r['snowflake_table'], 'column': r['snowflake_column'], 'cdp': r['cdp']},
                'snowflake_stage': t['stage'], 'snowflake_table': t['relation'], 'snowflake_column': t['column'],
                'snowflake_model': t['model'], 'snowflake_model_id': t['model_id'],
                'snowflake_model_description': t.get('model_description'), 'snowflake_description': t.get('description'),
                'snowflake_description_origin': 'recorded_input' if t.get('description') else 'unknown',
                'snowflake_data_type': t.get('data_type'), 'snowflake_classification': t.get('classification'),
                'target_business_review_json': {'business_definition': None, 'status': 'unknown', 'reviewer': None,
                                                'reviewed_at': None, 'description_is_approved_definition': False},
                'target_source_model': t.get('source_model'), 'target_source_column': t.get('source_column'),
                'target_source_expression': t.get('source_expression'), 'target_projection_expression': t.get('projection_expression'),
                'target_source_location_json': {k: t[k] for k in ('source_path', 'source_line', 'projection_line') if k in t},
                'rename_summary': '; '.join(x['from_object'] + '.' + x['from_name'] + ' -> ' + x['to_object'] + '.' + x['to_name']
                                            + ' (' + x['change_kind'] + ')' for x in renames),
                'rename_details_json': renames, 'process_summary': process_text.strip(),
                'process_relationship_ids': process_ids,
                'operation_output_scope_json': {rid: ops[rid]['target_field_ids'] for rid in process_ids},
                'process_details_json': None,
                'path_details_json': [{'path_id': uid('path', snapshot, entry, process_ids),
                                       'source_entry_id': s['group'], 'target_field_id': tid,
                                       'field_ids': path_fields, 'relationship_ids': process_ids,
                                       'state': 'complete_as_reported' if s['source_resolved'] else 'partial',
                                       'source_participation': 'value' if s['source_resolved'] else 'unknown',
                                       'path_complete': s['source_resolved'], 'unresolved_segments': s['source_gaps'],
                                       'verification_mode': 'reported_json_only',
                                       'scope': 'reported locator/reference association through represented target; no runtime verification'}],
                'association_status': 'reported',
                'source_participation_json': {'role': 'value' if s['source_resolved'] else 'unknown',
                                              'target_field_id': tid, 'basis': 'reported input bindings',
                                              'sole_source_established': False},
                'path_complete': s['source_resolved'], 'datatype_observations_json': observations,
                'description_details_json': descriptions, 'original_mapping_confidence': r['confidence'],
                'relationship_confidence_summary': '; '.join(rid + ': Unscored (numeric assessment not supplied)' for rid in process_ids),
                'relationship_confidence_json': [{'relationship_id': rid, 'confidence_score_10': None,
                                                  'confidence_state': 'unscored', 'confidence_method': None,
                                                  'confidence_rationale': None, 'confidence_assessment_json': None} for rid in process_ids],
                'field_catalog_json': [nodes[fid] for fid in field_ids], 'route_context_json': route,
                'hvr_channels_json': route['hvr_channels'], 's3_paths_json': route['s3_paths'],
                'airflow_dag': route['airflow_dag'], 'airflow_tasks_json': route['airflow_tasks'],
                'raw_relation': route['raw_relation'], 'dbt_input': route['dbt_input'],
                'needs_review': bool(reviews), 'review_notes_json': reviews,
                'provenance_json': {'input_file': args.input.name, 'input_sha256': digest, 'input_pointer': p,
                                    'verification_mode': 'reported_json_only',
                                    'technical_summary': {'origin': 'rule_generated', 'method': 'literal_recorded_path_summary'},
                                    'description_author': None, 'business_review': 'not_supplied',
                                    'notes': 'No model calls, repository validation, runtime checks or numeric scoring were performed.'},
                'source_refs_json': [ref(p), ref(tp)], 'original_record_json': r,
                'input_property_map_json': None,
            }
            # Add type/verification annotations without replacing the original location claims.
            row['target_source_location_json'].update(verification_mode='reported_json_only', input_pointer=tp)
            missing_headers = set(headers) - row.keys()
            assert not missing_headers, ('Unpopulated contract columns', missing_headers)
            assert not row.keys() - set(headers), ('Undocumented output columns', row.keys() - set(headers))
            direct = {
                '/field_id': ('ultracs_field_id', ''), '/business_field': ('business_field_label', ''),
                '/ultracs_program': ('source_program', ''), '/ultracs_position': ('extract_position', ''),
                '/extract_file': ('extract_file', ''), '/param_column': ('extract_column', ''),
                '/notes': ('original_mapping_notes', ''), '/confidence': ('original_mapping_confidence', ''),
                '/source_path': ('hvr_parameter_source_path', ''),
                '/snowflake_table': ('source_primary_target_json', '/table'),
                '/snowflake_column': ('source_primary_target_json', '/column'),
                '/cdp': ('source_primary_target_json', '/cdp'),
                '/hvr_parameter/name': ('extract_column', ''), '/hvr_parameter/type': ('hvr_type', ''),
                '/hvr_parameter/obfuscate': ('hvr_obfuscation', ''),
                '/hvr_parameter/cleanup': ('hvr_cleanup_json', ''), '/ingestion_route': ('route_context_json', ''),
                '/ultracs/program': ('source_program', ''), '/ultracs/source_path': ('ultracs_source_path', ''),
                '/ultracs/source_locator': ('source_locator', ''),
                '/ultracs/source_references': ('source_references_json', ''),
                '/ultracs/description': ('source_description', ''), '/ultracs/transformation': ('basic_transformation', ''),
                '/ultracs/basic_expression': ('basic_expression', ''), '/ultracs/basic_comment': ('basic_comment', ''),
                '/ultracs/basic_source_line': ('basic_source_line', ''), '/ultracs/extract_file': ('extract_file', ''),
                '/ultracs/position': ('extract_position', ''), '/ultracs/param_column': ('extract_column', ''),
            }
            target_columns = {'stage': 'snowflake_stage', 'model': 'snowflake_model', 'model_id': 'snowflake_model_id',
                              'relation': 'snowflake_table', 'column': 'snowflake_column', 'model_description': 'snowflake_model_description',
                              'description': 'snowflake_description', 'data_type': 'snowflake_data_type',
                              'classification': 'snowflake_classification', 'source_model': 'target_source_model',
                              'source_column': 'target_source_column', 'source_expression': 'target_source_expression',
                              'projection_expression': 'target_projection_expression'}
            for key, col in target_columns.items():
                if key in t: direct['/dbt_targets/' + str(j) + '/' + key] = (col, '')
            for key in ('source_path', 'source_line', 'projection_line'):
                if key in t: direct['/dbt_targets/' + str(j) + '/' + key] = ('target_source_location_json', '/' + key)
            coverage = []
            for relative, value in walk(r):
                destinations = [{'column': 'original_record_json', 'json_pointer': relative}]
                matches = [prefix for prefix in direct if relative == prefix or relative.startswith(prefix + '/')]
                if matches:
                    prefix = max(matches, key=len)
                    col, tail = direct[prefix]
                    destinations.append({'column': col, 'json_pointer': tail + relative[len(prefix):]})
                coverage.append({'input_pointer': p + relative, 'value_type': jtype(value),
                                 'destinations': destinations,
                                 'coverage_state': ('verified_structured' if isinstance(row[col], (dict, list))
                                                    else 'verified_visible') if matches else 'verified_raw'})
            row['input_property_map_json'] = coverage
            rows.append(row)

    for rid, op in ops.items():
        op['dictionary_entry_ids'] = sorted(set(op['dictionary_entry_ids']))
    for row in rows:
        row['process_details_json'] = [ops[rid] for rid in row['process_relationship_ids']]
    # CSV formula protection is reversible and does not modify the archived values.
    for row in rows:
        escaping = {}
        for col in headers:
            value = row[col]
            if isinstance(value, str) and (value.startswith("'") or value.lstrip().startswith(('=', '+', '-', '@')) or value.startswith(('\t', '\r'))):
                escaping[col] = {'original_value': value, 'method': 'one_apostrophe_prefix', 'escaped_prefix_count': 1}
                row[col] = "'" + value
        row['provenance_json']['csv_text_escaping'] = escaping
    return {'headers': headers, 'rows': rows, 'records': records,
            'nodes': nodes, 'operations': ops, 'snapshot_id': snapshot,
            'input_sha256': digest, 'sources': sources, 'build_issues': build_issues}
