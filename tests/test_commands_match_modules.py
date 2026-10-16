"""
With DEFINEUTILS_BIN naming a folder of commands -- the installed console scripts, or a frozen build -- each command
must behave as python -m does on the test files: the same exit code, stdout and stderr, and byte-identical HTML.
Skipped when DEFINEUTILS_BIN is not set, since python -m would then be compared with itself.
"""
import json
import os
import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(not os.environ.get("DEFINEUTILS_BIN"),
                                reason="compares the DEFINEUTILS_BIN commands with python -m")

DEFINES = ["define.xml", "define-adam.xml"]

# each report command, with the options that change what it prints
REPORTS = [("definevalidate",), ("definevalidate", "--json"), ("definepp",), ("definerefs",),
           ("definerefs", "--json"), ("definemetrics",), ("definemetrics", "--json"), ("defineconform",),
           ("defineconform", "--json")]

# the tail of the schema path definevalidate loads by default, wherever its install or bundle is
DEFAULT_SCHEMA = ("defineutils", "validate", "schema", "cdisc-define-2.1", "define2-1-0.xsd")

SCHEMA_LINE = re.compile(rb"^  Schema: (.*?)\r?$", re.MULTILINE)


def data_path() -> Path:
    return Path(__file__).parent


def _without_schema(stdout: bytes, as_json: bool) -> tuple:
    """a validate report without the schema path, which names each install's own copy, and that path"""
    if as_json:
        report = json.loads(stdout)
        return report, report.pop("schema_file")
    return SCHEMA_LINE.sub(b"", stdout), SCHEMA_LINE.search(stdout).group(1).decode()


@pytest.mark.parametrize("define", DEFINES)
def test_definehtml_writes_the_same_html(define, tmp_path, run_cli, run_module):
    command = run_cli("definehtml", "-d", str(data_path() / define), "-o", str(tmp_path / "command.html"))
    module = run_module("definehtml", "-d", str(data_path() / define), "-o", str(tmp_path / "module.html"))

    assert command.returncode == module.returncode == 0
    assert (command.stdout, command.stderr) == (module.stdout, module.stderr)
    assert (tmp_path / "command.html").read_bytes() == (tmp_path / "module.html").read_bytes()


@pytest.mark.parametrize("define", DEFINES)
def test_defineview_writes_the_same_html(define, tmp_path, run_cli, run_module):
    # exit codes and files only: the windowed Windows build may have no stdout or stderr
    command = run_cli("defineview", "--no-open", "-o", str(tmp_path / "command.html"), str(data_path() / define))
    module = run_module("defineview", "--no-open", "-o", str(tmp_path / "module.html"), str(data_path() / define))

    assert command.returncode == module.returncode == 0
    assert (tmp_path / "command.html").read_bytes() == (tmp_path / "module.html").read_bytes()


@pytest.mark.parametrize("define", DEFINES)
@pytest.mark.parametrize("report", REPORTS, ids=" ".join)
def test_reports_match(define, report, run_cli, run_module):
    name, *options = report
    args = ["-d", str(data_path() / define), *options]

    command = run_cli(name, *args)
    module = run_module(name, *args)

    assert command.returncode == module.returncode
    assert command.stderr == module.stderr
    if name != "definevalidate":
        assert command.stdout == module.stdout
        return
    command_report, schema = _without_schema(command.stdout, "--json" in options)
    module_report, _ = _without_schema(module.stdout, "--json" in options)
    assert command_report == module_report
    # the command found the bundled schema in its own install or bundle
    assert Path(schema).parts[-len(DEFAULT_SCHEMA):] == DEFAULT_SCHEMA
    assert Path(schema).is_file()
