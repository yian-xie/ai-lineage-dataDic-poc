from pathlib import Path

from lineage_poc.parsers.ultracs_basic import parse_ultracs_basic, parse_ultracs_record


SAMPLE_PROGRAM = '''
* KWDW_ACC
* OPEN 'COMMENTED_OUT' TO IGNORED
OPEN 'TRAN' TO TRAN ELSE STOP
OPEN 'ACCOUNT' TO ACCOUNT ELSE STOP
SELECT ACCOUNT
10: READNEXT ID ELSE GO 20
READ REC FROM TRAN,ID ELSE GO 10
LINE = CIS:SEP:PID:SEP:OCONV(REC<1>,'MD2')
WRITESEQ LINE ON DWACC ELSE STOP
EXECUTE "NEXT_JOB"
'''


def test_parse_ultracs_basic_extracts_file_ops_and_tasks():
    program = parse_ultracs_basic(SAMPLE_PROGRAM)

    assert program.name == "KWDW_ACC"
    assert "TRAN" in program.open_files
    assert "ACCOUNT" in program.open_files
    assert "COMMENTED_OUT" not in program.open_files
    assert "DWACC" in program.write_targets
    assert "SELECT ACCOUNT" in program.operations
    assert program.has_statement("READNEXT") is True
    assert program.has_statement("EXECUTE") is True


def test_parse_ultracs_record_splits_pipe_delimited_records():
    record = "S123|L001|1000.00|ACTIVE|2024-05-01"
    parsed = parse_ultracs_record(record)

    assert parsed == ["S123", "L001", "1000.00", "ACTIVE", "2024-05-01"]
