"""The defineutils commands: their console-script entry points, and the run() each one calls."""
import importlib
import sys
from importlib import metadata

import pytest

from defineutils import __version__

# each command, and the module holding the run() its console script calls
ENTRY_MODULES = {"definehtml": "defineutils.definehtml.__main__",
                 "definevalidate": "defineutils.validate.__main__",
                 "definepp": "defineutils.definepp.__main__",
                 "definerefs": "defineutils.definerefs.__main__",
                 "definemetrics": "defineutils.metrics.__main__"}

# the commands that print a report to the console, so can meet a pager that quits early
PAGED = ["definevalidate", "definepp", "definerefs", "definemetrics"]


def _installed():
    try:
        return metadata.distribution("defineutils")
    except metadata.PackageNotFoundError:
        pytest.skip("defineutils is not installed")


def _cli(name: str, monkeypatch):
    """the command's module, with os._exit swapped for sys.exit so run() can be called in-process"""
    module = importlib.import_module(ENTRY_MODULES[name])
    if hasattr(module, "_quiet_exit"):
        monkeypatch.setattr(module, "_quiet_exit", sys.exit)
    return module


def test_each_command_is_a_console_script_that_calls_run():
    scripts = {ep.name: ep for ep in _installed().entry_points if ep.group == "console_scripts"}

    assert {name: ep.value for name, ep in scripts.items()} == \
           {name: f"{module}:run" for name, module in ENTRY_MODULES.items()}, \
           "the installed metadata is stale; re-run pip install -e ."
    for name, ep in scripts.items():
        assert ep.load() is importlib.import_module(ENTRY_MODULES[name]).run


def test_the_installed_version_is_the_package_version():
    # --version prints defineutils.__version__, so it must match the version that was installed
    assert _installed().version == __version__, "the installed metadata is stale; re-run pip install -e ."


@pytest.mark.parametrize("name", ENTRY_MODULES)
def test_version_flag(name, run_cli):
    completed = run_cli(name, "--version")

    assert completed.returncode == 0
    assert completed.stdout.decode().strip() == f"{name} {__version__}"


@pytest.mark.parametrize("name", ENTRY_MODULES)
def test_help_names_the_command(name, run_cli):
    completed = run_cli(name, "--help")

    assert completed.returncode == 0
    assert completed.stdout.decode().startswith(f"usage: {name} ")


@pytest.mark.parametrize("name", [name for name in ENTRY_MODULES if name != "definepp"])
def test_run_exits_with_the_code_main_returns(name, monkeypatch):
    # definepp is left out: its main() returns nothing, so it always exits 0
    module = _cli(name, monkeypatch)
    monkeypatch.setattr(module, "main", lambda: 2)

    with pytest.raises(SystemExit) as excinfo:
        module.run()
    assert excinfo.value.code == 2


@pytest.mark.parametrize("name", ENTRY_MODULES)
def test_run_exits_130_on_ctrl_c(name, monkeypatch):
    def interrupted():
        raise KeyboardInterrupt

    module = _cli(name, monkeypatch)
    monkeypatch.setattr(module, "main", interrupted)

    with pytest.raises(SystemExit) as excinfo:
        module.run()
    assert excinfo.value.code == 130


@pytest.mark.parametrize("name", PAGED)
def test_run_exits_0_when_the_pager_closes(name, monkeypatch):
    def closed_pipe():
        raise BrokenPipeError

    module = _cli(name, monkeypatch)
    monkeypatch.setattr(module, "main", closed_pipe)

    with pytest.raises(SystemExit) as excinfo:
        module.run()
    assert excinfo.value.code == 0
