import json
import subprocess
import sys
from pathlib import Path
import pytest

from retry_sequence_check.cli import _InvalidInput, _result


def write(tmp_path, content):
    path = tmp_path / "fixture.jsonl"
    path.write_bytes(content)
    return str(path)


def test_observed_sequence_semantics(tmp_path):
    for attempts, expected in [([2, 3], [1]), ([1, 3, 4], [2]), ([2, 1], [1, 2])]:
        rows = b"".join(json.dumps({"id": f"e{i}", "operation": "op", "attempt": n}).encode() + b"\n"
                        for i, n in enumerate(attempts))
        assert _result(write(tmp_path, rows))[0]["issue_lines"] == expected


def test_interleaving_and_unicode_delimiters(tmp_path):
    path = write(tmp_path, ('{"id":"α","operation":"a","attempt":1}\r\n'
                            '{"id":"b","operation":"b","attempt":1}\n'
                            '{"id":"c","operation":"a","attempt":2}').encode())
    assert _result(path) == ({"status": "valid", "record_count": 3, "issue_lines": []}, 0)

    bare_cr = write(tmp_path, b'{"id":"d","operation":"a","attempt":1}\r{"id":"e","operation":"a","attempt":2}')
    assert _result(bare_cr)[0]["record_count"] == 2

    separator_in_string = write(tmp_path, '{"id":"f","operation":"a\\u2028b","attempt":1}'.encode())
    assert _result(separator_in_string)[0]["status"] == "valid"


def test_invalid_inputs_and_private_output(tmp_path):
    for raw in [b"\xff", b"\n", b'{"id":"x","id":"y","operation":"o","attempt":1}\n',
                b'{"id":"\\ud800","operation":"o","attempt":1}\n',
                b'{"id":"x","operation":"o","attempt":true}\n',
                b'{"id":"x","operation":"o","attempt":1}\n\n']:
        path = write(tmp_path, raw)
        proc = subprocess.run([sys.executable, "-m", "retry_sequence_check", path],
                              capture_output=True, text=True)
        assert proc.returncode == 2
        assert proc.stdout == '{"status":"invalid_input"}\n'
        assert proc.stderr == ""
        assert "x" not in proc.stdout and path not in proc.stdout


def test_nonfinite_surrogates_blank_and_late_invalid_are_atomic(tmp_path):
    valid = b'{"id":"ordinary","operation":"op","attempt":1}\n'
    cases = [b'{"id":"x","operation":"o","attempt":NaN}\n',
             b'{"id":"x","operation":"o","attempt":Infinity}\n',
             valid + b'{"id":"later","operation":"o","attempt":2,"extra":"\\udfff"}\n',
             valid + b'{"id":"later","operation":"o","attempt":2}\n\n']
    for raw in cases:
        path = write(tmp_path, raw)
        proc = subprocess.run([sys.executable, "-m", "retry_sequence_check", path],
                              capture_output=True, text=True)
        assert proc.returncode == 2 and proc.stdout == '{"status":"invalid_input"}\n'
        assert proc.stderr == "" and "ordinary" not in proc.stdout

    deep = b'{"id":"d","operation":"o","attempt":1,"extra":' + b"[" * 1500 + b"0" + b"]" * 1500 + b"}\n"
    assert _invalid_subprocess(tmp_path, deep)


def _invalid_subprocess(tmp_path, raw):
    path = write(tmp_path, raw)
    proc = subprocess.run([sys.executable, "-m", "retry_sequence_check", path],
                          capture_output=True, text=True)
    return proc.returncode == 2 and proc.stdout == '{"status":"invalid_input"}\n' and proc.stderr == ""


def test_duplicate_event_and_pair_are_invalid(tmp_path):
    for rows in [
        [{"id": "x", "operation": "o", "attempt": 1}, {"id": "x", "operation": "p", "attempt": 1}],
        [{"id": "x", "operation": "o", "attempt": 1}, {"id": "y", "operation": "o", "attempt": 1}],
    ]:
        path = write(tmp_path, b"".join(json.dumps(row).encode() + b"\n" for row in rows))
        with pytest.raises(_InvalidInput):
            _result(path)


def test_empty_file_is_valid(tmp_path):
    assert _result(write(tmp_path, b"")) == ({"status": "valid", "record_count": 0, "issue_lines": []}, 0)


def test_startup_gap_and_decrease(tmp_path):
    path = write(tmp_path, b'{"id":"a","operation":"op","attempt":4}\n'
                           b'{"id":"b","operation":"op","attempt":7}\n'
                           b'{"id":"c","operation":"op","attempt":5}\n')
    assert _result(path)[0]["issue_lines"] == [1, 2, 3]
