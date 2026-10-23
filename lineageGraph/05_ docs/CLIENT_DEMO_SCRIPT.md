# Client Demo Script: Account Data Lineage

**Length:** 7–9 minutes, plus questions  
**Audience:** Business and technical stakeholders  
**Suggested screen order:** Project Findings → Detailed graph → Schema overview fan-out and Detail toggle → focused column → Data Dictionary → Enterprise graph

## Opening (30 seconds)

**Show:** Findings page.

**Say:**

> Today I'll show how this proof of concept traces account data from the legacy Ultracs environment toward Snowflake. We'll start with the account journey, then follow one field, and finish with selected downstream Enterprise consumers.
>
> One important boundary: this is lineage inferred from checked-in code and configuration. It is not a live production trace, and it does not run or inspect production jobs.

## Set the scale (45 seconds)

**Show:** The graph counts on the findings page.

**Say:**

> The full repository graph contains 2,005 nodes and 3,033 relationships. A node is a distinct typed item in the graph: for example, a program, file, HVR channel, workflow task, or Snowflake relation. These counts are not counts of columns or source files.
>
> For this walkthrough, we’ve narrowed that larger graph to the account slice: 39 nodes and 65 relationships. That smaller view makes one business journey easier to inspect.

**Technical note:** The full graph is assembled from parser evidence across BASIC, HVR, Airflow, dbt, and schemachange files. Multiple graph items can come from one file; repeated IDs are deduplicated. Edges carry the relationship type and evidence metadata.

## 1. Source and extract (1 minute)

**Show:** Main column-lineage page in Detailed mode. Locate `ACCOUNT`, `TRAN`, `KWDW_ACC`, and `DWACC`.

**Say:**

> The journey begins with account and transaction records in Ultracs. The legacy `KWDW_ACC` program reads those records and creates the `DWACC` extract. In business terms, this is where the account data is selected and prepared for downstream delivery.
>
> The graph lets us move between the source records, the program, and the output file, then inspect which repository evidence supports those links.

**Technical note:** Describe the relationship labels as the parser recorded them. For example, `READS_FROM` is stored from the program to its input-file node; do not treat every displayed arrow as a literal source-to-consumer data-flow direction.

## 2. Delivery routes and the known gap (1.5 minutes)

**Show:** The HVR and account-ingestion portions of the Detailed graph.

**Say:**

> From `DWACC`, the repository evidence shows two configured routes. One is a direct HVR route to the `LOADACCOUNTS_INGEST` landing relation. The other carries files through S3 and the account Airflow ingestion path into the account RAW table, where dbt models continue the journey.
>
> The distinction matters: we can show both routes, but the checked-in evidence does not establish that the direct HVR landing relation feeds the account-v1 RAW table. We’ve kept that as an explicit open question rather than drawing a connection we can’t substantiate.

**Technical note:** The S3/Airflow path is supported by the configured file copy/load steps and dbt source/model declarations. The filename-pattern match between the extract and HVR capture is inferred. The direct landing-to-RAW bridge remains unproven.

## 3. Show the Schema Overview (1.5 minutes)

**Show:** Select outer **Schema overview** and expand the groups. Point out the five node shapes, entity-type colors, directional arrows, and the separate disconnected direct-route warning.

**Say:**

> This view is a compact, selected critical path, not every node in the repository graph. Expanded nodes open the existing inspector. The visible path is presentation-only; it does not add relationships to the canonical graph JSON. The direct HVR landing is kept separate because no checked-in evidence connects it to the account RAW path.

**Then show:** The nested **Detail view**, which restores the older schema force graph and its inspector. Return to **Schema view** before continuing.

## 4. Follow one field (1.5 minutes)

**Show:** Account Number column graph.

**Say:**

> Now we can narrow from table-level movement to one business field: the account number. The mapping follows `KiwiAcc` in the `DWACC` layout to `KIWIBANKACCOUNTNUMBER` in Snowflake, with type `VARCHAR(100)`.
>
> This is useful when someone asks, "Where does this field come from, and what evidence supports the mapping?" The view gives us a specific path to review instead of asking the audience to infer a column from a table-level graph.

**Technical note:** The field mapping is supported through the S3/Airflow/dbt route. The displayed confidence score is a fixed evidence-strength heuristic, not a statistical probability or a guarantee that production ran as configured.

## 5. Data Dictionary and Enterprise consumers (2 minutes)

**Show:** Select **Data Dictionary**, then the Enterprise graph.

**Say:**

> The V3 dictionary viewer includes CSV and bundle import, filters, custom conditions, sorting, row details, and filtered export. Its embedded snapshot contains 179 mapping rows, 95 source mappings, 369 relationships, 7 assets, and 464 fields. The Enterprise graph is selected downstream context, not a complete product catalog.

## 6. Downstream Enterprise consumers (1 minute)

**Show:** Enterprise graph.

**Say:**

> The final view extends selected account outputs into downstream Enterprise models. It shows how account data is consumed by a focused set of products, including integrated account and curated dimension/fact models.
>
> This is a targeted extension, not a complete Enterprise catalog. The links shown are at table/model level; they do not claim column-level lineage or fill in orchestration that is not present in the repository evidence.

**Technical note:** The Enterprise extension reports 238 nodes and 495 relationships, reusing the account graph’s 39 nodes. It covers four selected Enterprise products; 30 of the 34 product directories are outside this account-focused view.

## Close (45 seconds)

**Say:**

> The value of this view is that it makes the supported path visible and separates confirmed evidence from assumptions and gaps. It gives business teams a way to discuss impact and ownership, and gives engineering teams concrete artifacts and unresolved joins to validate.
>
> The next useful validations are whether the direct HVR landing feeds account RAW, whether Account Index ID is formally defined as the combination of Account and Prod, and what source should provide runtime lineage.

## Likely questions

**"Does this prove what happened in production?"**  
No. It describes what checked-in source and configuration declare. A runtime/catalog integration would be needed to verify actual executions and deployed state.

**"Why are some links inferred?"**  
Some links are supported indirectly, such as by a filename-pattern match or a candidate composite key. The graph labels those separately so they can be validated instead of presented as confirmed.

**"Does this cover every column?"**  
The account DWACC inventory covers all 95 ordered HVR fields and their BASIC output expressions. It includes 112 internal and 67 public DBT projections; 59 fields reach a public model. The two Account Index ID components remain inferred, and public targets are listed only where the public SQL selects them.

**"What should we validate next?"**  
Confirm the direct HVR-to-RAW relationship, confirm the Account Index ID definition with its owner, and identify the authoritative source for runtime lineage.

## Presenter reminders

- Use “the repository configuration shows” or “the evidence supports,” not “production does.”
- Keep the direct HVR and S3/Airflow routes distinct unless new evidence connects them.
- Explain confidence as an evidence label/heuristic, never as a probability.
- If asked about a missing link, show it as a validation question; do not fill it in verbally.
- The direct HVR branch is intentionally omitted from the simplified fan-out; use Detailed mode for the complete graph evidence.