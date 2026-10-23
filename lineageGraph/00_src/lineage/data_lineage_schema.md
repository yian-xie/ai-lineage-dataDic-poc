## Purpose and Modeling Rules

This schema keeps source ingestion, physical data movement, metadata declarations, dbt dependencies, and schema migrations independently traversable. A relationship is emitted only when supported by configuration or code evidence. Every parsed node and edge should retain `source_path`; inferred relationships should also carry a confidence value and must not be presented as confirmed routes.

`layer` describes where a relation/model sits in the product architecture. `kind` describes the physical Snowflake object. Do not infer one from the other: dbt views exist in both `internal/` and `public/`.

## Entity Types

### Source-Ingest Foundation

Retain these four existing entity types and their established identifiers/relationships while the graph builder is migrated to the expanded schema:

| Type | Meaning | Key properties |
| --- | --- | --- |
| `PROGRAM` | Ultracs BASIC program; files are mostly extensionless | `name`, `source_file` (actual repository-relative path/name; do not append `.b`) |
| `MV_FILE` | Ultracs MultiValue source file, such as `ACCOUNT` or `TRAN` | `name`, `source_file` |
| `EXTRACT_FILE` | Pipe-delimited extract emitted by a BASIC program, such as `dwacc` | `name`, `source_file`, `format` |
| `SNOWFLAKE_TABLE` | Compatibility type for existing source-ingest/raw-table graph nodes | `name`, `layer`; canonicalize to the matching `SNOWFLAKE_RELATION` identity when graphs are combined; do not create a duplicate physical object |

### Movement and Orchestration

| Type | Meaning | Key properties |
| --- | --- | --- |
| `HVR_CHANNEL` | HVR channel definition | `name`, `source_file`, `description` |
| `HVR_LOCATION` | Named HVR source or target location from a channel definition | `name`, `role` (`SOURCE`/`TARGET`), `source_file` |
| `S3_PATH` | A bucket/prefix at a specific point in a route | `uri_or_prefix`, `bucket_role` (for example `HVR` or `DATALAKE`), `source_file` |
| `CDP_PRODUCT` | CDP product directory/project, such as `accounts-v1` | `name`, `source_file` |
| `AIRFLOW_DAG` | Airflow DAG definition | `dag_id`, `source_file` |
| `AIRFLOW_TASK` | A task/operator in a DAG | `task_id`, `task_kind`, `source_file` |

### Declarations, Models, and Physical Relations

| Type | Meaning | Key properties |
| --- | --- | --- |
| `DBT_SOURCE` | A dbt source declaration, not the physical Snowflake object | `source_name`, `table_name`, declared `database`/`schema`, `source_file` |
| `DBT_MODEL` | A dbt SQL model | `name`, configured `materialized`, configured `database`/`schema`, `layer`, `source_file` |
| `SNOWFLAKE_RELATION` | Canonical physical Snowflake object | `name` (qualified where known), `kind` (`TABLE` or `VIEW`), `layer`, `creation_mechanism`, `source_file` |
| `SCHEMACHANGE_MIGRATION` | Versioned schemachange migration script | `version`, `name`, `source_file` |

`SNOWFLAKE_RELATION.creation_mechanism` identifies the evidence-backed creator, for example `HVR`, `AIRFLOW_COPY`, `DBT`, or `SCHEMACHANGE`. dbt `table` and `incremental` materializations produce a `SNOWFLAKE_RELATION` with `kind=TABLE`; dbt `view` produces one with `kind=VIEW`. Schemachange is not the only way a table can be created or changed. Keep the dbt model and its physical relation as separate nodes.

`DBT_SOURCE` resolves to the physical RAW relation using `RESOLVES_TO`; it is never a substitute for that relation. Likewise, `DBT_MODEL` materializes to a physical relation using `MATERIALIZES_AS`.

## Architectural Layers

Layers are metadata and are not entity types or physical relation kinds:

| Layer | Typical contents |
| --- | --- |
| `source` | Ultracs MultiValue files |
| `extract` | BASIC programs and emitted extract files |
| `landing` | HVR/Datalake S3 paths and raw Snowflake relations, such as `ACCOUNTS_V1__ACCOUNTS` |
| `internal` | dbt internal models and their materialized relations; may include tables and views |
| `public` | dbt public models and their materialized relations; may include tables and views |

## Relationship Types

Relationship direction is from the producing/owning entity to the consumed or resulting entity, except where the verb explicitly denotes an incoming source (such as `READS_FROM`).

### Ultracs BASIC

| Relationship | Direction | Meaning |
| --- | --- | --- |
| `READS_FROM` | `PROGRAM` -> `MV_FILE` | Program reads source file |
| `WRITES_TO` | `PROGRAM` -> `EXTRACT_FILE` | Program emits extract |
| `CALLS` | `PROGRAM` -> `PROGRAM` | Program invokes another program |

### HVR and Data Movement

| Relationship | Direction | Meaning |
| --- | --- | --- |
| `CARRIED_BY` | `EXTRACT_FILE` -> `HVR_CHANNEL` | Extract is handled by this channel; emit only when the channel/config identifies the file |
| `CAPTURES_FROM` | `HVR_CHANNEL` -> `HVR_LOCATION` | Channel source location from HVR configuration |
| `INTEGRATES_TO` | `HVR_CHANNEL` -> `HVR_LOCATION` | Channel target location from HVR configuration |
| `COPIES_TO` | `HVR_CHANNEL` -> `S3_PATH` | HVR channel writes to the evidenced HVR S3 path/prefix |
| `LANDS_IN` | `HVR_CHANNEL` -> `SNOWFLAKE_RELATION` | Direct HVR-to-Snowflake integration, only when configuration proves it |

Keep direct HVR-to-Snowflake integration and HVR-to-S3 ingestion as separate branches. Do not join them into one route unless configuration or runtime evidence establishes that connection.

### Airflow Orchestration and Loads

| Relationship | Direction | Meaning |
| --- | --- | --- |
| `CONTAINS` | `CDP_PRODUCT` -> `AIRFLOW_DAG` / `DBT_MODEL` / `SCHEMACHANGE_MIGRATION` | Product owns the artifact |
| `CONTAINS_TASK` | `AIRFLOW_DAG` -> `AIRFLOW_TASK` | Task belongs to DAG |
| `PRECEDES` | `AIRFLOW_TASK` -> `AIRFLOW_TASK` | Explicit task dependency/order in the DAG |
| `COPIES_FROM` | `AIRFLOW_TASK` -> `S3_PATH` | Task reads/copies from this S3 location |
| `COPIES_TO` | `AIRFLOW_TASK` -> `S3_PATH` | Task writes/copies to this S3 location |
| `LOADS_FROM` | `AIRFLOW_TASK` -> `S3_PATH` | Snowflake load task reads files from this S3 location |
| `LOADS_TO` | `AIRFLOW_TASK` -> `SNOWFLAKE_RELATION` | Task loads data into a physical Snowflake relation |
| `EXECUTES_DBT` | `AIRFLOW_TASK` -> `DBT_MODEL` | A dbt invocation/task runs the model; record selection/scope when known, not a DAG-wide scheduling assumption |

For the account S3 route, represent HVR S3 and Datalake S3 as distinct `S3_PATH` nodes. Model the copy task between them and the Snowflake load task from Datalake S3 to the RAW `SNOWFLAKE_RELATION`. The dbt source declaration then resolves to that RAW relation. Do not connect an S3 path directly to a `DBT_SOURCE`.

Airflow task ordering and dbt model dependencies are different relationships. Do not use `SCHEDULES: AIRFLOW_DAG -> DBT_MODEL` as a replacement for task-level orchestration and dbt `ref()` edges.

### dbt Dependencies and Materialization

| Relationship | Direction | Meaning |
| --- | --- | --- |
| `DEPENDS_ON` | `DBT_MODEL` -> `DBT_SOURCE` / `DBT_MODEL` | dbt `source()` or `ref()` dependency |
| `RESOLVES_TO` | `DBT_SOURCE` -> `SNOWFLAKE_RELATION` | Declared source maps to a physical relation |
| `MATERIALIZES_AS` | `DBT_MODEL` -> `SNOWFLAKE_RELATION` | Model output object, with kind derived from configured materialization |

### Schemachange

| Relationship | Direction | Meaning |
| --- | --- | --- |
| `MIGRATES` | `SCHEMACHANGE_MIGRATION` -> `SNOWFLAKE_RELATION` | Migration creates or alters the physical relation; retain the specific operation (`CREATE`, `ALTER`, etc.) as edge metadata when parsed |

`MIGRATES` covers both creation and alteration without asserting that every migration only evolves an existing table. A migration may target a `TABLE` or `VIEW` relation.

## Provenance and Confidence

All parser-produced nodes and edges should include `source_path`. Prefer the exact repository-relative file path, especially for extensionless BASIC programs. Attach configuration details or matched expressions as evidence metadata where useful. Use `confidence=explicit` for direct declarations and `confidence=inferred` (with a short reason) for filename-pattern or naming-based associations. Do not infer that a configured location is a concrete table or S3 prefix unless the relevant config/action supplies that mapping.