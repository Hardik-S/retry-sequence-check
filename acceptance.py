"""Installed-wheel smoke check used by CI and release review."""

from __future__ import annotations

import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sysconfig
import tempfile


def main() -> int:
    dist = importlib.metadata.distribution("retry-sequence-check")
    assert dist.version == "0.1.0", dist.version
    scripts = Path(sysconfig.get_path("scripts"))
    executable = scripts / ("retry-sequence-check.exe" if os.name == "nt" else "retry-sequence-check")
    assert executable.is_file(), str(executable)

    fixture = Path(__file__).parent / "examples" / "valid.jsonl"
    result = subprocess.run([str(executable), str(fixture)], capture_output=True, text=True, check=False)
    assert result.returncode == 0, (result.returncode, result.stderr)
    assert json.loads(result.stdout) == {"status": "valid", "record_count": 3, "issue_lines": []}
    help_result = subprocess.run([str(executable), "--help"], capture_output=True, text=True, check=False)
    assert help_result.returncode == 0 and "usage:" in help_result.stdout and not help_result.stderr

    with tempfile.TemporaryDirectory() as scratch:
        scratch_path = Path(scratch)
        sequence = scratch_path / "sequence.jsonl"
        sequence.write_text('{"id":"private-event","operation":"private-op","attempt":1}\n'
                            '{"id":"private-event-2","operation":"private-op","attempt":3}\n', encoding="utf-8")
        issue = subprocess.run([str(executable), str(sequence)], capture_output=True, text=True, check=False)
        assert issue.returncode == 1 and json.loads(issue.stdout) == {
            "status": "sequence_issues", "record_count": 2, "issue_lines": [2]}
        invalid_file = scratch_path / "private-path-invalid.jsonl"
        invalid_file.write_text('{"id":"do-not-disclose","operation":"bad","attempt":true}\n', encoding="utf-8")
        invalid = subprocess.run([str(executable), str(invalid_file)], capture_output=True, text=True, check=False)
        assert invalid.returncode == 2 and invalid.stdout == '{"status":"invalid_input"}\n'
        assert invalid.stderr == "" and "do-not-disclose" not in invalid.stdout
        assert str(invalid_file) not in invalid.stdout
        for argv in ([], [str(sequence), "extra"], ["--unknown"]):
            usage = subprocess.run([str(executable), *argv], capture_output=True, text=True, check=False)
            assert usage.returncode == 2 and usage.stdout == '{"status":"invalid_input"}\n' and not usage.stderr

    module = importlib.util.find_spec("retry_sequence_check")
    assert module is not None and module.origin
    assert Path(module.origin).resolve().is_relative_to(Path(dist.locate_file("retry_sequence_check")).resolve())
    print("installed package 0.1.0; console path via sysconfig; exit 0/1/2, help, privacy, and fixture PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
