import signal
import subprocess
import sys
import time
from pathlib import Path
import pytest
from lxml import etree

from defineutils.definepp import DefinePrettyPrinter, DefinePrettyPrintError


def data_path() -> Path:
    return Path(__file__).parent


def _run_pp_console() -> subprocess.Popen:
    """Launch `python -m defineutils.definepp -d tests/define.xml` with stdout/stderr piped.
    Run from the repo root so the package resolves whether or not it is installed."""
    define_file = data_path() / "define.xml"
    return subprocess.Popen(
        [sys.executable, "-m", "defineutils.definepp", "-d", str(define_file)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(data_path().parent),
    )


def test_pretty_print_to_string_basic():
    define_file = data_path() / "define.xml"
    pp = DefinePrettyPrinter(define_file)

    xml = pp.pretty_print_to_string()

    assert isinstance(xml, str)
    assert len(xml) > 0
    assert xml.lstrip().startswith("<?xml")
    assert "<ODM" in xml
    assert "</ODM>" in xml


def test_pretty_print_is_indented():
    define_file = data_path() / "define.xml"
    pp = DefinePrettyPrinter(define_file)

    lines = pp.pretty_print_to_string().splitlines()

    # a real Define-XML reformats to many lines with indented child elements
    assert len(lines) > 100
    assert any(line.startswith("  <") for line in lines)


def test_pretty_print_preserves_content():
    define_file = data_path() / "define.xml"
    pp = DefinePrettyPrinter(define_file)

    pretty = pp.pretty_print_to_string()

    # byte-preserving apart from whitespace: element count is unchanged
    src_count = len(list(etree.parse(str(define_file)).getroot().iter()))
    out_count = len(list(etree.fromstring(pretty.encode("utf-8")).iter()))
    assert src_count == out_count
    # comments in the source define.xml survive the reformat
    assert "<!--" in pretty


def test_pretty_print_to_file_basic(tmp_path: Path):
    define_file = data_path() / "define.xml"
    pp = DefinePrettyPrinter(define_file)
    out_file = tmp_path / "define.pretty.xml"

    pp.pretty_print_to_file(out_file)

    assert out_file.exists()
    # the output re-parses as valid XML with an ODM root
    tree = etree.parse(str(out_file))
    assert tree.getroot().tag.endswith("ODM")


def test_init_raises_when_define_missing(tmp_path: Path):
    missing = tmp_path / "nope.xml"
    with pytest.raises(DefinePrettyPrintError):
        DefinePrettyPrinter(missing)


def test_pretty_print_malformed_xml_raises(tmp_path: Path):
    bad_xml = tmp_path / "bad.xml"
    bad_xml.write_text("<define><broken></define>", encoding="utf-8")
    pp = DefinePrettyPrinter(bad_xml)

    with pytest.raises(DefinePrettyPrintError):
        pp.pretty_print_to_string()


def test_pretty_print_to_console_head(capsys):
    define_file = data_path() / "define.xml"
    pp = DefinePrettyPrinter(define_file)

    pp.pretty_print_to_console(head=10)

    captured = capsys.readouterr()
    assert len(captured.out.splitlines()) == 10


def test_pretty_print_to_console_full(capsys):
    define_file = data_path() / "define.xml"
    pp = DefinePrettyPrinter(define_file)

    pp.pretty_print_to_console()

    captured = capsys.readouterr()
    expected = pp.pretty_print_to_string().splitlines()
    assert len(captured.out.splitlines()) == len(expected)


def test_pretty_print_to_file_errors_graceful(tmp_path: Path):
    define_file = data_path() / "define.xml"
    pp = DefinePrettyPrinter(define_file)

    # writing to a directory path triggers the IsADirectoryError branch
    with pytest.raises(DefinePrettyPrintError):
        pp.pretty_print_to_file(tmp_path)


def test_console_broken_pipe_exits_cleanly():
    # a reader (e.g. `more`/`head`) that quits after one line closes the pipe early;
    # the CLI should exit 0 with no traceback. define.xml is larger than the OS pipe
    # buffer, so the writer is still writing when the read end closes.
    p = _run_pp_console()
    try:
        p.stdout.readline()          # read one line, like a pager's first screen
        p.stdout.close()             # reader goes away -> next write hits a broken pipe
        err = p.stderr.read()
        rc = p.wait(timeout=15)
    finally:
        if p.poll() is None:
            p.kill()
        p.stderr.close()

    assert rc == 0
    assert b"Traceback" not in err
    assert b"BrokenPipeError" not in err


def test_console_ctrl_c_exits_cleanly():
    # Ctrl-C while paging sends SIGINT to the writer, which raises KeyboardInterrupt
    # mid-write; the CLI should exit quietly with no traceback. The read end stays open
    # so the interrupt (not a broken pipe) is what ends the process. On POSIX the CLI
    # re-raises SIGINT so it dies *by* the signal (returncode -SIGINT) to keep the shell
    # prompt clean; elsewhere it exits 130.
    p = _run_pp_console()
    try:
        p.stdout.readline()          # read one line so the writer blocks on a full pipe
        time.sleep(0.3)
        p.send_signal(signal.SIGINT)  # Ctrl-C
        rc = p.wait(timeout=15)
        err = p.stderr.read()
    finally:
        if p.poll() is None:
            p.kill()
        p.stdout.close()
        p.stderr.close()

    assert rc in (-signal.SIGINT, 130)
    assert b"Traceback" not in err
    assert b"KeyboardInterrupt" not in err
    assert b"BrokenPipeError" not in err
