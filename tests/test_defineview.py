"""
defineview: renders a define.xml, writes the HTML beside it (or to the temp folder) and opens it in the browser. The
in-process tests record what would be opened rather than starting a browser; the CLI tests always pass --no-open, and
check exit codes and files only, since the windowed Windows build may have no stdout or stderr.
"""
import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

from defineutils import __version__
from defineutils.definehtml import DefineHtml
from defineutils.definehtml import definehtml as definehtml_module
from defineutils.defineview import DefineViewer, DefineViewError, open_in_browser
from defineutils.defineview import __main__ as defineview_cli
from defineutils.defineview import defineview as defineview_module

DATA = Path(__file__).parent


@pytest.fixture
def define_copy(tmp_path: Path) -> Path:
    """a copy of tests/define.xml, alone in its folder"""
    (tmp_path / "study").mkdir()
    define = tmp_path / "study" / "study.xml"
    shutil.copy(DATA / "define.xml", define)
    return define


@pytest.fixture
def temp(tmp_path: Path, monkeypatch) -> Path:
    """the temp folder defineview writes to, in place of the real one"""
    folder = tmp_path / "temp"
    folder.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(folder))
    return folder


@pytest.fixture
def opened(monkeypatch) -> list:
    """the pages defineview opens, recorded instead of opened"""
    pages = []
    monkeypatch.setattr(defineview_cli, "open_in_browser", pages.append)
    return pages


def _main(monkeypatch, *args: str) -> int:
    monkeypatch.setattr(sys, "argv", ["defineview", *args])
    return defineview_cli.main()


def _relative_html(define: Path, tmp_path: Path) -> bytes:
    """the HTML definehtml writes for define, with its links relative"""
    out_file = tmp_path / "reference.html"
    DefineHtml(define).transform_to_html_file(out_file)
    return out_file.read_bytes()


def _only_file(folder: Path) -> Path:
    files = [path for path in folder.rglob("*") if path.is_file()]
    assert len(files) == 1, files
    return files[0]


# where the HTML goes

def test_opens_the_html_written_beside_the_define(define_copy, temp, opened, tmp_path, monkeypatch):
    assert _main(monkeypatch, str(define_copy)) == 0

    html_file = define_copy.with_suffix(".html")
    assert opened == [html_file]
    assert html_file.read_bytes() == _relative_html(define_copy, tmp_path)
    assert not list(temp.iterdir())


def test_replaces_an_html_file_beside_the_define(define_copy, temp, opened, monkeypatch):
    define_copy.with_suffix(".html").write_text("an older page", encoding="utf-8")

    assert _main(monkeypatch, str(define_copy)) == 0

    assert "</html>" in define_copy.with_suffix(".html").read_text(encoding="utf-8")


def test_temp_writes_to_the_temp_folder_with_absolute_links(define_copy, temp, opened, monkeypatch):
    assert _main(monkeypatch, "--temp", str(define_copy)) == 0

    html_file = _only_file(temp)
    assert opened == [html_file]
    assert html_file == DefineViewer(define_copy).temp_folder / "study.html"
    assert f'href="{define_copy.parent.as_uri()}/acrf.pdf#page=' in html_file.read_text(encoding="utf-8")
    assert not define_copy.with_suffix(".html").exists()


def test_falls_back_to_temp_when_the_define_folder_cant_be_written(define_copy, temp, opened, monkeypatch):
    real_open = open

    def no_writing_beside_the_define(file, *args, **kwargs):
        if Path(file).parent == define_copy.parent:
            raise PermissionError(13, "Permission denied", str(file))
        return real_open(file, *args, **kwargs)

    monkeypatch.setattr(definehtml_module, "open", no_writing_beside_the_define, raising=False)

    assert _main(monkeypatch, str(define_copy)) == 0

    html_file = _only_file(temp)
    assert opened == [html_file]
    assert f'href="{define_copy.parent.as_uri()}/acrf.pdf#page=' in html_file.read_text(encoding="utf-8")
    assert not define_copy.with_suffix(".html").exists()


def test_out_file_in_another_folder_gets_absolute_links(define_copy, temp, opened, tmp_path, monkeypatch):
    out_file = tmp_path / "view.html"

    assert _main(monkeypatch, "-o", str(out_file), str(define_copy)) == 0

    assert opened == [out_file]
    assert f'href="{define_copy.parent.as_uri()}/acrf.pdf#page=' in out_file.read_text(encoding="utf-8")


def test_out_file_beside_the_define_keeps_relative_links(define_copy, temp, opened, tmp_path, monkeypatch):
    out_file = define_copy.parent / "view.html"

    assert _main(monkeypatch, "--no-open", "-o", str(out_file), str(define_copy)) == 0

    assert opened == []
    assert out_file.read_bytes() == _relative_html(define_copy, tmp_path)


def test_each_define_has_its_own_temp_folder(define_copy, temp):
    other = define_copy.parent.parent / "other" / define_copy.name

    folder = DefineViewer(define_copy).temp_folder

    assert folder.parent == temp / "defineutils"
    assert folder == DefineViewer(define_copy.parent / ".." / "study" / define_copy.name).temp_folder
    assert folder != DefineViewer(other).temp_folder


def test_temp_and_an_out_file_cant_be_combined(define_copy, tmp_path):
    with pytest.raises(DefineViewError, match="not both"):
        DefineViewer(define_copy, temp=True, out_file=tmp_path / "view.html")


# a define.xml that can't be shown opens a page saying why

def _not_well_formed(folder: Path) -> Path:
    path = folder / "broken.xml"
    path.write_text("<ODM><broken></ODM>", encoding="utf-8")
    return path


def _not_define_xml(folder: Path) -> Path:
    path = folder / "schema.xml"
    shutil.copy(DATA.parent / "defineutils" / "validate" / "schema" / "cdisc-define-2.1" / "define2-1-0.xsd", path)
    return path


@pytest.mark.parametrize("make, reason", [(lambda folder: folder / "missing.xml", "not found"),
                                          (_not_well_formed, "not well-formed XML"),
                                          (_not_define_xml, "not a Define-XML v2.1 document")],
                         ids=["missing", "not well-formed", "not Define-XML"])
def test_a_define_that_cant_be_shown_opens_an_error_page(make, reason, tmp_path, temp, opened, monkeypatch, capsys):
    (tmp_path / "study").mkdir()
    define = make(tmp_path / "study")

    assert _main(monkeypatch, str(define)) == 2

    page = DefineViewer(define).temp_folder / f"{define.stem}.error.html"
    assert opened == [page]
    text = page.read_text(encoding="utf-8")
    assert f"{define.name} could not be shown" in text
    assert reason in text
    assert reason in capsys.readouterr().err
    # nothing is written beside the define.xml, and the plain-XML link is offered when there is a file to show
    assert sorted(path.name for path in define.parent.iterdir()) == ([define.name] if define.exists() else [])
    assert (f'href="{define.as_uri()}"' in text) == define.exists()


def test_the_error_page_escapes_the_message(define_copy, temp):
    page = DefineViewer(define_copy).write_error_page("<script>alert(1)</script> & more")

    text = page.read_text(encoding="utf-8")
    assert "&lt;script&gt;alert(1)&lt;/script&gt; &amp; more" in text
    assert "<script>" not in text


def test_an_unexpected_error_opens_a_page_with_the_traceback(define_copy, temp, opened, monkeypatch, capsys):
    def crash(self):
        raise RuntimeError("simulated defect")

    monkeypatch.setattr(DefineViewer, "write_html", crash)

    assert _main(monkeypatch, str(define_copy)) == 1

    text = opened[0].read_text(encoding="utf-8")
    assert "failed unexpectedly" in text
    assert "RuntimeError: simulated defect" in text
    assert defineview_module.ISSUES in text
    assert "Traceback" in capsys.readouterr().err


def test_a_browser_that_wont_start_is_reported(define_copy, temp, monkeypatch, capsys):
    def no_browser(page):
        raise DefineViewError(f"No browser could be started to show {page}.")

    monkeypatch.setattr(defineview_cli, "open_in_browser", no_browser)

    assert _main(monkeypatch, str(define_copy)) == 2

    assert "No browser could be started" in capsys.readouterr().err


def test_an_error_page_that_cant_be_written_is_reported(tmp_path, opened, monkeypatch, capsys):
    # the temp folder is a file, so no folder can be made in it
    not_a_folder = tmp_path / "temp"
    not_a_folder.write_text("", encoding="utf-8")
    monkeypatch.setattr(tempfile, "tempdir", str(not_a_folder))

    assert _main(monkeypatch, str(tmp_path / "missing.xml")) == 2

    assert opened == []
    err = capsys.readouterr().err
    assert "not found" in err
    assert "Unable to write" in err


# without a console, as on Windows, messages go to a message box

@pytest.fixture
def message_boxes(monkeypatch) -> list:
    """the messages shown in a message box, as on Windows, recorded instead of shown"""
    shown = []
    monkeypatch.setattr(defineview_cli, "WINDOWS", True)
    monkeypatch.setattr(defineview_cli, "_message_box", shown.append)
    return shown


def _without_a_console(monkeypatch) -> None:
    """
    no stdout or stderr, as for the windowed Windows build. Called in the test itself: pytest's output capturing sets
    both again once the fixtures are set up
    """
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)


@pytest.mark.parametrize("args, code, message", [(["--version"], 0, f"defineview {__version__}"),
                                                 ([], 2, "usage: defineview"),
                                                 (["--temp", "-o", "x.html", "x.xml"], 2, "not allowed with")],
                         ids=["version", "no define", "usage error"])
def test_without_a_console_argparse_output_goes_to_a_message_box(message_boxes, monkeypatch, args, code, message):
    _without_a_console(monkeypatch)

    with pytest.raises(SystemExit) as excinfo:
        _main(monkeypatch, *args)

    assert excinfo.value.code == code
    assert len(message_boxes) == 1
    assert message in message_boxes[0]


def test_without_a_console_a_problem_with_no_page_goes_to_a_message_box(message_boxes, tmp_path, opened,
                                                                         monkeypatch):
    not_a_folder = tmp_path / "temp"
    not_a_folder.write_text("", encoding="utf-8")
    monkeypatch.setattr(tempfile, "tempdir", str(not_a_folder))
    _without_a_console(monkeypatch)

    assert _main(monkeypatch, str(tmp_path / "missing.xml")) == 2

    assert len(message_boxes) == 1
    assert "not found" in message_boxes[0]
    assert "Unable to write" in message_boxes[0]


def test_without_a_console_a_shown_page_needs_no_message_box(message_boxes, define_copy, temp, opened, monkeypatch):
    _without_a_console(monkeypatch)

    assert _main(monkeypatch, str(define_copy)) == 0

    assert message_boxes == []


def test_with_a_console_the_help_is_printed(monkeypatch, capsys):
    with pytest.raises(SystemExit) as excinfo:
        _main(monkeypatch)

    assert excinfo.value.code == 2
    assert capsys.readouterr().out.startswith("usage: defineview ")


# opening the page

def test_open_in_browser_opens_the_page_as_a_file_url(tmp_path, monkeypatch):
    urls = []
    monkeypatch.setattr(defineview_module.webbrowser, "open", lambda url: urls.append(url) or True)

    open_in_browser(tmp_path / "study.html")

    assert urls == [(tmp_path / "study.html").as_uri()]


def test_open_in_browser_reports_a_browser_that_wont_start(tmp_path, monkeypatch):
    monkeypatch.setattr(defineview_module.webbrowser, "open", lambda url: False)

    with pytest.raises(DefineViewError, match="No browser could be started"):
        open_in_browser(tmp_path / "study.html")


# the command, run as python -m, installed, or frozen (DEFINEUTILS_BIN); never opening a browser

@pytest.fixture
def temp_env(tmp_path: Path) -> tuple:
    """an environment whose temp folder is a new folder in tmp_path, and that folder"""
    folder = tmp_path / "temp"
    folder.mkdir()
    return {**os.environ, "TMPDIR": str(folder), "TEMP": str(folder), "TMP": str(folder)}, folder


def test_cli_writes_the_html_beside_the_define(define_copy, tmp_path, temp_env, run_cli):
    env, folder = temp_env

    completed = run_cli("defineview", "--no-open", str(define_copy), env=env)

    assert completed.returncode == 0
    assert define_copy.with_suffix(".html").read_bytes() == _relative_html(define_copy, tmp_path)
    assert not list(folder.iterdir())


def test_cli_temp_writes_to_the_temp_folder(define_copy, temp_env, run_cli):
    env, folder = temp_env

    completed = run_cli("defineview", "--no-open", "--temp", str(define_copy), env=env)

    assert completed.returncode == 0
    html_file = _only_file(folder)
    assert html_file.name == "study.html"
    assert f'href="{define_copy.parent.as_uri()}/acrf.pdf#page=' in html_file.read_text(encoding="utf-8")
    assert not define_copy.with_suffix(".html").exists()


def test_cli_writes_the_html_to_out(define_copy, tmp_path, run_cli):
    out_file = tmp_path / "view.html"

    completed = run_cli("defineview", "--no-open", "-o", str(out_file), str(define_copy))

    assert completed.returncode == 0
    assert out_file.read_text(encoding="utf-8") == \
           DefineHtml(define_copy, absolute_links=True).transform_to_html_string()


def test_cli_missing_file_exits_2_with_an_error_page(tmp_path, temp_env, run_cli):
    env, folder = temp_env

    completed = run_cli("defineview", "--no-open", str(tmp_path / "missing.xml"), env=env)

    assert completed.returncode == 2
    page = _only_file(folder)
    assert page.name == "missing.error.html"
    assert "not found" in page.read_text(encoding="utf-8")


def test_cli_temp_and_out_exit_2(define_copy, tmp_path, run_cli):
    completed = run_cli("defineview", "--no-open", "--temp", "-o", str(tmp_path / "view.html"), str(define_copy))

    assert completed.returncode == 2
    assert not (tmp_path / "view.html").exists()
