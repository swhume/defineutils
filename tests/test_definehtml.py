from pathlib import Path
import pytest

from definehtml.definehtml import DefineHtml
from definehtml.definehtml import DefineHtmlGenerationError


def data_path() -> Path:
    return Path(__file__).parent


def test_transform_to_html_string_basic():
    # Arrange
    define_file = data_path() / "define.xml"
    dh = DefineHtml(define_file)

    # Act
    html_bytes = dh.transform_to_html_string()

    # Assert
    assert isinstance(html_bytes, (bytes, bytearray))
    assert len(html_bytes) > 0
    # very light sanity checks
    text = html_bytes.decode("utf-8", errors="ignore")
    assert "<html" in text.lower()
    assert "</html>" in text.lower()


def test_transform_to_html_file_basic(tmp_path: Path):
    # Arrange
    define_file = data_path() / "define.xml"
    dh = DefineHtml(define_file)
    out_file = tmp_path / "define.html"

    # Act
    dh.transform_to_html_file(out_file)

    # Assert
    assert out_file.exists()
    content = out_file.read_text(encoding="utf-8", errors="ignore")
    assert "<html" in content.lower()
    assert "</html>" in content.lower()
    assert "it.dm.domain" in content.lower()


def test_init_raises_when_define_missing(tmp_path: Path):
    missing = tmp_path / "nope.xml"
    with pytest.raises(DefineHtmlGenerationError):
        DefineHtml(missing)


def test_transform_handles_invalid_xml(tmp_path: Path, monkeypatch):
    # Create an invalid XML file
    bad_xml = tmp_path / "bad.xml"
    bad_xml.write_text("<define><broken></define>", encoding="utf-8")
    dh = DefineHtml.__new__(DefineHtml)
    # Bypass __init__ file-exists guard so we can inject our path
    dh.define = bad_xml
    dh.xslt = Path(__file__).parent.parent / "definehtml" / "define2-1.xsl"

    # Act
    result = dh.transform_to_html_string()

    # Assert: implementation returns empty string on failure
    assert result == ""


def test_transform_to_html_file_errors_graceful(tmp_path: Path):
    # Valid define.xml but try to write to a directory path to trigger IsADirectoryError branch
    define_file = data_path() / "define.xml"
    dh = DefineHtml(define_file)

    # Use the temp directory path itself as the output "file"
    with pytest.raises(DefineHtmlGenerationError):
        dh.transform_to_html_file(tmp_path)
