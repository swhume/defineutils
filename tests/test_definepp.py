from pathlib import Path
import pytest
from lxml import etree

from defineutils.definepp import DefinePrettyPrinter, DefinePrettyPrintError


def data_path() -> Path:
    return Path(__file__).parent


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
