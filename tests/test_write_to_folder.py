"""
Writing a report to a folder is reported as a folder on every platform. Windows raises PermissionError there rather
than IsADirectoryError, so these tests make each module's open() raise PermissionError as Windows does, which runs that
branch on macOS and Linux too. The tests writing to a real folder are in each module's own test file.
"""
import importlib
from pathlib import Path

import pytest

from defineutils.definepp import DefinePrettyPrinter, DefinePrettyPrintError
from defineutils.definerefs import DefineRefChecker, DefineRefCheckError
from defineutils.metrics import DefineMetrics, DefineMetricsError
from defineutils.validate import DefineSchemaLoadError, DefineSchemaValidator

DEFINE = Path(__file__).parent / "define.xml"

# each module that writes a report with open(), a function writing its report to a path, and the error it raises
WRITERS = [
    pytest.param("defineutils.definepp.definepp", lambda path: DefinePrettyPrinter(DEFINE).pretty_print_to_file(path),
                 DefinePrettyPrintError, id="definepp"),
    pytest.param("defineutils.definerefs.definerefs", lambda path: DefineRefChecker(DEFINE).check_to_file(path),
                 DefineRefCheckError, id="definerefs"),
    pytest.param("defineutils.metrics.metrics", lambda path: DefineMetrics(DEFINE).collect_to_file(path),
                 DefineMetricsError, id="metrics"),
    pytest.param("defineutils.validate.validate", lambda path: DefineSchemaValidator(DEFINE).validate_to_file(path),
                 DefineSchemaLoadError, id="validate"),
]


def _windows_open(file, *args, **kwargs):
    """open() as it fails on Windows for a folder, and for a file the user may not write"""
    raise PermissionError(13, "Permission denied", str(file))


@pytest.mark.parametrize("module, write, error", WRITERS)
def test_folder_is_reported_when_open_raises_permission_error(module, write, error, tmp_path, monkeypatch):
    monkeypatch.setattr(importlib.import_module(module), "open", _windows_open, raising=False)

    with pytest.raises(error, match="write to a directory"):
        write(tmp_path)


@pytest.mark.parametrize("module, write, error", WRITERS)
def test_file_permission_error_is_reported_as_one(module, write, error, tmp_path, monkeypatch):
    monkeypatch.setattr(importlib.import_module(module), "open", _windows_open, raising=False)

    with pytest.raises(error, match="Permission error attempting to write to"):
        write(tmp_path / "report.txt")
