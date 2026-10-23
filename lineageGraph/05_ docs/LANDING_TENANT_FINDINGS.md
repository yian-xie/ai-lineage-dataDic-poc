# Tenant Landing Lineage Findings

## Scope

The parser reads dbt project metadata and SQL from `kb-cdp-tenant-landing/products/*/dbt`. The generated graph is a standalone parser output; it does not modify or merge into `table_lineage.json`.

The repository has **56 dbt product projects**. The parsed graph contains **4,255 nodes** and **5,838 relationships**: **56 products**, **2,218 models**, **577 source declarations**, and **1,404 physical relation identities**.

`ultracs-v1` contributes **339 models**, **97 sources**, **436 relation nodes**, and **812 dbt relationships**. Its `97` `ULTRACS_RAW` source declarations represent the HVR-facing landing layer.

## Position in the Lineage

`kb-cdp-tenant-landing` belongs after HVR ingestion and before downstream tenant consumers:

`Ultracs sources -> HVR -> Snowflake ULTRACS_RAW -> tenant-landing dbt views -> account tenant / selected Enterprise consumers`

The account tenant declares `1` source(s) named `ultracs_landing`; **1** has a matching landing model by declared schema and relation name: `feeexemption` in `ULTRACS_PUBLIC`. The same account project also declares `account_raw_source` tables in `RAW`; those are a distinct ingestion path and should not automatically be routed through tenant landing.

## Evidence and Limits

The current table graph has HVR-created physical relation names matching **90 of 97** `ultracs-v1` raw-source table names. These are **name-only candidates**, not merged lineage edges: HVR relations are often unqualified, while landing source declarations carry `ULTRACS_RAW` and a database declaration. Canonical database/schema evidence is needed before treating them as the same physical object.

The parser emits `2218` product ownership relationships, `2216` dbt dependency relationships, `577` source-to-relation relationships, and `827` model-to-relation relationships.

## Open Questions

- Confirm which HVR-created relations resolve to the tenant-landing `ULTRACS_RAW` objects using database/schema or runtime evidence.
- Confirm whether account and Enterprise consumers beyond `feeexemption` should source directly from tenant landing or continue through account-tenant `RAW` and public models.
- The repository README is still a placeholder; product ownership, deployment/runtime behavior, and the full intended consumer boundary need owner confirmation.

## Products

The parser scanned: `aci-payments-v1`, `activate-bb-v1`, `activate-kb-v1`, `ang-v1`, `argos-v1`, `centrix-v1`, `citibank-v1`, `complaints-v1`, `edw-dm-v1`, `edw-dwh-v1`, `etsl-v1`, `eunexus-v1`, `fetch-services-v1`, `isl-v1`, `kafl-v1`, `kb-publiccontent-v1`, `kbnetwork-v1`, `kiwisaver-v1`, `m365-v1`, `mds-intref-v1`, `mds-sysref-v1`, `p1c-v1`, `payee-v1`, `payments-delivery-v1`, `postilion-v1`, `qualtrics-v1`, `quote-tool-v1`, `reuters-v1`, `roecalc-v1`, `sdt-aml-v1`, `sdt-b2k-v1`, `sdt-cash-ordering-v1`, `sdt-comms-v1`, `sdt-compliance-v1`, `sdt-core-v1`, `sdt-crm-v1`, `sdt-identification-document-v1`, `sdt-insurance-v1`, `sdt-loan-v1`, `sdt-mw-v1`, `sdt-notes-v1`, `sdt-nps-v1`, `sdt-onboarding-v1`, `sdt-questionnaire-v1`, `sdt-report-v1`, `sdt-specialcare-v1`, `sdt-v1`, `secure-mail-v1`, `staging-ult-gl-v1`, `statements-v1`, `swift-v1`, `test-dp2`, `third-party-v1`, `tms-v1`, `ubw-v1`, `ultracs-v1`.

Generated graph: `../output/landing_tenant_lineage.json`.
