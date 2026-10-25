import json
from pathlib import Path

import pytest
import yaml

from lineage_poc.parsers.snapshot import REQUIRED_REPOSITORIES

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def source_factory(tmp_path):
    def create(name="sources", description="Māori account\nsecond line"):
        root = tmp_path / name
        for repository in REQUIRED_REPOSITORIES:
            (root / repository).mkdir(parents=True)
        warehouse = root / "kb-ultracs-datawarehouse"
        program = (FIXTURES / "KWDW_SAMPLE").read_text(encoding="utf-8").replace("KWDW_SAMPLE", "KWDW_ACC")
        (warehouse / "KWDW_ACC").write_bytes(program.replace("\n", "\r\n").encode("utf-8"))
        ignored = warehouse / ".git" / "ignored"
        ignored.parent.mkdir()
        ignored.write_text("not source evidence", encoding="utf-8")
        parameters = root / "kb-cdp-hvr" / "hvr-config" / "scripts" / "DWACC.param"
        parameters.parent.mkdir(parents=True)
        parameters.write_text(
            json.dumps({"data_source": "Ultracs", "delim": "|", "columns": {"KiwiAcc": {"data_type": "string"}}}),
            encoding="utf-8",
        )
        channels = parameters.parents[1] / "apps" / "channels"
        channels.mkdir(parents=True)
        (channels / "fixture.json").write_bytes((FIXTURES / "channel.json").read_bytes())
        product = root / "kb-cdp-tenant-account" / "products" / "accounts-v1"
        dbt = product / "dbt"
        dbt.mkdir(parents=True)
        project = yaml.safe_load((FIXTURES / "dbt" / "dbt_project.yml").read_text(encoding="utf-8"))
        (dbt / "dbt_project.yml").write_text(yaml.safe_dump(project), encoding="utf-8")
        for suffix in ("detail", "eod_balances"):
            internal = f"accounts_v1__ultracs_accounts_{suffix}_v2"
            public = f"accounts_v1__ultracs_accounts_{suffix}"
            for stage, model in (("internal", internal), ("public", public)):
                folder = dbt / "models" / stage / model
                folder.mkdir(parents=True)
                sql = (
                    "SELECT\n    DATA:KiwiAcc::VARCHAR(100) AS KIWIBANKACCOUNTNUMBER\n"
                    "FROM {{ source('account_raw_source', 'ACCOUNTS_V1__ACCOUNTS') }}\n"
                    if stage == "internal"
                    else "SELECT\n    KIWIBANKACCOUNTNUMBER\nFROM {{ ref('" + internal + "') }}\n"
                )
                (folder / f"{model}.sql").write_text(sql, encoding="utf-8")
                schema = {
                    "version": 2,
                    "models": [{"name": model, "description": description, "config": {
                        "schema": stage.upper(), "materialized": "incremental" if stage == "internal" else "view",
                    }, "columns": [
                        {"name": "KIWIBANKACCOUNTNUMBER", "description": description, "data_type": "VARCHAR(100)"}
                    ]}],
                }
                if stage == "internal":
                    schema["sources"] = [{"name": "account_raw_source", "schema": "RAW", "tables": [{"name": "ACCOUNTS_V1__ACCOUNTS"}]}]
                (folder / f"{model}.yml").write_text(yaml.safe_dump(schema, allow_unicode=True), encoding="utf-8")
        dag = product / "airflow" / "accounts_v1" / "src" / "dags" / "accounts_v1_ingestion_v1.py"
        dag.parent.mkdir(parents=True)
        dag.write_text(
            'file_and_table_names = {"dwacc": "ACCOUNTS_V1__ACCOUNTS"}\nraise RuntimeError("DAG source must not execute")\n',
            encoding="utf-8",
        )
        return root

    return create
