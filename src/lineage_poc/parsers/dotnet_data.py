"""Repository-static EF snapshot schemas and CLR property bindings, not MSBuild execution."""

import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

from tree_sitter import Language, Parser
import tree_sitter_c_sharp


def _walk(node):
    yield node
    for child in node.named_children:
        yield from _walk(child)


def _text(node, source):
    return source[node.start_byte:node.end_byte].decode("utf-8") if node else ""


def _literal(node, source):
    if node is None or node.type != "string_literal":
        return None
    try:
        return json.loads(_text(node, source))
    except ValueError:
        return None


def _call(node, source):
    function = node.child_by_field_name("function")
    if not function or function.type != "member_access_expression":
        return None, [], None
    name = function.child_by_field_name("name")
    if name.type == "generic_name":
        name = name.named_children[0]
    arguments = node.child_by_field_name("arguments")
    values = [argument.named_children[-1] for argument in arguments.named_children if argument.named_children]
    return _text(name, source), values, function.child_by_field_name("expression")


def _chain(node, source):
    result = []
    while node and node.type == "invocation_expression":
        name, values, node = _call(node, source)
        result.insert(0, (name, values))
    return result


def _generic_argument_from_text(value):
    if "<" not in value or ">" not in value:
        return None
    return value.split("<", 1)[1].rsplit(">", 1)[0].strip().rstrip("?")


def _property_documentation(root, parser):
    records = {}
    for path in sorted(root.glob("src/**/*.cs")):
        if any("Tests" in part or part in {"bin", "obj"} for part in path.parts) or "Migrations" in path.parts:
            continue
        source = path.read_bytes()
        tree = parser.parse(source)
        namespace = next((_text(node.child_by_field_name("name"), source) for node in _walk(tree.root_node)
                          if node.type in {"namespace_declaration", "file_scoped_namespace_declaration"}), "")
        for declaration in _walk(tree.root_node):
            if declaration.type != "class_declaration":
                continue
            entity_name = namespace + "." + _text(declaration.child_by_field_name("name"), source)
            body = declaration.child_by_field_name("body")
            for property_node in body.named_children if body else []:
                if property_node.type != "property_declaration":
                    continue
                comments = []
                sibling = property_node.prev_named_sibling
                while sibling and sibling.type == "comment" and _text(sibling, source).startswith("///"):
                    comments.insert(0, _text(sibling, source))
                    sibling = sibling.prev_named_sibling
                documentation = "\n".join(line[3:] for comment in comments for line in comment.splitlines())
                description = ""
                if documentation:
                    try:
                        summary = ET.fromstring("<documentation>" + documentation + "</documentation>").find("summary")
                        description = " ".join("".join(summary.itertext()).split()) if summary is not None else ""
                    except ET.ParseError:
                        pass
                name = _text(property_node.child_by_field_name("name"), source)
                records[(entity_name, name)] = {"description": description, "source_path": path.relative_to(root).as_posix(),
                    "source_line": property_node.start_point.row + 1, "original_documentation": documentation,
                    "source_data_type": _text(property_node.child_by_field_name("type"), source)}
    return records


def _additional_evidence(root, parser):
    migrations, assignments, gaps = [], [], []
    operations = {"CreateTable", "DropTable", "RenameTable", "AddColumn", "DropColumn", "RenameColumn", "AlterColumn",
                  "AddForeignKey", "DropForeignKey", "CreateIndex", "DropIndex", "Sql", "InsertData", "UpdateData", "DeleteData"}
    for path in sorted(root.glob("src/**/*.cs")):
        if any("Tests" in part or part in {"bin", "obj"} for part in path.parts):
            continue
        relative = path.relative_to(root).as_posix()
        source = path.read_bytes()
        tree = parser.parse(source)
        if tree.root_node.has_error:
            gaps.append({"repository": "kb-accounts", "source_path": relative, "reason": "csharp_syntax_requires_additional_parser_support"})
            continue
        if "Migrations" in path.parts and not path.name.endswith((".Designer.cs", "ModelSnapshot.cs")):
            recorded = []
            for method in _walk(tree.root_node):
                if method.type != "method_declaration" or _text(method.child_by_field_name("name"), source) != "Up":
                    continue
                for call in _walk(method):
                    if call.type != "invocation_expression":
                        continue
                    name, arguments, _ = _call(call, source)
                    if name in operations:
                        recorded.append({"operation": name, "expression": _text(call, source), "source_line": call.start_point.row + 1,
                                         "literal_arguments": [_literal(argument, source) for argument in arguments]})
            migrations.append({"source_path": relative, "direction": "Up", "operations": recorded, "executed": False})
        if "Mapper" in path.stem:
            recorded = []
            for assignment in _walk(tree.root_node):
                if assignment.type == "assignment_expression":
                    recorded.append({"expression": _text(assignment, source), "source_line": assignment.start_point.row + 1,
                                     "binding_status": "not_resolved_to_database_or_cross_repository_fields"})
            if recorded:
                assignments.append({"source_path": relative, "assignments": recorded})
                gaps.append({"repository": "kb-accounts", "source_path": relative,
                             "reason": "csharp_mapper_assignments_require_semantic_field_binding", "assignment_count": len(recorded)})
    return migrations, assignments, gaps


def _event_relationships(root, parser, schema, documentation):
    fields = {}
    for row in schema:
        fields.setdefault(row["entity"].rsplit(".", 1)[-1], {}).setdefault(row["entity_id"], {})[row["property"]] = row
    entity_by_id = {identity: properties for candidates in fields.values() for identity, properties in candidates.items()}
    nodes, edges, mappings = {}, {}, []
    covered = {}
    for path in sorted(root.glob("src/**/*.cs")):
        if any("Tests" in part or part in {"bin", "obj", "Migrations"} for part in path.parts):
            continue
        source = path.read_bytes()
        tree = parser.parse(source)
        if tree.root_node.has_error:
            continue
        aliases, imports = {}, []
        namespace = next((_text(node.child_by_field_name("name"), source) for node in tree.root_node.named_children
                  if node.type in {"file_scoped_namespace_declaration", "namespace_declaration"}), "")
        for directive in tree.root_node.named_children:
            if directive.type == "using_directive":
                children = directive.named_children
                if len(children) == 2:
                    aliases[_text(children[0], source)] = _text(children[1], source)
                elif children:
                    imports.append(_text(children[-1], source))
        def resolve_event(type_name):
            prefix, separator, suffix = type_name.partition(".")
            resolved = aliases[prefix] + ("." + suffix if separator else "") if prefix in aliases else type_name
            if not separator and prefix not in aliases:
                event_imports = [name for name in imports if ".Events." in name]
                if len(event_imports) == 1:
                    resolved = event_imports[0] + "." + type_name
            return resolved if ".Events." in resolved else None

        relative = path.relative_to(root).as_posix()
        def event_node(resolved):
            identity = "dotnet:event:kb-accounts:" + resolved
            nodes.setdefault(identity, {"id": identity, "type": "DOTNET_EVENT", "properties": {
                "name": resolved, "kind": "CLR_EVENT_CONTRACT", "layer": "event_contract", "repository": "kb-accounts",
                "source_path": relative, "confidence": "explicit", "runtime_verified": False, "wire_serialization_verified": False}})
            return identity

        return_types = {_text(method.child_by_field_name("name"), source): resolve_event(_text(method.child_by_field_name("returns"), source))
                        for method in _walk(tree.root_node) if method.type == "method_declaration"}
        publisher_parameters = {}
        for parameter in _walk(tree.root_node):
            if parameter.type != "parameter":
                continue
            type_node = parameter.child_by_field_name("type")
            if type_node and _text(type_node, source).startswith("IOutboxEventPublisher<"):
                arguments = next((node for node in _walk(type_node) if node.type == "type_argument_list"), None)
                resolved = resolve_event(_text(arguments.named_children[0], source)) if arguments and arguments.named_children else None
                if resolved:
                    publisher_parameters[_text(parameter.child_by_field_name("name"), source)] = resolved
        for call in _walk(tree.root_node):
            if call.type != "invocation_expression":
                continue
            name, arguments, receiver = _call(call, source)
            publisher = publisher_parameters.get(_text(receiver, source))
            if name == "PublishAsync" and publisher:
                identity = "event:publisher:kb-accounts:" + relative + ":" + _text(receiver, source)
                nodes[identity] = {"id": identity, "type": "EVENT_PUBLISHER", "properties": {
                    "name": "Outbox publication boundary", "repository": "kb-accounts", "source_path": relative,
                    "confidence": "explicit", "is_boundary_node": True, "topic": None, "runtime_verified": False,
                    "reason": "Typed outbox publication call; concrete topic and publisher-to-consumer continuity unresolved."}}
                source_id = event_node(publisher)
                edges[(source_id, identity)] = {"source": source_id, "target": identity, "type": "PUBLISHED_VIA",
                    "properties": {"source_path": relative, "confidence": "explicit", "evidence": _text(call, source)}}
        for method in _walk(tree.root_node):
            if method.type != "method_declaration":
                continue
            parameters = method.child_by_field_name("parameters")
            bound = {}
            collection_parameters = {}
            entity_types = {}
            for identity, properties in entity_by_id.items():
                entity_types.setdefault(next(iter(properties.values()))["entity"], (identity, properties))

            def resolve_entity(type_name):
                if not type_name:
                    return None
                prefix, separator, suffix = type_name.partition(".")
                resolved = aliases[prefix] + ("." + suffix if separator else "") if prefix in aliases else type_name
                if resolved in entity_types:
                    return entity_types[resolved]
                if not separator:
                    candidates = [value for name, value in entity_types.items()
                                  if name.rsplit(".", 1)[-1] == resolved
                                  and name.rsplit(".", 1)[0] in imports + [namespace]]
                    if len(candidates) == 1:
                        return candidates[0]
                return None

            def generic_argument(type_node):
                if not type_node:
                    return None
                for item in _walk(type_node):
                    if item.type == "type_argument_list" and item.named_children:
                        return _text(item.named_children[0], source)
                return None

            def collection_entity(receiver):
                if receiver is None:
                    return None
                receiver_text = _text(receiver, source)
                direct = collection_parameters.get(receiver_text)
                if direct:
                    return direct
                for member in _walk(receiver):
                    if member.type != "member_access_expression":
                        continue
                    base = member.child_by_field_name("expression")
                    name = member.child_by_field_name("name")
                    if not base or base.type != "identifier" or _text(base, source) not in bound:
                        continue
                    parent_id, _ = bound[_text(base, source)]
                    parent_properties = entity_by_id.get(parent_id, {})
                    if not parent_properties:
                        continue
                    parent_type = next(iter(parent_properties.values()))["entity"]
                    property_record = documentation.get((parent_type, _text(name, source)), {})
                    element_type = _generic_argument_from_text(property_record.get("source_data_type", ""))
                    if element_type:
                        resolved = resolve_entity(element_type)
                        if resolved:
                            return resolved
                return None

            for parameter in parameters.named_children if parameters else []:
                type_name = _text(parameter.child_by_field_name("type"), source)
                direct = resolve_entity(type_name)
                if direct:
                    entity_id, entity_properties = direct
                    bound[_text(parameter.child_by_field_name("name"), source)] = (entity_id, entity_properties)
                element = resolve_entity(generic_argument(parameter.child_by_field_name("type")))
                if element:
                    collection_parameters[_text(parameter.child_by_field_name("name"), source)] = element

            for loop in _walk(method):
                if loop.type == "foreach_statement":
                    element = collection_entity(loop.child_by_field_name("right"))
                    if element:
                        bound[_text(loop.child_by_field_name("left"), source)] = element

            for lambda_node in _walk(method):
                if lambda_node.type != "lambda_expression":
                    continue
                parameter_node = lambda_node.child_by_field_name("parameters")
                if not parameter_node or parameter_node.type != "implicit_parameter":
                    continue
                owner = lambda_node.parent
                while owner and owner.type != "invocation_expression":
                    owner = owner.parent
                if not owner:
                    continue
                _, _, receiver = _call(owner, source)
                element = collection_entity(receiver)
                if element:
                    bound[_text(parameter_node, source)] = element
            if not bound:
                continue
            for creation in _walk(method):
                if creation.type != "object_creation_expression":
                    continue
                type_name = _text(creation.child_by_field_name("type"), source)
                resolved = resolve_event(type_name)
                if not resolved:
                    continue
                event_id = event_node(resolved)
                for assignment in _walk(creation):
                    if assignment.type != "assignment_expression":
                        continue
                    owner = assignment.parent
                    while owner and owner.type != "object_creation_expression":
                        owner = owner.parent
                    if owner != creation:
                        continue
                    target = _text(assignment.child_by_field_name("left"), source)
                    expression = assignment.child_by_field_name("right")
                    if not target.isidentifier() or expression is None:
                        continue
                    if expression.type == "invocation_expression":
                        helper = _text(expression.child_by_field_name("function"), source)
                        nested_type = return_types.get(helper)
                        if nested_type:
                            nested_id = event_node(nested_type)
                            edges[(nested_id, event_id)] = {"source": nested_id, "target": event_id, "type": "WRAPPED_IN_EVENT",
                                "properties": {"source_path": relative, "confidence": "explicit", "property": target,
                                    "evidence": _text(assignment, source), "wire_serialization_verified": False}}
                    dependencies = {}
                    for member in _walk(expression):
                        if member.type != "member_access_expression":
                            continue
                        ancestor = member.parent
                        diagnostic = False
                        while ancestor and ancestor != expression:
                            diagnostic = diagnostic or ancestor.type in {"throw_expression", "throw_statement"}
                            ancestor = ancestor.parent
                        if diagnostic:
                            continue
                        reference = _text(member, source)
                        variable, separator, property_name = reference.partition(".")
                        if separator and variable in bound and property_name in bound[variable][1]:
                            record = bound[variable][1][property_name]
                            dependencies[(record["entity_id"], property_name)] = record
                    for (entity_id, property_name), record in dependencies.items():
                        common = {"source_path": relative, "source_line": assignment.start_point.row + 1,
                                  "repository": "kb-accounts", "confidence": "explicit", "runtime_verified": False}
                        nodes[event_id] = {"id": event_id, "type": "DOTNET_EVENT", "properties": {**common,
                            "name": resolved, "kind": "CLR_EVENT_CONTRACT", "layer": "event_contract",
                            "wire_serialization_verified": False}}
                        key = (entity_id, event_id)
                        edge = edges.setdefault(key, {"source": entity_id, "target": event_id, "type": "ASSIGNS_TO_EVENT",
                            "properties": {**common, "related_field_mappings": [], "binding_scope": "Explicit C# source property references; wire serialization and runtime transport unverified."}})
                        exact = _text(assignment, source)
                        identity = json.dumps([entity_id, property_name, event_id, target, relative, exact])
                        mapping_id = "csharp-event:" + hashlib.sha256(identity.encode()).hexdigest()[:24]
                        edge["properties"]["related_field_mappings"].append(mapping_id)
                        covered.setdefault((entity_id, property_name), []).append(mapping_id)
                        mappings.append({"field_id": mapping_id, "graph_id": "tmv_column_lineage", "snapshot_id": "pending",
                            "repository": "kb-accounts", "project": record["context"], "source_relation_id": entity_id,
                            "source_relation": record["entity"], "source_column": property_name, "target_model_id": event_id,
                            "target_model": resolved, "target_relation_id": event_id, "target_relation": resolved,
                            "target_column": target, "source_path": relative, "source_line": common["source_line"],
                            "transformation_expression": exact, "expression_chain": [exact], "mapping_kind": "csharp_event_assignment",
                            "property_metadata": record["property_metadata"], "data_type": None, "confidence": "explicit",
                            "confidence_reason": "The exact C# assignment references this scoped entity property; helper implementations and transport/wire bindings are not verified.",
                            "lineage_granularity": "CLR-entity-property-to-CLR-event-contract-property"})
    assessments = []
    for record in schema:
        related = sorted(set(covered.get((record["entity_id"], record["property"]), [])))
        assessments.append({"entity_id": record["entity_id"], "property": record["property"], "database_column": record["column"],
            "relation_id": record["relation_id"], "source_path": record["source_path"], "related_mapping_ids": related,
            "status": "source_assignment_supported_transport_unresolved" if related else "unresolved",
            "reason": "Explicit source references found; event serialization and publisher-to-consumer topic continuity still unverified." if related else "No unambiguous typed entity-to-event assignment found for this extracted property; no relationship inferred from its name."})
    return list(nodes.values()), list(edges.values()), list({row["field_id"]: row for row in mappings}.values()), assessments


def parse_ef_snapshots(repo_path):
    root = Path(repo_path)
    parser = Parser(Language(tree_sitter_c_sharp.language()))
    documentation = _property_documentation(root, parser)
    nodes, edges, mappings, gaps, inventory, bindings = {}, [], [], [], [], {}
    snapshots = sorted(root.glob("src/**/*ModelSnapshot.cs"))
    for path in snapshots:
        if any("Tests" in part for part in path.parts):
            continue
        source = path.read_bytes()
        tree = parser.parse(source)
        relative = path.relative_to(root).as_posix()
        context = path.stem.removesuffix("ModelSnapshot")
        if tree.root_node.has_error:
            gaps.append({"repository": "kb-accounts", "source_path": relative, "reason": "csharp_snapshot_syntax_not_supported"})
            continue
        for invocation in _walk(tree.root_node):
            if invocation.type != "invocation_expression":
                continue
            method, values, _ = _call(invocation, source)
            if method != "Entity" or len(values) < 2 or values[-1].type != "lambda_expression":
                continue
            entity_name = _literal(values[0], source)
            if not entity_name:
                gaps.append({"repository": "kb-accounts", "source_path": relative, "reason": "ef_entity_identity_not_literal"})
                continue
            body = values[-1].child_by_field_name("body")
            table_calls = []
            for statement in body.named_children:
                if statement.type == "expression_statement":
                    calls = _chain(statement.named_children[0], source)
                    table_calls.extend(arguments for name, arguments in calls if name == "ToTable")
            binding_key = (context, entity_name)
            if not table_calls and binding_key in bindings:
                table, schema = bindings[binding_key]
            elif len(table_calls) == 1 and table_calls[0] and _literal(table_calls[0][0], source):
                table = _literal(table_calls[0][0], source)
                schema = _literal(table_calls[0][1], source) if len(table_calls[0]) > 1 else None
                bindings[binding_key] = table, schema
            else:
                gaps.append({"repository": "kb-accounts", "source_path": relative, "model_id": entity_name, "reason": "ef_table_binding_not_unique_literal"})
                continue
            relation_name = (schema or "<schema-unspecified>") + "." + table
            entity_id = "dotnet:entity:kb-accounts:" + context + ":" + entity_name
            relation_id = "postgres:relation:kb-accounts:" + context + ":" + relation_name
            common = {"source_path": relative, "project": context, "repository": "kb-accounts", "confidence": "explicit", "runtime_verified": False}
            nodes[entity_id] = {"id": entity_id, "type": "DOTNET_ENTITY", "properties": {**common, "name": entity_name, "kind": "CLR_ENTITY", "layer": "application"}}
            nodes[relation_id] = {"id": relation_id, "type": "POSTGRES_RELATION", "properties": {**common, "name": relation_name, "table": table, "schema": schema, "database": None, "kind": "TABLE", "layer": "application_database", "physical_binding_status": "repository_declared_not_runtime_verified"}}
            if table_calls:
                edges.append({"source": entity_id, "target": relation_id, "type": "MAPS_TO", "properties": {**common, "evidence": _text(invocation, source), "binding_scope": "EF model snapshot declaration"}})

            def emit(property_path, column, expression, column_type, kind="ef_property_binding"):
                expression_text = _text(expression, source)
                original = documentation.get((entity_name, property_path), {})
                schema_record = {"repository": "kb-accounts", "context": context, "entity": entity_name, "entity_id": entity_id,
                    "relation_id": relation_id, "relation": relation_name, "schema": schema, "table": table,
                    "property": property_path, "column": column, "data_type": column_type,
                    "source_path": relative, "source_line": expression.start_point.row + 1,
                    "expression": expression_text, "is_system_column": column == "xmin", "property_metadata": original}
                inventory.append(schema_record)
                identity = json.dumps([context, entity_name, property_path, column, relative], ensure_ascii=True)
                mappings.append({"field_id": "ef-column:" + hashlib.sha256(identity.encode()).hexdigest()[:24],
                    "graph_id": "tmv_column_lineage", "snapshot_id": "pending", "repository": "kb-accounts", "project": context,
                    "source_relation_id": entity_id, "source_relation": entity_name, "source_column": property_path,
                    "target_model_id": entity_id, "target_model": entity_name,
                    "target_relation_id": relation_id, "target_relation": relation_name, "target_column": column,
                    "transformation_expression": expression_text, "expression_chain": [expression_text],
                    "source_path": relative, "source_line": schema_record["source_line"], "data_type": column_type,
                    "mapping_kind": kind, "property_metadata": original, "confidence": "explicit",
                    "confidence_reason": "Explicit EF model-snapshot property/column declaration; not runtime processing or a SQL transformation.",
                    "lineage_granularity": "CLR-property-to-repository-declared-database-column"})

            def properties(block, prefix=""):
                nested_table_calls = [_chain(statement.named_children[0], source) for statement in block.named_children
                                      if statement.type == "expression_statement" and statement.named_children]
                for chain in nested_table_calls:
                    for name, arguments in chain:
                        if name == "ToTable" and arguments and _literal(arguments[0], source) != table:
                            gaps.append({"repository": "kb-accounts", "source_path": relative, "model_id": entity_id, "reason": "ef_owned_json_or_separate_table_not_supported", "property": prefix})
                            return
                for statement in block.named_children:
                    if statement.type != "expression_statement" or not statement.named_children:
                        continue
                    expression = statement.named_children[0]
                    details = dict(_chain(expression, source))
                    if "ToJson" in details:
                        arguments = details["ToJson"]
                        column = _literal(arguments[0], source) if arguments else None
                        types = details.get("HasColumnType", [])
                        if column and prefix:
                            emit(prefix.rstrip("."), column, expression, _literal(types[0], source) if types else None, "ef_json_document_binding")
                        else:
                            gaps.append({"repository": "kb-accounts", "source_path": relative, "model_id": entity_id, "reason": "ef_owned_json_or_separate_table_not_supported", "property": prefix})
                        return
                for statement in block.named_children:
                    if statement.type != "expression_statement" or not statement.named_children:
                        continue
                    expression = statement.named_children[0]
                    calls = _chain(expression, source)
                    if not calls:
                        continue
                    method, arguments = calls[0]
                    if method in {"ComplexProperty", "OwnsOne", "OwnsMany"}:
                        literals = [_literal(value, source) for value in arguments]
                        property_name = literals[1] if method in {"OwnsOne", "OwnsMany"} and len(literals) > 1 and literals[1] else next((value for value in literals if value), None)
                        nested = next((value for value in arguments if value.type == "lambda_expression"), None)
                        if nested and property_name:
                            properties(nested.child_by_field_name("body"), prefix + property_name + ".")
                        else:
                            gaps.append({"repository": "kb-accounts", "source_path": relative, "model_id": entity_id, "reason": "ef_nested_binding_not_resolved"})
                        continue
                    if method not in {"Property", "PrimitiveCollection"} or not arguments:
                        continue
                    property_name = _literal(arguments[0], source)
                    details = {name: values for name, values in calls}
                    column_arguments = details.get("HasColumnName", [])
                    column = _literal(column_arguments[0], source) if column_arguments else None
                    type_arguments = details.get("HasColumnType", [])
                    column_type = _literal(type_arguments[0], source) if type_arguments else None
                    if not property_name or not column:
                        gaps.append({"repository": "kb-accounts", "source_path": relative, "model_id": entity_id, "reason": "ef_column_name_not_explicit", "expression": _text(expression, source)})
                        continue
                    property_path = prefix + property_name
                    emit(property_path, column, expression, column_type)
            properties(body)
    migrations, assignments, extra_gaps = _additional_evidence(root, parser)
    gaps.extend(extra_gaps)
    event_nodes, event_edges, event_mappings, assessments = _event_relationships(root, parser, inventory, documentation)
    for node in event_nodes:
        nodes[node["id"]] = node
    edges.extend(event_edges)
    return {"nodes": list(nodes.values()), "edges": edges, "mappings": mappings, "schema_inventory": inventory,
        "event_mappings": event_mappings, "field_relationship_assessments": assessments,
        "migration_evidence": migrations, "assignment_evidence": assignments,
        "unresolved": gaps, "coverage": {"snapshot_count": len(snapshots), "binding_count": len(mappings),
            "runtime_verified": False, "business_transformations_verified": False,
            "migration_files": len(migrations), "mapper_files_with_unbound_assignments": len(assignments),
            "limitations": ["C# runtime transformations and service-to-dbt bridges are not inferred from property bindings.",
                           "Model snapshots report schemas; historical migrations are separate evidence, not additional current tables.",
                           "Database identities, imported mappings and conditional runtime configuration remain unverified."]}}