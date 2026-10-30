(function (root) {
  'use strict';

  var REQUIRED = ['dictionary_entry_id', 'source_entry_id', 'target_field_id',
    'process_relationship_ids', 'operation_output_scope_json', 'process_details_json', 'field_catalog_json'];
  var own = function (value, key) { return Object.prototype.hasOwnProperty.call(value, key); };
  var object = function (value) { return value !== null && typeof value === 'object' && !Array.isArray(value); };
  var text = function (value) { return value === null || value === undefined ? '' : String(value); };
  var lower = function (value) { return text(value).trim().toLowerCase(); };
  var empty = function (value) { return value === null || value === undefined || text(value).trim() === ''; };
  var inactive = function (value) { return empty(value) || lower(value) === 'all' || lower(value) === 'any'; };
  var truth = function (value) {
    if (value === true || lower(value) === 'true') return true;
    if (value === false || lower(value) === 'false') return false;
    return null;
  };
  function fail(message) { throw new Error(message); }
  function stable(value) {
    if (Array.isArray(value)) return '[' + value.map(stable).join(',') + ']';
    if (object(value)) return '{' + Object.keys(value).sort().map(function (key) {
      return JSON.stringify(key) + ':' + stable(value[key]);
    }).join(',') + '}';
    return JSON.stringify(value);
  }
  function headersValid(headers) {
    if (!Array.isArray(headers) || !headers.length) fail('CSV must contain a header row.');
    var seen = Object.create(null);
    headers.forEach(function (header) {
      if (typeof header !== 'string' || !header.trim()) fail('CSV contains an empty column name.');
      if (own(seen, header)) fail('CSV contains a duplicate column: ' + header);
      seen[header] = true;
    });
  }

  function parseCSV(input) {
    if (typeof input !== 'string') fail('CSV input must be text.');
    var source = input.charCodeAt(0) === 0xFEFF ? input.slice(1) : input;
    var records = [], record = [], cell = '', state = 'start', line = 1;
    function finishCell() { record.push(cell); cell = ''; state = 'start'; }
    function finishRecord() { finishCell(); records.push(record); record = []; }
    for (var i = 0; i < source.length; i += 1) {
      var ch = source[i];
      if (state === 'quoted') {
        if (ch === '"') {
          if (source[i + 1] === '"') { cell += '"'; i += 1; }
          else state = 'closed';
        } else {
          cell += ch;
          if (ch === '\n' || (ch === '\r' && source[i + 1] !== '\n')) line += 1;
        }
        continue;
      }
      if (ch === ',') { finishCell(); continue; }
      if (ch === '\r' || ch === '\n') {
        finishRecord();
        if (ch === '\r' && source[i + 1] === '\n') i += 1;
        line += 1;
        continue;
      }
      if (state === 'closed') fail('Unexpected text after a closing CSV quote near line ' + line + '.');
      if (ch === '"') {
        if (state !== 'start') fail('Unexpected CSV quote near line ' + line + '.');
        state = 'quoted';
      } else { cell += ch; state = 'plain'; }
    }
    if (state === 'quoted') fail('CSV contains an unclosed quoted field.');
    if (state !== 'start' || record.length || cell.length) finishRecord();
    if (!records.length) fail('CSV is empty.');
    var headers = records.shift();
    headersValid(headers);
    var rows = records.map(function (values, index) {
      if (values.length !== headers.length) fail('CSV record ' + (index + 2) + ' has ' + values.length +
        ' cells; expected ' + headers.length + '.');
      var row = Object.create(null);
      headers.forEach(function (header, n) { row[header] = values[n]; });
      return row;
    });
    return { headers: headers, rows: rows };
  }

  function getScore(op) {
    if (!object(op)) return null;
    var score = op.confidence_score_10;
    return typeof score === 'number' && Number.isFinite(score) && score >= 0 && score <= 10 ? score : null;
  }
  function uniqueStrings(value, location) {
    if (!Array.isArray(value)) fail(location + ' must be a JSON array.');
    var seen = Object.create(null);
    value.forEach(function (id) {
      if (typeof id !== 'string' || !id.trim()) fail(location + ' contains an empty or invalid ID.');
      if (own(seen, id)) fail(location + ' contains a duplicate ID: ' + id);
      seen[id] = true;
    });
    return value;
  }
  function arrayValue(value, fallback) { return Array.isArray(value) ? value : fallback; }
  function relevantOutputs(row, op) {
    var scope = row.json.operation_output_scope_json;
    if (!own(scope, op.relationship_id) || scope[op.relationship_id] === null) return null;
    return scope[op.relationship_id];
  }
  function relevantInputs(row, op, outputs) {
    if (outputs === null || !object(op.output_input_bindings_json)) return op.source_field_ids.slice();
    var result = [], seen = Object.create(null), unknown = false;
    outputs.forEach(function (output) {
      var bindings = op.output_input_bindings_json[output];
      if (!Array.isArray(bindings)) { unknown = true; return; }
      bindings.forEach(function (binding) {
        if (!own(seen, binding.field_id)) { seen[binding.field_id] = true; result.push(binding.field_id); }
      });
    });
    return unknown ? op.source_field_ids.slice() : result;
  }
  function nodeSearch(node) {
    if (!node) return '';
    return ['field_id', 'system', 'stage', 'object', 'field_name', 'locator', 'description', 'data_type', 'classification']
      .map(function (key) { return text(node[key]); }).join('\n');
  }
  function operationSearch(row, op) {
    var outputs = relevantOutputs(row, op);
    if (outputs !== null && !outputs.length) return '';
    var selected = outputs === null ? [] : outputs;
    var parts = [text(op.relationship_id), text(op.operation_type), text(op.status), text(op.dependency_role),
      text(op.confidence_method), text(op.confidence_rationale)];
    // Multi-output process names, global expressions and evidence may mention sibling branches.
    // Use explicit per-output formulas/bindings whenever a process has more than one output.
    if (op.target_field_ids.length <= 1) {
      parts.push(text(op.process_name), text(op.expression));
      arrayValue(op.evidence_json, []).forEach(function (evidence) {
        if (object(evidence)) parts.push(text(evidence.expression), text(evidence.transformation));
      });
    }
    selected.forEach(function (id) {
      parts.push(nodeSearch(row.catalog[id]));
      if (object(op.output_expressions_json)) parts.push(text(op.output_expressions_json[id]));
    });
    relevantInputs(row, op, outputs).forEach(function (id) { parts.push(nodeSearch(row.catalog[id])); });
    return parts.join('\n');
  }
  function reviewKey(review) { return stable(review); }
  function makeSearchText(row) {
    var names = ['ultracs_field_name', 'ultracs_field_id', 'business_field_label', 'source_locator',
      'source_program', 'source_description', 'business_definition', 'extract_file', 'extract_column',
      'extract_position', 'basic_expression', 'basic_transformation', 'basic_comment', 'original_mapping_notes',
      'snowflake_table', 'snowflake_column', 'snowflake_model', 'snowflake_model_description',
      'snowflake_description', 'snowflake_stage', 'snowflake_data_type', 'snowflake_classification',
      'target_source_model', 'target_source_column', 'target_source_expression', 'target_projection_expression',
      'process_summary', 'rename_summary', 'original_mapping_confidence'];
    var parts = names.map(function (name) { return text(row.raw[name]); });
    row.ops.forEach(function (op) { parts.push(operationSearch(row, op)); });
    row.reviews.forEach(function (review) {
      if (object(review)) parts.push(text(review.code), text(review.reason), text(review.message));
      else parts.push(text(review));
    });
    return parts.join('\n').toLowerCase();
  }

  function prepareDataset(parsed) {
    if (!object(parsed) || !Array.isArray(parsed.rows)) fail('Expected parsed CSV headers and rows.');
    headersValid(parsed.headers);
    REQUIRED.forEach(function (header) {
      if (parsed.headers.indexOf(header) === -1) fail('Required CSV column is missing: ' + header);
    });
    var rowIDs = Object.create(null), operations = Object.create(null), fieldIDs = Object.create(null);
    var fieldDefinitions = Object.create(null);
    var sourceIDs = Object.create(null), targetIDs = Object.create(null), snapshots = Object.create(null);
    var rows = parsed.rows.map(function (original, index) {
      var rowLabel = 'CSV record ' + (index + 2), raw = Object.create(null), json = Object.create(null);
      if (!object(original)) fail(rowLabel + ' must be a field/value object.');
      parsed.headers.forEach(function (header) {
        if (!own(original, header) || typeof original[header] !== 'string') fail(rowLabel + ' has an invalid cell: ' + header);
        raw[header] = original[header];
        if (/_json$/.test(header) || header === 'process_relationship_ids') {
          try { json[header] = JSON.parse(raw[header]); }
          catch (error) { fail(rowLabel + ', ' + header + ': invalid JSON.'); }
        }
      });
      if (empty(raw.dictionary_entry_id) || empty(raw.source_entry_id)) fail(rowLabel + ' is missing a dictionary/source ID.');
      if (own(rowIDs, raw.dictionary_entry_id)) fail('Duplicate dictionary row ID: ' + raw.dictionary_entry_id);
      rowIDs[raw.dictionary_entry_id] = true;
      var row = { raw: raw, json: json, id: raw.dictionary_entry_id, sourceId: raw.source_entry_id,
        snapshotId: text(raw.snapshot_id), ops: [], catalog: Object.create(null), reviews: [] };
      snapshots[row.snapshotId] = true;
      sourceIDs[JSON.stringify([row.snapshotId, row.sourceId])] = true;
      if (!empty(raw.target_field_id)) targetIDs[JSON.stringify([row.snapshotId, raw.target_field_id])] = true;
      else if (raw.row_kind !== 'no_documented_target') fail(rowLabel + ' has no target field ID.');
      if (!Array.isArray(json.field_catalog_json)) fail(rowLabel + ', field_catalog_json must be an array.');
      json.field_catalog_json.forEach(function (node) {
        if (!object(node) || typeof node.field_id !== 'string' || !node.field_id.trim()) fail(rowLabel + ' has an invalid catalog field.');
        if (own(row.catalog, node.field_id)) fail(rowLabel + ' contains a duplicate catalog field ID: ' + node.field_id);
        var fieldKey = JSON.stringify([row.snapshotId, node.field_id]);
        var fieldDefinition = stable(node);
        if (own(fieldDefinitions, fieldKey) && fieldDefinitions[fieldKey] !== fieldDefinition) {
          fail('Conflicting shared field definitions: ' + node.field_id);
        }
        fieldDefinitions[fieldKey] = fieldDefinition;
        row.catalog[node.field_id] = node;
        fieldIDs[fieldKey] = true;
      });
      if (!empty(raw.target_field_id) && !own(row.catalog, raw.target_field_id)) fail(rowLabel + ' has a dangling target field: ' + raw.target_field_id);
      if (!empty(raw.target_field_id)) {
        var targetNode = row.catalog[raw.target_field_id];
        [['snowflake_table', 'object'], ['snowflake_column', 'field_name'], ['snowflake_stage', 'stage']].forEach(function (pair) {
          if (!empty(raw[pair[0]]) && !empty(targetNode[pair[1]]) && raw[pair[0]] !== targetNode[pair[1]]) {
            fail(rowLabel + ' target metadata disagrees with its catalog identity: ' + pair[0]);
          }
        });
      }
      var ids = uniqueStrings(json.process_relationship_ids, rowLabel + ', process_relationship_ids');
      if (!object(json.operation_output_scope_json)) fail(rowLabel + ', operation_output_scope_json must be an object.');
      if (!Array.isArray(json.process_details_json)) fail(rowLabel + ', process_details_json must be an array.');
      var localOps = Object.create(null);
      json.process_details_json.forEach(function (op) {
        if (!object(op) || typeof op.relationship_id !== 'string' || !op.relationship_id.trim()) fail(rowLabel + ' has an invalid operation ID.');
        if (own(localOps, op.relationship_id)) fail(rowLabel + ' contains a duplicate operation ID: ' + op.relationship_id);
        if (op.snapshot_id !== undefined && op.snapshot_id !== row.snapshotId) fail(rowLabel + ' has an operation from another snapshot.');
        uniqueStrings(op.source_field_ids, rowLabel + ', operation inputs');
        uniqueStrings(op.target_field_ids, rowLabel + ', operation outputs');
        if (!op.target_field_ids.length) fail(rowLabel + ' has an operation with no output fields.');
        op.source_field_ids.concat(op.target_field_ids).forEach(function (id) {
          if (!own(row.catalog, id)) fail(rowLabel + ' has a dangling operation endpoint: ' + id);
        });
        if (own(op, 'confidence_score_10') && op.confidence_score_10 !== null &&
          (typeof op.confidence_score_10 !== 'number' || getScore(op) === null)) fail(rowLabel + ' has a confidence score outside 0–10 or a nonnumeric score.');
        var state = lower(op.confidence_state), score = getScore(op);
        if ((state === 'scored' && score === null) || (state === 'unscored' && score !== null)) fail(rowLabel + ' has inconsistent confidence score/state.');
        ['input_roles_json', 'output_expressions_json', 'output_input_bindings_json'].forEach(function (key) {
          if (own(op, key) && op[key] !== null && !object(op[key])) fail(rowLabel + ', ' + key + ' must be an object or null.');
        });
        if (object(op.input_roles_json)) Object.keys(op.input_roles_json).forEach(function (id) {
          if (op.source_field_ids.indexOf(id) === -1) fail(rowLabel + ' has an input role for an unknown operation input.');
          if (!Array.isArray(op.input_roles_json[id])) fail(rowLabel + ' has invalid input roles.');
        });
        if (object(op.output_expressions_json)) Object.keys(op.output_expressions_json).forEach(function (id) {
          if (op.target_field_ids.indexOf(id) === -1) fail(rowLabel + ' has an expression for an unknown operation output.');
        });
        if (object(op.output_input_bindings_json)) {
          Object.keys(op.output_input_bindings_json).forEach(function (id) {
            if (op.target_field_ids.indexOf(id) === -1) fail(rowLabel + ' has bindings for an unknown operation output.');
            var bindings = op.output_input_bindings_json[id];
            if (bindings !== null && !Array.isArray(bindings)) fail(rowLabel + ' has invalid output bindings.');
            if (Array.isArray(bindings)) bindings.forEach(function (binding) {
              if (!object(binding) || op.source_field_ids.indexOf(binding.field_id) === -1) fail(rowLabel + ' has a binding to an unknown operation input.');
              if (own(binding, 'roles') && !Array.isArray(binding.roles)) fail(rowLabel + ' has invalid binding roles.');
            });
          });
          op.target_field_ids.forEach(function (id) {
            if (!own(op.output_input_bindings_json, id)) fail(rowLabel + ' is missing an operation output binding; use null if unresolved.');
          });
        }
        var key = JSON.stringify([row.snapshotId, op.relationship_id]), encoded = stable(op);
        if (own(operations, key) && operations[key].encoded !== encoded) fail('Conflicting shared operation definitions: ' + op.relationship_id);
        operations[key] = { encoded: encoded, operation: op };
        localOps[op.relationship_id] = op;
      });
      ids.forEach(function (id) {
        if (!own(localOps, id)) fail(rowLabel + ' references an operation without an embedded definition: ' + id);
        if (!own(json.operation_output_scope_json, id)) fail(rowLabel + ' is missing an operation output scope: ' + id);
        row.ops.push(localOps[id]);
      });
      Object.keys(localOps).forEach(function (id) {
        if (ids.indexOf(id) === -1) fail(rowLabel + ' embeds an operation absent from process_relationship_ids: ' + id);
      });
      Object.keys(json.operation_output_scope_json).forEach(function (id) {
        if (!own(localOps, id)) fail(rowLabel + ' has a scope for an unknown operation: ' + id);
        var scope = json.operation_output_scope_json[id];
        if (scope !== null) uniqueStrings(scope, rowLabel + ', operation output scope').forEach(function (output) {
          if (localOps[id].target_field_ids.indexOf(output) === -1) fail(rowLabel + ' scopes an output not produced by its operation: ' + output);
        });
      });
      if (own(json, 'path_details_json') && json.path_details_json !== null) {
        if (!Array.isArray(json.path_details_json)) fail(rowLabel + ', path_details_json must be an array.');
        json.path_details_json.forEach(function (path) {
          if (!object(path)) fail(rowLabel + ' contains an invalid path.');
          arrayValue(path.relationship_ids, []).forEach(function (id) {
            if (!own(localOps, id)) fail(rowLabel + ' has a dangling path operation: ' + id);
          });
          arrayValue(path.field_ids, []).forEach(function (id) {
            if (!own(row.catalog, id)) fail(rowLabel + ' has a dangling path field: ' + id);
          });
          if (path.target_field_id && path.target_field_id !== raw.target_field_id) fail(rowLabel + ' contains another target’s path.');
        });
      }
      var relevantFields = Object.create(null);
      if (!empty(raw.target_field_id)) relevantFields[raw.target_field_id] = true;
      row.ops.forEach(function (op) {
        var outputs = relevantOutputs(row, op);
        if (outputs !== null && !outputs.length) return;
        if (outputs !== null) outputs.forEach(function (id) { relevantFields[id] = true; });
        relevantInputs(row, op, outputs).forEach(function (id) { relevantFields[id] = true; });
      });
      row.relevantFieldIds = Object.keys(relevantFields);
      var reviewSet = Object.create(null), suppliedReviews = arrayValue(json.review_notes_json, []).slice();
      row.ops.forEach(function (op) { suppliedReviews = suppliedReviews.concat(arrayValue(op.review_notes_json, [])); });
      suppliedReviews.forEach(function (review) {
        if (object(review)) {
          var affected = review.affected_field_id || review.affected_target_field_id || review.target_field_id;
          if (affected && !own(relevantFields, affected)) return;
          var operation = review.affected_relationship_id || review.relationship_id;
          if (operation && !own(localOps, operation)) return;
        }
        var key = reviewKey(review);
        if (!own(reviewSet, key)) { reviewSet[key] = true; row.reviews.push(review); }
      });
      row.reviewCodes = row.reviews.map(function (review) { return object(review) ? text(review.code) : ''; }).filter(Boolean);
      row.needsReview = truth(raw.needs_review) === true || row.reviews.length > 0;
      row.sourceDescriptionMissing = empty(raw.source_description);
      row.targetDescriptionMissing = empty(raw.snowflake_description);
      row.primary = truth(raw.is_primary_target);
      row.pathComplete = truth(raw.path_complete);
      row.pathState = row.pathComplete === true ? 'complete' : row.pathComplete === false ? 'partial' : 'unknown';
      row.sourceName = text(raw.ultracs_field_name || raw.extract_column);
      row.table = text(raw.snowflake_table); row.column = text(raw.snowflake_column); row.stage = text(raw.snowflake_stage);
      row.classification = text(raw.snowflake_classification); row.mappingLabel = text(raw.original_mapping_confidence);
      row.searchText = makeSearchText(row);
      return row;
    });
    return { headers: parsed.headers.slice(), rows: rows, operationCount: Object.keys(operations).length,
      sourceCount: Object.keys(sourceIDs).length, targetCount: Object.keys(targetIDs).length,
      fieldCount: Object.keys(fieldIDs).length, snapshots: Object.keys(snapshots), operationRegistry: operations };
  }

  function bound(value, label) {
    if (empty(value)) return null;
    if (typeof value === 'boolean') fail(label + ' must be a number.');
    var result = Number(value);
    if (!Number.isFinite(result)) fail(label + ' must be a number.');
    return result;
  }
  function hasOperationFilters(filters) {
    return !inactive(filters.operation) || !inactive(filters.opStatus) || !inactive(filters.confidence) ||
      !empty(filters.scoreMin) || !empty(filters.scoreMax);
  }
  function matchingOperations(row, filters) {
    filters = filters || {};
    var min = bound(filters.scoreMin, 'Minimum score'), max = bound(filters.scoreMax, 'Maximum score');
    return row.ops.filter(function (op) {
      var scope = relevantOutputs(row, op);
      if (scope !== null && !scope.length) return false;
      if (!inactive(filters.operation) && lower(op.operation_type) !== lower(filters.operation)) return false;
      if (!inactive(filters.opStatus) && lower(op.status) !== lower(filters.opStatus)) return false;
      var score = getScore(op), category = lower(filters.confidence);
      if (category === 'unscored' && score !== null) return false;
      if (category === 'scored' && score === null) return false;
      if (category === 'low' && (score === null || score >= 5)) return false;
      if (category === 'medium' && (score === null || score < 5 || score >= 8)) return false;
      if (category === 'high' && (score === null || score < 8)) return false;
      if (min !== null && (score === null || score < min)) return false;
      if (max !== null && (score === null || score > max)) return false;
      return true;
    });
  }
  function customMatch(row, condition) {
    if (!object(condition) || !condition.column) return true;
    if (!own(row.raw, condition.column)) return false;
    var value = row.raw[condition.column], wanted = text(condition.value), op = condition.operator || 'contains';
    if (op === 'empty') return empty(value);
    if (op === 'not_empty') return !empty(value);
    if (op === 'contains') return lower(value).indexOf(lower(wanted)) !== -1;
    if (op === 'not_contains') return lower(value).indexOf(lower(wanted)) === -1;
    if (op === 'equals') return lower(value) === lower(wanted);
    if (op === 'gte' || op === 'lte') {
      if (empty(value) || empty(wanted)) return false;
      var a = Number(value), b = Number(wanted);
      if (!Number.isFinite(a) || !Number.isFinite(b)) return false;
      return op === 'gte' ? a >= b : a <= b;
    }
    fail('Unknown custom filter operator: ' + op);
  }
  function filterRows(rows, filters) {
    if (!Array.isArray(rows)) fail('Expected prepared dictionary rows.');
    filters = filters || {};
    var min = bound(filters.scoreMin, 'Minimum score'), max = bound(filters.scoreMax, 'Maximum score');
    if (min !== null && max !== null && min > max) return [];
    var q = lower(filters.q), custom = arrayValue(filters.custom, []).filter(function (rule) { return object(rule) && rule.column; });
    return rows.filter(function (row) {
      var raw = row.raw;
      if (q && row.searchText.indexOf(q) === -1) return false;
      if (!inactive(filters.source) && row.sourceId !== filters.source) return false;
      if (!inactive(filters.table) && text(raw.snowflake_table) !== filters.table) return false;
      if (!inactive(filters.column) && text(raw.snowflake_column) !== filters.column) return false;
      if (!inactive(filters.stage) && lower(raw.snowflake_stage) !== lower(filters.stage)) return false;
      if (!inactive(filters.reviewReason) && row.reviewCodes.indexOf(filters.reviewReason) === -1) return false;
      if (filters.reviewState === 'needs_review' && !row.needsReview) return false;
      if (filters.reviewState === 'clear' && row.needsReview) return false;
      if (filters.sourceDescription === 'missing' && !row.sourceDescriptionMissing) return false;
      if (filters.sourceDescription === 'present' && row.sourceDescriptionMissing) return false;
      if (filters.targetDescription === 'missing' && !row.targetDescriptionMissing) return false;
      if (filters.targetDescription === 'present' && row.targetDescriptionMissing) return false;
      if (filters.primary === 'yes' && row.primary !== true) return false;
      if (filters.primary === 'no' && row.primary !== false) return false;
      if (!inactive(filters.path) && row.pathState !== filters.path) return false;
      if (!inactive(filters.mappingLabel) && lower(raw.original_mapping_confidence) !== lower(filters.mappingLabel)) return false;
      if (!inactive(filters.classification) && lower(raw.snowflake_classification) !== lower(filters.classification)) return false;
      if (hasOperationFilters(filters) && !matchingOperations(row, filters).length) return false;
      if (custom.length) {
        var test = function (rule) { return customMatch(row, rule); };
        if (lower(filters.customMode) === 'any' ? !custom.some(test) : !custom.every(test)) return false;
      }
      return true;
    });
  }

  function exportCSV(headers, rows) {
    headersValid(headers);
    if (!Array.isArray(rows)) fail('Expected rows to export.');
    function quote(value) {
      var cell = text(value);
      return /[",\r\n]/.test(cell) ? '"' + cell.replace(/"/g, '""') + '"' : cell;
    }
    var records = [headers.map(quote).join(',')];
    rows.forEach(function (row) {
      var raw = object(row) && object(row.raw) ? row.raw : row;
      if (!object(raw)) fail('Export rows must contain original CSV values.');
      records.push(headers.map(function (header) {
        if (!own(raw, header)) fail('Export row is missing column: ' + header);
        if (raw[header] !== null && typeof raw[header] === 'object') fail('Export requires original serialized CSV cells.');
        return quote(raw[header]);
      }).join(','));
    });
    return '\uFEFF' + records.join('\r\n') + '\r\n';
  }

  root.DDCore = Object.freeze({ parseCSV: parseCSV, prepareDataset: prepareDataset,
    filterRows: filterRows, exportCSV: exportCSV, getScore: getScore, matchingOperations: matchingOperations });
})(window);
