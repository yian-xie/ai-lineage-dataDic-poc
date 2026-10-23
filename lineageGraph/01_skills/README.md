# Lineage Skills

Skills are instruction sets for both the GitHub Copilot agent and the future Data Dictionary Builder agent. Each skill file tells the agent exactly how to perform one type of task, what inputs it needs, what output it must produce, and what rules it must follow.

## Skills

- [column_lineage_skill.md](column_lineage_skill.md): trace Ultracs fields through extract and HVR metadata to Snowflake columns.
- [column_lineage_explanation_skill.md](column_lineage_explanation_skill.md): explain a selected field's evidence-backed end-to-end flow in Markdown and in its focused HTML view.
- [confidence_score_skill.md](confidence_score_skill.md): assign and report confidence labels consistently, including clean-run checks, path scoring, and the reserved runtime-verified level.
- [data_dictionary_skill.md](dataDic/skill/data_dictionary_skill.md): build cited data dictionary entries (definition, type, classification, lineage) for traced Snowflake columns.
- [json_payload_skill.md](json_payload_skill.md): define the required JSON record structure for column lineage.
- [graph_traversal_skill.md](graph_traversal_skill.md): answer lineage questions using the table- and column-lineage graphs.
- [graph_query_skill.md](graph_query_skill.md): query generated graph JSON and column mappings with the dependency-free `query_graph.py` CLI.
- [html_graph_render_skill.md](html_graph_render_skill.md): render detailed, schema-overview, and focused lineage views with description provenance and confidence labels.

For clean-room regeneration and publishing, follow `../docs/RUNBOOK.md`. The column-lineage skills default to one requested column; the full evidence-backed mapping inventory remains a separate reusable artifact.

The authoritative entity and relationship definitions remain in `src/lineage/data_lineage_schema.md`. These skills describe how agents should apply that schema to specific tasks.