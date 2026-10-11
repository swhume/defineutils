import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from defineutils.definehtml import DefineHtml
from defineutils.definehtml import __main__ as definehtml_cli


def data_path() -> Path:
    return Path(__file__).parent


def _run_cli(*cli_args) -> subprocess.CompletedProcess:
    """Run `python -m defineutils.definehtml` from the repo root so the package resolves
    whether or not it is installed."""
    return subprocess.run([sys.executable, "-m", "defineutils.definehtml", *cli_args],
                          capture_output=True, cwd=str(data_path().parent))


@pytest.fixture
def define_copy(tmp_path: Path) -> Path:
    define = tmp_path / "study.xml"
    shutil.copy(data_path() / "define.xml", define)
    return define


def test_cli_writes_the_html_beside_the_define_by_default(define_copy: Path):
    completed = _run_cli("-d", str(define_copy))

    assert completed.returncode == 0
    assert completed.stderr == b""
    assert "</html>" in define_copy.with_suffix(".html").read_text(encoding="utf-8")


def test_cli_writes_the_html_to_out(define_copy: Path, tmp_path: Path):
    out_file = tmp_path / "rendered.html"

    completed = _run_cli("-d", str(define_copy), "-o", str(out_file))

    assert completed.returncode == 0
    assert out_file.read_text(encoding="utf-8") == DefineHtml(define_copy).transform_to_html_string()
    assert not define_copy.with_suffix(".html").exists()


def test_cli_requires_define():
    completed = _run_cli()

    assert completed.returncode == 2
    assert b"-d/--define" in completed.stderr


def test_cli_missing_file_exits_2():
    completed = _run_cli("-d", "does_not_exist.xml")

    assert completed.returncode == 2
    assert b"not found" in completed.stderr
    assert completed.stdout == b""
    assert b"Traceback" not in completed.stderr


def test_cli_malformed_file_exits_2(tmp_path: Path):
    bad_xml = tmp_path / "bad.xml"
    bad_xml.write_text("<ODM><broken></ODM>", encoding="utf-8")

    completed = _run_cli("-d", str(bad_xml))

    assert completed.returncode == 2
    assert b"python -m defineutils.validate" in completed.stderr
    assert b"Traceback" not in completed.stderr
    assert not bad_xml.with_suffix(".html").exists()


def test_cli_out_that_is_the_define_exits_2_and_leaves_it_unchanged(define_copy: Path):
    before = define_copy.read_bytes()

    completed = _run_cli("-d", str(define_copy), "-o", str(define_copy))

    assert completed.returncode == 2
    assert b"would overwrite it" in completed.stderr
    assert define_copy.read_bytes() == before


def test_cli_stylesheet_options(define_copy: Path):
    completed = _run_cli("-d", str(define_copy), "--comments-table", "--no-methods-table",
                         "--prefixes", "--length-format", "--codelist-items", "999")

    html_text = define_copy.with_suffix(".html").read_text(encoding="utf-8")
    assert completed.returncode == 0
    assert 'id="comment"' in html_text
    assert 'id="compmethod"' not in html_text
    assert "[Comment]" in html_text
    assert "Length [SignificantDigits] : Display Format" in html_text
    assert "Terms]" not in html_text


def test_cli_invalid_codelist_items_exits_2(define_copy: Path):
    completed = _run_cli("-d", str(define_copy), "--codelist-items", "-1")

    assert completed.returncode == 2
    assert b"non-negative integer" in completed.stderr
    assert b"Traceback" not in completed.stderr


def test_cli_unexpected_error_returns_1_with_a_traceback(define_copy: Path, monkeypatch, capsys):
    def crash(self, html_file):
        raise RuntimeError("simulated defect")

    monkeypatch.setattr(DefineHtml, "transform_to_html_file", crash)
    monkeypatch.setattr(sys, "argv", ["definehtml", "-d", str(define_copy)])

    assert definehtml_cli.main() == 1
    stderr = capsys.readouterr().err
    assert "Traceback" in stderr
    assert "RuntimeError: simulated defect" in stderr
