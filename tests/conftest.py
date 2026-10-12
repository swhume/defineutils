"""Fixtures shared by the tests."""
import itertools
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from lxml import etree, html

from defineutils.definehtml import DefineHtml

DATA = Path(__file__).parent

# each command, and the module python -m runs for it
COMMANDS = {"definehtml": "defineutils.definehtml",
            "definevalidate": "defineutils.validate",
            "definepp": "defineutils.definepp",
            "definerefs": "defineutils.definerefs",
            "definemetrics": "defineutils.metrics"}


@pytest.fixture
def cli_command():
    """
    returns command(name): the argv that starts the named command. By default that is
    python -m <module>, which resolves from the repo root whether or not the package is installed.
    When the DEFINEUTILS_BIN environment variable names a folder of commands -- the installed
    console scripts, or a frozen build -- the command in that folder is run instead
    """
    def command(name: str) -> list[str]:
        bin_dir = os.environ.get("DEFINEUTILS_BIN")
        if not bin_dir:
            return [sys.executable, "-m", COMMANDS[name]]
        found = shutil.which(name, path=bin_dir)
        if found is None:
            pytest.fail(f"{name} was not found in DEFINEUTILS_BIN={bin_dir}")
        return [found]

    return command


@pytest.fixture
def run_cli(cli_command):
    """returns run(name, *args): runs the named command from the repo root, capturing its output"""
    def run(name: str, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run([*cli_command(name), *args], capture_output=True, cwd=str(DATA.parent))

    return run


@pytest.fixture
def run_module():
    """
    returns run(name, *args): runs the named command's module with python -m from the repo root, in UTF-8 mode as
    the frozen build runs. It is the reference the DEFINEUTILS_BIN commands are compared with, so it ignores
    DEFINEUTILS_BIN; every other CLI test uses run_cli
    """
    def run(name: str, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, "-X", "utf8", "-m", COMMANDS[name], *args], capture_output=True,
                              cwd=str(DATA.parent))

    return run


@pytest.fixture
def edited_define(tmp_path):
    """
    returns make(edit, source): writes a copy of a test define.xml to tmp_path after edit(tree)
    changes it with lxml, and returns its path. Synthetic test files are built this way rather
    than committed
    """
    counter = itertools.count(1)

    def make(edit=None, source: Path = DATA / "define.xml") -> Path:
        tree = etree.parse(str(source))
        if edit is not None:
            edit(tree)
        path = tmp_path / f"edited-{next(counter)}-{Path(source).name}"
        tree.write(str(path), xml_declaration=True, encoding="utf-8")
        return path

    return make


@pytest.fixture
def render():
    """returns render(path, **options): the define.xml rendered by DefineHtml and parsed as HTML"""
    def render_html(path: Path, **options) -> html.HtmlElement:
        return html.fromstring(DefineHtml(path, **options).transform_to_html_string())

    return render_html
