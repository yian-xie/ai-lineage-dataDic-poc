import json
from pathlib import Path
from typing import Dict, List

from lineage_poc.graph.builder import _add_edge, _add_node
from lineage_poc.graph.models import Edge, GraphPayload, Node
from lineage_poc.parsers.ultracs_basic import parse_ultracs_basic_file


FIELD_MAPPINGS = [
    {
        "field": "Account_Opened_Date",
        "source": "ACCOUNT<1>",
        "transformation": "OCONV(AREC<1>, 'D4')",
        "job": "KWDW_ACC",
        "output": "DWACC",
        "parquet_column": "OpenDate",
        "parquet_position": 54,
        "hvr_param_status": "CONFIRMED",
        "confidence": "confirmed",
        "evidence": "KWDW_ACC emits AREC<1> with the comment ACCOUNT OPENDATE.",
    },
    {
        "field": "Account_Name",
        "source": "ACCOUNT<28,2>",
        "transformation": "Direct; appended from AREC<28,2> (also emitted earlier as account name special).",
        "job": "KWDW_ACC",
        "output": "DWACC",
        "parquet_column": "AccountName",
        "parquet_position": 51,
        "hvr_param_status": "CONFIRMED",
        "confidence": "confirmed",
        "evidence": "KWDW_ACC comments AREC<28,2> as ACCOUNT NAME and Account Name (includes Suffix if present).",
    },
    {
        "field": "Signatory_Count",
        "source": "TRAN<4,4>",
        "transformation": "If REC<4,4> is zero, output 1; otherwise output REC<4,4>.",
        "job": "KWDW_ACC",
        "output": "DWACC",
        "parquet_column": "NumOfSignaturesReq",
        "parquet_position": 62,
        "hvr_param_status": "CONFIRMED",
        "confidence": "confirmed",
        "evidence": "KWDW_ACC computes NS from REC<4,4> and comments it NUM OF SIGNATURES REQUIRED.",
    },
    {
        "field": "Account_Index_ID",
        "source": "ACCOUNT @ID",
        "transformation": "Split ID into CIS and PID: FIELD(ID,'S',1), else FIELD(ID,'L',1), else FIELD(ID,'I',1); PID is the following 9 characters.",
        "job": "KWDW_ACC",
        "output": "DWACC",
        "parquet_columns": ["Account", "Prod"],
        "parquet_positions": [1, 2],
        "hvr_param_status": "INFERRED",
        "confidence": "candidate_composite_key",
        "evidence": "The first two output values are CIS and PID. No literal Account_Index_ID name appears in the searched jobs; confirm the consumer's key definition.",
    },
    {
        "field": "Account_ID",
        "source": "TRAN<4,8>",
        "transformation": "Direct output; KWDW_ACC labels REC<4,8> KIWIBANK ACCOUNT ID.",
        "job": "KWDW_ACC",
        "output": "DWACC",
        "parquet_column": "KiwiAcc",
        "parquet_position": 7,
        "hvr_param_status": "CONFIRMED",
        "confidence": "confirmed",
        "evidence": "KWDW_ACC labels REC<4,8> as KIWIBANK ACCOUNT ID.",
    },
    {
        "field": "Balance",
        "source": "TRAN<1> and TRAN transaction detail",
        "transformation": "BAL starts as OCONV(REC<1>,'MD2'); adjusted for records with PRDATE > RUNDATE using signed EODAMT based on TCODE <= 50; emitted as EOD BALANCE.",
        "job": "KWDW_ACC",
        "output": "DWACC",
        "parquet_column": "Balance",
        "parquet_position": 5,
        "hvr_param_status": "CONFIRMED",
        "confidence": "confirmed_calculated",
        "evidence": "KWDW_ACC initializes BAL from REC<1>, applies post-run-date adjustments, and appends BAL with the comment EOD BALANCE.",
    },
]


def build_account_fields_graph(
    datawarehouse_repo: str | Path,
    hvr_config_repo: str | Path | None = None,
) -> GraphPayload:
    repo = Path(datawarehouse_repo)
    hvr_config = Path(hvr_config_repo) if hvr_config_repo else repo.parent / "kb-cdp-hvr" / "hvr-config"
    acc_program = parse_ultracs_basic_file(repo / "KWDW_ACC")
    bal_program = parse_ultracs_basic_file(repo / "KWDW_ACCBAL")
    channels_dir = hvr_config / "apps" / "channels"
    sf_channel_data = json.loads((channels_dir / "ult_sf_acc.json").read_text(encoding="utf-8"))
    s3_channel_1_data = json.loads((channels_dir / "ult_s3_acc1.json").read_text(encoding="utf-8"))
    s3_channel_2_data = json.loads((channels_dir / "ult_s3_acc2.json").read_text(encoding="utf-8"))
    dwacc_param = json.loads((hvr_config / "scripts" / "DWACC.param").read_text(encoding="utf-8"))
    sf_channel = sf_channel_data["changes"][0]["add_channel"]
    s3_channel_1 = s3_channel_1_data["changes"][0]["add_channel"]
    s3_channel_2 = s3_channel_2_data["changes"][0]["add_channel"]

    def capture_pattern(channel: Dict) -> str:
        return next(
            action["params"]["Pattern"]
            for action in channel["actions"]
            if action.get("type") == "Capture" and "Pattern" in action.get("params", {})
        )

    def agent_plugin(channel: Dict) -> str:
        return next(
            Path(action["params"]["Command"]).name
            for action in channel["actions"]
            if action.get("type") == "AgentPlugin" and "Command" in action.get("params", {})
        )

    nodes: List[Node] = []
    edges: List[Edge] = []
    _add_node(nodes, "ultracs", "system", name="Ultracs / Pick BASIC", repo="kb-ultracs-datawarehouse")
    _add_node(nodes, "job:KWDW_ACC", "job", name=acc_program.name)
    _add_node(nodes, "job:KWDW_ACCBAL", "job", name=bal_program.name)
    _add_node(nodes, "file:DWACC", "extract_file", name="DWACC (daily account summary)")
    _add_node(nodes, "file:ACCBAL.TXT", "extract_file", name="ACCBAL.TXT (account balance extract)")
    _add_node(nodes, "file:ACCOUNT", "source_file", name="ACCOUNT", system="Ultracs")
    _add_node(nodes, "file:TRAN", "source_file", name="TRAN", system="Ultracs")
    sf_table = sf_channel["tables"]["loadaccounts_ingest"]
    _add_node(nodes, "location:fs_ultracs", "hvr_location", name="fs_ultracs", role="source")
    _add_node(nodes, "location:sf_lnd_ultra", "hvr_location", name="sf_lnd_ultra", role="Snowflake landing")
    _add_node(
        nodes,
        "channel:ult_sf_acc",
        "hvr_channel",
        name="ult_sf_acc",
        description=sf_channel["description"],
        capture_pattern=capture_pattern(sf_channel),
        source_file_format_separator="\\x1F",
    )
    _add_node(nodes, "config:ult_sf_acc.json", "hvr_config", path="hvr-config/apps/channels/ult_sf_acc.json")
    _add_node(
        nodes,
        "table:loadaccounts_ingest",
        "snowflake_landing_table",
        name=sf_table["base_name"],
        table_group=sf_table.get("table_group", ""),
        configured_columns=",".join(sf_table["cols"].keys()),
        raw_row_payload="payload",
    )
    for column_name, column_config in sf_table["cols"].items():
        _add_node(
            nodes,
            f"column:loadaccounts_ingest:{column_name}",
            "snowflake_column",
            table=sf_table["base_name"],
            name=column_name,
            data_type=column_config["data_type"],
        )

    s3_source_location = s3_channel_1["loc_groups"]["SOURCE"]["members"][0]
    s3_conversion_location = s3_channel_1["loc_groups"]["TARGET"]["members"][0]
    s3_target_location = s3_channel_2["loc_groups"]["TARGET"]["members"][0]
    s3_target_pattern = capture_pattern(s3_channel_2)
    s3_rename = next(
        action["params"]["RenameExpression"]
        for action in s3_channel_2["actions"]
        if action.get("type") == "Integrate" and "RenameExpression" in action.get("params", {})
    )
    _add_node(nodes, f"location:{s3_source_location}", "hvr_location", name=s3_source_location, role="source")
    _add_node(nodes, f"location:{s3_conversion_location}", "hvr_location", name=s3_conversion_location, role="conversion output")
    _add_node(nodes, f"location:{s3_target_location}", "hvr_location", name=s3_target_location, role="S3 target")
    _add_node(
        nodes,
        "channel:ult_s3_acc1",
        "hvr_channel",
        name="ult_s3_acc1",
        description=s3_channel_1["description"],
        capture_pattern=capture_pattern(s3_channel_1),
    )
    _add_node(nodes, "config:ult_s3_acc1.json", "hvr_config", path="hvr-config/apps/channels/ult_s3_acc1.json")
    _add_node(
        nodes,
        "channel:ult_s3_acc2",
        "hvr_channel",
        name="ult_s3_acc2",
        description=s3_channel_2["description"],
        capture_pattern=s3_target_pattern,
        target_path=s3_rename,
    )
    _add_node(nodes, "config:ult_s3_acc2.json", "hvr_config", path="hvr-config/apps/channels/ult_s3_acc2.json")
    _add_node(
        nodes,
        "config:DWACC.param",
        "parameter_config",
        path="hvr-config/scripts/DWACC.param",
        delimiter=dwacc_param["delim"],
        adds_header=dwacc_param["add_header"],
    )
    _add_node(
        nodes,
        "transform:src_to_parquet",
        "conversion_process",
        name=agent_plugin(s3_channel_1),
        parameter_file="DWACC.param",
        delimiter=dwacc_param["delim"],
        adds_header=dwacc_param["add_header"],
    )
    _add_node(nodes, "dataset:DWACC.parquet", "parquet_dataset", name="DWACC converted Parquet")

    _add_edge(edges, "ultracs", "job:KWDW_ACC", "runs")
    _add_edge(edges, "ultracs", "job:KWDW_ACCBAL", "runs")
    _add_edge(edges, "job:KWDW_ACC", "file:ACCOUNT", "reads")
    _add_edge(edges, "job:KWDW_ACC", "file:TRAN", "reads")
    if "DWACC" in acc_program.write_targets:
        _add_edge(edges, "job:KWDW_ACC", "file:DWACC", "writes")
    if "DWOUT" in bal_program.write_targets:
        _add_edge(edges, "job:KWDW_ACCBAL", "file:ACCBAL.TXT", "writes", file_handle="DWOUT")

    for mapping in FIELD_MAPPINGS:
        field_id = f"field:{mapping['field']}"
        source_id = f"source:{mapping['source']}"
        is_candidate_key = mapping["confidence"] == "candidate_composite_key"
        _add_node(
            nodes,
            field_id,
            "business_field",
            name=mapping["field"],
            confidence=mapping["confidence"],
            hvr_param_status=mapping["hvr_param_status"],
            direct_snowflake_status="INFERRED",
        )
        _add_node(nodes, source_id, "source_field", locator=mapping["source"])
        source_file_id = "file:ACCOUNT" if mapping["source"].startswith("ACCOUNT") else "file:TRAN"
        _add_edge(edges, source_file_id, source_id, "contains_column")

        if is_candidate_key:
            split_id = "transform:Account_Index_ID:split"
            combine_id = "transform:Account_Index_ID:combine_candidate"
            candidate_id = "candidate_key:DWACC:CIS+PID"
            _add_node(nodes, split_id, "transformation", expression=mapping["transformation"], implemented_in="KWDW_ACC")
            _add_node(nodes, combine_id, "transformation", expression="Proposed composite: CIS + PID", confidence="unconfirmed")
            _add_node(nodes, candidate_id, "candidate_composite_key", extract="DWACC", business_name=mapping["field"], confidence="unconfirmed")
            _add_edge(edges, source_id, split_id, "input_to")
            _add_edge(edges, "job:KWDW_ACC", split_id, "implements")
            for position, part in enumerate(("CIS", "PID"), start=1):
                part_id = f"output:DWACC:{part}"
                _add_node(nodes, part_id, "extract_field", extract="DWACC", column_name=part, position=position)
                _add_edge(edges, "file:DWACC", part_id, "contains_column")
                _add_edge(edges, split_id, part_id, "produces")
                _add_edge(edges, part_id, combine_id, "input_to")
            _add_edge(edges, combine_id, candidate_id, "produces")
            _add_edge(edges, candidate_id, field_id, "candidate_mapping", confidence="unconfirmed", lineage_status="INFERRED")
            for column_name, position in zip(mapping["parquet_columns"], mapping["parquet_positions"]):
                parquet_column_id = f"column:DWACC.parquet:{column_name}"
                _add_node(nodes, parquet_column_id, "parquet_column", name=column_name, position=position, lineage_status="CONFIRMED")
                _add_edge(edges, "dataset:DWACC.parquet", parquet_column_id, "contains_column", lineage_status="CONFIRMED")
                part_name = "CIS" if column_name == "Account" else "PID"
                _add_edge(
                    edges,
                    "config:DWACC.param",
                    parquet_column_id,
                    "defines_column",
                    lineage_status="CONFIRMED",
                    position=position,
                )
                _add_edge(
                    edges,
                    f"output:DWACC:{part_name}",
                    parquet_column_id,
                    "positionally_named_as",
                    lineage_status="CONFIRMED",
                    parameter_file="DWACC.param",
                    position=position,
                )
                _add_edge(edges, parquet_column_id, combine_id, "candidate_key_part", position=position, lineage_status="INFERRED")
        else:
            transform_id = f"transform:{mapping['field']}"
            output_id = f"output:{mapping['output']}:{mapping['field']}"
            column_name = {
                "Account_Opened_Date": "ACCOUNT OPENDATE",
                "Account_Name": "Account Name",
                "Signatory_Count": "NUM OF SIGNATURES REQUIRED",
                "Account_ID": "KIWIBANK ACCOUNT ID",
                "Balance": "EOD BALANCE",
            }[mapping["field"]]
            _add_node(nodes, transform_id, "transformation", expression=mapping["transformation"], implemented_in="KWDW_ACC")
            _add_node(
                nodes,
                output_id,
                "extract_field",
                extract=mapping["output"],
                column_name=column_name,
                business_name=mapping["field"],
                ordinal=mapping["parquet_position"],
                evidence=mapping["evidence"],
            )
            _add_edge(edges, source_id, transform_id, "input_to")
            _add_edge(edges, "job:KWDW_ACC", transform_id, "implements")
            _add_edge(edges, transform_id, output_id, "produces")
            _add_edge(edges, "file:DWACC", output_id, "contains_column")
            _add_edge(edges, output_id, field_id, "maps_to", confidence=mapping["confidence"])
            parquet_column_id = f"column:DWACC.parquet:{mapping['parquet_column']}"
            _add_node(
                nodes,
                parquet_column_id,
                "parquet_column",
                name=mapping["parquet_column"],
                position=mapping["parquet_position"],
                lineage_status=mapping["hvr_param_status"],
            )
            _add_edge(edges, "dataset:DWACC.parquet", parquet_column_id, "contains_column", lineage_status="CONFIRMED")
            _add_edge(
                edges,
                "config:DWACC.param",
                parquet_column_id,
                "defines_column",
                lineage_status="CONFIRMED",
                position=mapping["parquet_position"],
            )
            _add_edge(
                edges,
                output_id,
                parquet_column_id,
                "positionally_named_as",
                lineage_status=mapping["hvr_param_status"],
                parameter_file="DWACC.param",
                position=mapping["parquet_position"],
            )
            _add_edge(edges, parquet_column_id, field_id, "maps_to", confidence=mapping["confidence"], lineage_status=mapping["hvr_param_status"])

        payload_column_id = "column:loadaccounts_ingest:payload"
        direct_source_outputs = ("output:DWACC:CIS", "output:DWACC:PID") if is_candidate_key else (output_id,)
        for source_output_id in direct_source_outputs:
            _add_edge(
                edges,
                source_output_id,
                "channel:ult_sf_acc",
                "carried_by_row_pattern",
                lineage_status="INFERRED",
                capture_pattern=capture_pattern(sf_channel),
            )
            _add_edge(
                edges,
                source_output_id,
                payload_column_id,
                "serialized_into_raw_payload",
                lineage_status="INFERRED",
                note="The HVR Snowflake table defines a row payload, not this individual business column.",
            )

    _add_node(nodes, "output:ACCBAL.TXT:Account_ID", "extract_field", extract="ACCBAL.TXT", position=4, expression="REC<4,8>")
    _add_node(nodes, "output:ACCBAL.TXT:Balance", "extract_field", extract="ACCBAL.TXT", position=5, expression="OCONV(REC<1>,'MD2')")
    _add_edge(edges, "file:ACCBAL.TXT", "output:ACCBAL.TXT:Account_ID", "contains_field")
    _add_edge(edges, "file:ACCBAL.TXT", "output:ACCBAL.TXT:Balance", "contains_field")
    _add_edge(edges, "job:KWDW_ACCBAL", "output:ACCBAL.TXT:Account_ID", "emits")
    _add_edge(edges, "job:KWDW_ACCBAL", "output:ACCBAL.TXT:Balance", "emits")
    _add_edge(edges, "source:TRAN<4,8>", "output:ACCBAL.TXT:Account_ID", "maps_to")
    _add_edge(edges, "source:TRAN<1>", "output:ACCBAL.TXT:Balance", "formats_as", rule="OCONV(REC<1>,'MD2')")

    _add_edge(edges, "config:ult_sf_acc.json", "channel:ult_sf_acc", "defines_channel", lineage_status="CONFIRMED")
    _add_edge(
        edges,
        "file:DWACC",
        "channel:ult_sf_acc",
        "captured_by",
        lineage_status="INFERRED",
        pattern=capture_pattern(sf_channel),
    )
    _add_edge(edges, "location:fs_ultracs", "channel:ult_sf_acc", "source_location", lineage_status="CONFIRMED")
    _add_edge(edges, "channel:ult_sf_acc", "location:sf_lnd_ultra", "integrates_to", lineage_status="CONFIRMED")
    _add_edge(edges, "channel:ult_sf_acc", "table:loadaccounts_ingest", "loads", lineage_status="CONFIRMED")
    _add_edge(edges, "table:loadaccounts_ingest", "column:loadaccounts_ingest:payload", "contains_column", lineage_status="CONFIRMED")
    _add_edge(edges, "table:loadaccounts_ingest", "column:loadaccounts_ingest:integration_timestamp", "contains_column", lineage_status="CONFIRMED")

    _add_edge(edges, "config:ult_s3_acc1.json", "channel:ult_s3_acc1", "defines_channel", lineage_status="CONFIRMED")
    _add_edge(
        edges,
        "file:DWACC",
        "channel:ult_s3_acc1",
        "captured_by",
        lineage_status="INFERRED",
        pattern=capture_pattern(s3_channel_1),
    )
    _add_edge(edges, f"location:{s3_source_location}", "channel:ult_s3_acc1", "source_location", lineage_status="CONFIRMED")
    _add_edge(edges, "channel:ult_s3_acc1", "transform:src_to_parquet", "invokes", lineage_status="CONFIRMED")
    _add_edge(edges, "transform:src_to_parquet", "dataset:DWACC.parquet", "converts_to", lineage_status="CONFIRMED")
    _add_edge(edges, "dataset:DWACC.parquet", f"location:{s3_conversion_location}", "written_to", lineage_status="CONFIRMED")
    _add_edge(edges, "config:DWACC.param", "transform:src_to_parquet", "configures", lineage_status="CONFIRMED")
    _add_edge(edges, "transform:src_to_parquet", "dataset:DWACC.parquet", "uses_schema", lineage_status="CONFIRMED", parameter_file="DWACC.param")
    _add_edge(edges, "config:ult_s3_acc2.json", "channel:ult_s3_acc2", "defines_channel", lineage_status="CONFIRMED")
    _add_edge(edges, f"location:{s3_conversion_location}", "channel:ult_s3_acc2", "source_location", lineage_status="CONFIRMED")
    _add_edge(
        edges,
        "dataset:DWACC.parquet",
        "channel:ult_s3_acc2",
        "captured_by",
        lineage_status="INFERRED",
        pattern=s3_target_pattern,
    )
    _add_edge(
        edges,
        "channel:ult_s3_acc2",
        f"location:{s3_target_location}",
        "integrates_to",
        lineage_status="CONFIRMED",
        target_path=s3_rename,
    )

    return GraphPayload(nodes=nodes, edges=edges)
