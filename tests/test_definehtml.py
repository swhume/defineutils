import os
import re
import shutil
from pathlib import Path
import pytest
from lxml import html

from defineutils.definehtml import DefineHtml, DefineHtmlGenerationError
from defineutils.definehtml import definehtml as definehtml_module

NS = {"odm": "http://www.cdisc.org/ns/odm/v1.3",
      "def": "http://www.cdisc.org/ns/def/v2.1",
      "xlink": "http://www.w3.org/1999/xlink"}
ADAM_DEFINE = Path(__file__).parent / "define-adam.xml"

# an empty non-void element written in XML's self-closed form, which browsers read as an unclosed
# start tag (the void elements may legitimately end in />)
SELF_CLOSED_NON_VOID = re.compile(
    r"<(?!(?:area|base|br|col|embed|hr|img|input|link|meta|source|track|wbr)\b)[A-Za-z][\w-]*\b[^>]*/>")

XLINK_HREF = f"{{{NS['xlink']}}}href"


def data_path() -> Path:
    return Path(__file__).parent


def define_file() -> Path:
    return data_path() / "define.xml"


def set_acrf_href(href: str):
    """edit that points the aCRF leaf, the target of the Origin page links, at href"""
    def edit(tree):
        tree.xpath("//def:leaf[@ID='LF.acrf']", namespaces=NS)[0].set(XLINK_HREF, href)
    return edit


# output

def test_transform_to_html_string_basic():
    # Arrange
    dh = DefineHtml(define_file())

    # Act
    html_text = dh.transform_to_html_string()

    # Assert
    assert isinstance(html_text, str)
    assert "<html" in html_text.lower()
    assert "</html>" in html_text.lower()


def test_transform_to_html_file_basic(tmp_path: Path):
    # Arrange
    dh = DefineHtml(define_file())
    out_file = tmp_path / "define.html"

    # Act
    dh.transform_to_html_file(out_file)

    # Assert
    assert out_file.exists()
    content = out_file.read_text(encoding="utf-8", errors="ignore")
    assert "<html" in content.lower()
    assert "</html>" in content.lower()
    assert "it.dm.domain" in content.lower()


@pytest.mark.parametrize("define", [define_file(), ADAM_DEFINE], ids=["sdtm", "adam"])
def test_output_has_no_self_closed_non_void_elements(define: Path):
    assert SELF_CLOSED_NON_VOID.findall(DefineHtml(define).transform_to_html_string()) == []


def test_file_output_is_utf8_html_with_a_charset(tmp_path: Path):
    out_file = tmp_path / "define.html"
    dh = DefineHtml(define_file())

    dh.transform_to_html_file(out_file)

    content = out_file.read_bytes()
    assert b'content="text/html; charset=utf-8"' in content
    assert content.decode("utf-8") == dh.transform_to_html_string()


def test_menu_sections_stay_siblings_when_the_acrf_is_the_only_supplemental_doc(edited_define):
    # the Supplemental Documents submenu skips the aCRF, so here its list is empty; written as <ul/>
    # it swallowed every later menu section into the hidden submenu
    def acrf_only(tree):
        mdv = tree.find("odm:Study/odm:MetaDataVersion", NS)
        supplemental = mdv.find("def:SupplementalDoc", NS)
        for ref in supplemental.findall("def:DocumentRef", NS)[1:]:
            supplemental.remove(ref)
        supplemental.find("def:DocumentRef", NS).set("leafID", "LF.acrf")
        annotated = supplemental.makeelement(f"{{{NS['def']}}}AnnotatedCRF")
        annotated.append(annotated.makeelement(f"{{{NS['def']}}}DocumentRef", leafID="LF.acrf"))
        supplemental.addprevious(annotated)

    html_text = DefineHtml(edited_define(acrf_only)).transform_to_html_string()

    assert "<ul></ul>" in html_text
    top_level = html.fromstring(html_text).xpath("//ul[@class='hmenu']/li/a[@class='tocItem']/text()")
    assert {"Standards", "Datasets", "Controlled Terminology", "Methods"} <= set(top_level)


def test_both_outputs_reuse_one_transform(tmp_path: Path):
    dh = DefineHtml(define_file())
    first = dh._transform()

    dh.transform_to_html_file(tmp_path / "define.html")

    assert dh._transform() is first


# failures raise DefineHtmlGenerationError

def test_init_raises_when_define_missing(tmp_path: Path):
    missing = tmp_path / "nope.xml"
    with pytest.raises(DefineHtmlGenerationError):
        DefineHtml(missing)


def test_invalid_xml_raises_and_recommends_the_validate_utility(tmp_path: Path):
    bad_xml = tmp_path / "bad.xml"
    bad_xml.write_text("<define><broken></define>", encoding="utf-8")

    with pytest.raises(DefineHtmlGenerationError, match="not well-formed XML") as excinfo:
        DefineHtml(bad_xml).transform_to_html_string()
    assert "python -m defineutils.validate" in str(excinfo.value)


def test_non_xml_input_raises(tmp_path: Path):
    readme = tmp_path / "README.md"
    shutil.copy(data_path().parent / "README.md", readme)

    with pytest.raises(DefineHtmlGenerationError, match="not well-formed XML"):
        DefineHtml(readme).transform_to_html_file(tmp_path / "define.html")
    assert not (tmp_path / "define.html").exists()


@pytest.mark.skipif(os.name != "posix" or os.geteuid() == 0, reason="needs a non-root POSIX user")
def test_unreadable_define_raises(tmp_path: Path):
    unreadable = tmp_path / "define.xml"
    shutil.copy(define_file(), unreadable)
    unreadable.chmod(0)
    try:
        with pytest.raises(DefineHtmlGenerationError, match="Unable to read"):
            DefineHtml(unreadable).transform_to_html_string()
    finally:
        unreadable.chmod(0o600)


def test_transform_to_html_file_errors_graceful(tmp_path: Path):
    # Valid define.xml but try to write to a directory path to trigger IsADirectoryError branch
    define_file_path = define_file()
    dh = DefineHtml(define_file_path)

    # Use the temp directory path itself as the output "file"
    with pytest.raises(DefineHtmlGenerationError):
        dh.transform_to_html_file(tmp_path)


@pytest.mark.parametrize("as_given", ["direct", "dot-dot"])
def test_output_that_is_the_input_raises_and_leaves_it_unchanged(tmp_path: Path, as_given: str):
    define = tmp_path / "define.xml"
    shutil.copy(define_file(), define)
    (tmp_path / "sub").mkdir()
    out_file = define if as_given == "direct" else tmp_path / "sub" / ".." / "define.xml"
    before = define.read_bytes()

    with pytest.raises(DefineHtmlGenerationError, match="would overwrite it"):
        DefineHtml(define).transform_to_html_file(out_file)
    assert define.read_bytes() == before


def test_missing_output_directory_raises(tmp_path: Path):
    with pytest.raises(DefineHtmlGenerationError, match="output directory .* does not exist"):
        DefineHtml(define_file()).transform_to_html_file(tmp_path / "no_such_dir" / "define.html")


def test_transform_failure_reports_the_stylesheet_error_log(tmp_path: Path, monkeypatch):
    stylesheet = tmp_path / "terminate.xsl"
    stylesheet.write_text('<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">'
                          '<xsl:template match="/"><xsl:message terminate="yes">stopped: no output for '
                          'you</xsl:message></xsl:template></xsl:stylesheet>', encoding="utf-8")
    monkeypatch.setattr(definehtml_module, "STYLESHEET", stylesheet)

    with pytest.raises(DefineHtmlGenerationError, match="stopped: no output for you"):
        DefineHtml(define_file()).transform_to_html_string()


@pytest.mark.parametrize("content", [None, "<xsl:stylesheet"], ids=["missing", "malformed"])
def test_unloadable_stylesheet_raises_when_constructed(tmp_path: Path, monkeypatch, content):
    stylesheet = tmp_path / "define2-1.xsl"
    if content is not None:
        stylesheet.write_text(content, encoding="utf-8")
    monkeypatch.setattr(definehtml_module, "STYLESHEET", stylesheet)

    with pytest.raises(DefineHtmlGenerationError, match="Unable to load the stylesheet"):
        DefineHtml(define_file())


# only Define-XML v2.1 is rendered

def test_define_xml_v20_namespace_is_refused(tmp_path: Path):
    v20 = tmp_path / "define.xml"
    v20.write_text(define_file().read_text(encoding="utf-8").replace(
        "http://www.cdisc.org/ns/def/v2.1", "http://www.cdisc.org/ns/def/v2.0"), encoding="utf-8")

    with pytest.raises(DefineHtmlGenerationError, match="not a Define-XML v2.1 document") as excinfo:
        DefineHtml(v20).transform_to_html_string()
    assert "http://www.cdisc.org/ns/def/v2.0" in str(excinfo.value)
    assert "python -m defineutils.validate" in str(excinfo.value)


def test_non_odm_xml_is_refused():
    schema = data_path().parent / "defineutils" / "validate" / "schema" / "cdisc-define-2.1" / "define2-1-0.xsd"

    with pytest.raises(DefineHtmlGenerationError, match="its root element is"):
        DefineHtml(schema).transform_to_html_string()


def test_missing_define_version_is_refused(edited_define):
    def drop_define_version(tree):
        mdv = tree.find("odm:Study/odm:MetaDataVersion", NS)
        del mdv.attrib[f"{{{NS['def']}}}DefineVersion"]

    with pytest.raises(DefineHtmlGenerationError, match="no def:DefineVersion"):
        DefineHtml(edited_define(drop_define_version)).transform_to_html_string()


# links with an unsafe scheme become text

@pytest.mark.parametrize("href", ["javascript:alert(document.cookie)//", "JaVaScRiPt:alert(1)",
                                  " javascript:alert(1)", "java\tscript:alert(1)",
                                  "data:text/html,<script>alert(1)</script>", "vbscript:msgbox(1)"])
def test_unsafe_document_links_become_text(edited_define, render, href: str):
    page = render(edited_define(set_acrf_href(href)))

    assert [a.get("href") for a in page.iter("a") if "script" in (a.get("href") or "")
            or (a.get("href") or "").startswith("data:")] == []
    # the page links remain as text, and lose their external-link icon
    origins = page.xpath("//td[contains(., 'Annotated CRF [')]")
    assert origins
    assert not origins[0].xpath(".//span[@class='external-link-gif']")


def test_unsafe_external_codelist_link_becomes_text(edited_define, render):
    def hostile_dictionary(tree):
        tree.xpath("//odm:ExternalCodeList", namespaces=NS)[0].set("href", "javascript:alert(1)")

    row = render(edited_define(hostile_dictionary)).get_element_by_id("CL.CL.ISO.COUNTRY")

    assert not [a for a in row.iter("a") if a.get("href")]
    assert "ISO-3166 (Country Codes)" in row.text_content()


@pytest.mark.parametrize("href", ["acrf.pdf", "../docs/acrf.pdf", "https://example.org/acrf.pdf",
                                  "file:///c:/docs/acrf.pdf", "C:\\docs\\acrf.pdf"])
def test_safe_document_links_are_kept(edited_define, render, href: str):
    page = render(edited_define(set_acrf_href(href)))

    assert f"{href}#page=1" in {a.get("href") for a in page.iter("a")}


# stylesheet options

def test_default_options_are_the_stylesheet_defaults(render):
    page = render(define_file())

    assert page.get_element_by_id("compmethod", None) is not None
    assert page.get_element_by_id("comment", None) is None
    assert "[Comment]" not in page.text_content()


def test_comments_table_option(render):
    page = render(define_file(), comments_table=True)

    assert page.get_element_by_id("comment", None) is not None
    assert page.xpath("//a[@class='tocItem'][@href='#comment']")
    assert len(page.xpath("//tr[starts-with(@id, 'COMM.')]")) == 30


def test_methods_table_option(render):
    page = render(define_file(), methods_table=False)

    assert page.get_element_by_id("compmethod", None) is None
    assert not page.xpath("//tr[starts-with(@id, 'MT.')]")


@pytest.mark.parametrize("codelist_items, term_links, inline_terms", [(0, 40, 0), (5, 7, 123), (999, 0, 211)])
def test_codelist_items_option(render, codelist_items: int, term_links: int, inline_terms: int):
    page = render(define_file(), codelist_items=codelist_items)

    assert len(re.findall(r"\[\d+ Terms\]", page.text_content())) == term_links
    assert len(page.xpath("//li[@class='codelist-item']")) == inline_terms


def test_prefixes_option(render):
    text = render(define_file(), prefixes=True).text_content()

    assert "[Comment]" in text
    assert "[Method]" in text
    assert "[Origin]" in text


def test_length_format_option(render):
    page = render(define_file(), length_format=True)

    assert page.xpath("//th[normalize-space()='Length [SignificantDigits] : Display Format']")


@pytest.mark.parametrize("codelist_items", [-1, "5", True, 2.5])
def test_invalid_codelist_items_raises(codelist_items):
    with pytest.raises(DefineHtmlGenerationError, match="non-negative integer"):
        DefineHtml(define_file(), codelist_items=codelist_items)
