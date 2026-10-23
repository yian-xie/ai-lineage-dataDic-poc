# HTML Graph Render Skill

## Goal

Render the table, Enterprise, and column payloads as interactive local HTML graph views using vis.js Network. Do not use external dependencies beyond a vis.js CDN link. Embed the graph payloads in the page so generated HTML can be opened locally. The focused Account Number view uses the same renderer and adds a one-column flow banner.

## Node Appearance

Use these node colors by entity type:

| Entity type | Color |
| --- | --- |
| `MV_FILE` | Coral |
| `PROGRAM` | Amber |
| `EXTRACT_FILE` | Amber |
| `HVR_CHANNEL` | Purple |
| `S3_PATH` | Gray |
| `DBT_SOURCE` | Teal |
| `DBT_MODEL` | Teal |
| `SNOWFLAKE_RELATION` | Blue |
| `SCHEMACHANGE_MIGRATION` | Gray |

Use a restrained neutral fallback for other schema types, including `HVR_LOCATION`, `AIRFLOW_DAG`, `AIRFLOW_TASK`, and `CDP_PRODUCT`; never omit them just because no specific color was listed.

- Boundary nodes are larger.
- Entrypoint nodes have a double border.
- `confidence=INFERRED` edges render dashed; confirmed edges render solid. If confidence is absent, use a neutral dotted style and expose it as unspecified.
- Show edge labels on hover only; do not show all labels by default because they clutter the graph.

## Interaction

- Nodes must be movable; support pan and zoom.
- Provide a search control that finds node names, IDs, properties, and column mappings.
- Provide a side panel on node click with all node properties, including `source_path`, confidence, layer, and attached column mappings. List incoming and outgoing relationships with their types, directions, and confidence.
- For mapped column edges, show the source-system field locator, source description and transformation alongside the CDP/dbt model, target column description, data type, classification, and schema-file provenance when available. Preserve confidence and evidence notes.
- In both Detailed and Schema overview modes, show a non-empty description for every visible node and relationship, with a visible origin tag. Prefer checked-in node `description`/`model_description` and edge `description`/`evidence`; retain source paths. Use the shared `html_graph_descriptions.py` helper on a deep copy to fill gaps. Its `Generated` descriptions must stay literal and must not be mistaken for repository evidence or canonical data-dictionary definitions.
- Include descriptions in node inspectors, relationship inspectors/cards, and hover details. In Schema overview, show the description and origin for every column/repository/model/dataset node and every edge; hide raw helper metadata keys if an explicit description block is already rendered.
- Show confidence category plus the shared heuristic percentage rubric: explicit/confirmed 95%, confirmed_calculated 90%, declared_source 85%, inferred 60%, unconfirmed 50%; unknown is not rated. State that percentages are evidence-strength aids, not statistical probabilities.
- Provide visible relationship-confidence checkboxes for Explicit/confirmed (95%), Calculated (90%), Declared source (85%), Inferred/candidate (60%), Unconfirmed (50%), and Not rated. Multiple levels can be checked simultaneously; all are checked by default. Filter relationships by the selected set while retaining endpoint nodes as context; update relationship inspectors and visible edge counts. Reset checks all levels.
- Keep Enterprise continuation explicitly table-level unless column-level evidence and types are parsed. Never imply an Enterprise column mapping from a model/table dependency alone.
- Provide toggles for layer (`source`, `extract`, `landing`, `internal`, `public`), confirmed-only confidence, and route (`direct HVR only` / `S3 route only`). Do not merge the route branches when filtering.
- Provide an explicit option to hide the separate direct-HVR branch and a mapped-path-only view that hides nodes outside the evidence-backed column paths. Keep shared source/extract context and path connectors visible.
- Preserve the semantic relationship direction. If the viewer offers data-flow traversal, make reversed `READS_FROM` and `DEPENDS_ON` traversal visually distinct from stored edge direction.
- Keep text, controls, and graph legible on desktop and mobile; prevent labels and inspector content from clipping or overlapping.

## Data Dictionary View

- Provide a third **Data Dictionary** view beside Detailed and Schema overview, with Asset Registry, Field Catalog, and Lineage Links tabs.
- Derive asset rows from data-bearing nodes; derive field rows only from evidence-backed `(relation, column)` targets; derive lineage rows only from stored graph edges. This view is companion metadata and must not add or rewrite graph nodes/edges.
- Include the manager's asset fields (source system, layer, domain, owner, steward, description, refresh frequency, approximate row count, lineage reference, sensitivity, status) and field fields (business name, type, description, source, transformation, sample/enum, nullability, PII, primary/foreign key, business rules, verification date, notes).
- Show `Not documented` for unsupported values. Do not infer owner/steward, row counts, cadence, sample values, enums, nullability, keys, PII, or verification date. `SENSITIVE` is not itself a PII assertion.
- Preserve repository-relative evidence paths, description-origin tags, DBT target stage, and confidence. Show Enterprise assets/relationships as table-level only; do not create Enterprise field rows without column evidence.
- Offer search/filtering and CSV export for the active tab. CSV output must quote values and preserve commas/newlines safely.