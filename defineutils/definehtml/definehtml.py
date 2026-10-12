import re
from lxml import etree
from pathlib import Path

# the bundled Define-XML v2.1 stylesheet, a modified copy of Lex Jansen's define2-1.xsl (see
# stylesheet_changes.md); module-level so a test can point the class at another stylesheet
STYLESHEET = Path(__file__).parent.joinpath("define2-1.xsl")

ODM_NS = "http://www.cdisc.org/ns/odm/v1.3"
DEF_NS = "http://www.cdisc.org/ns/def/v2.1"

# the only URL schemes a rendered link may use; a link with any other scheme (javascript:, data:,
# vbscript: ...) is reduced to plain text. A one-letter scheme is a Windows drive (C:\docs\acrf.pdf)
SAFE_SCHEMES = {"http", "https", "file"}
# browsers ignore ASCII whitespace and control characters when they read a URL's scheme, so
# "java\tscript:" still runs; they are removed before the scheme is checked
_URL_IGNORED = re.compile(r"[\x00-\x20\x7f]")
_URL_SCHEME = re.compile(r"([A-Za-z][A-Za-z0-9+.\-]*):")

# the most distinct XSLT error-log messages quoted in a transform failure; a recursion failure
# alone logs dozens of entries
MAX_XSLT_MESSAGES = 5


class DefineHtmlGenerationError(Exception):
    pass


class DefineHtml:
    def __init__(self, define_xml_file: Path, codelist_items: int = 5, methods_table: bool = True,
                 comments_table: bool = False, prefixes: bool = False,
                 length_format: bool = False) -> None:
        """
        the stylesheet options default to the stylesheet's own defaults
        :param define_xml_file: Path to the Define-XML v2.1 file to render
        :param codelist_items: a codelist's terms are listed in the Controlled Terms column when it has
            at most this many terms, otherwise the column shows a link to the codelist
        :param methods_table: when True, the Methods table is included
        :param comments_table: when True, the Comments table is included
        :param prefixes: when True, comments, methods and origins are labeled [Comment], [Method] and
            [Origin]
        :param length_format: when True, the length column shows Length [Significant Digits] : Display
            Format rather than the display format or the length alone
        """
        self.define = Path(define_xml_file)
        self._does_define_file_exist()
        self._params = self._stylesheet_params(codelist_items, methods_table, comments_table,
                                               prefixes, length_format)
        self.xslt = STYLESHEET
        self._transformer = self._load_stylesheet()
        self._result = None

    def transform_to_html_string(self) -> str:
        """
        transforms the define.xml to HTML and returns the HTML as a string
        :return: string
        """
        return str(self._transform())

    def transform_to_html_file(self, html_file: Path) -> None:
        """
        transforms the define.xml to HTML and writes it, UTF-8 encoded, to html_file; the destination
        is checked before the transform runs
        :param html_file: Path to the file to save the HTML output
        :return: None
        """
        html_file = Path(html_file)
        self._check_html_file(html_file)
        # bytes() serializes through the stylesheet's xsl:output (method="html", encoding="utf-8");
        # etree.tostring() would write XML and self-close empty elements such as <span/>
        html = bytes(self._transform())
        try:
            with open(html_file, 'wb') as f:
                f.write(html)
        except IsADirectoryError as e:
            raise DefineHtmlGenerationError(f"Error attempting to write to a directory {html_file}.\n{e}") from e
        except PermissionError as e:
            raise DefineHtmlGenerationError(f"Permission error attempting to write to {html_file}.\n{e}") from e
        except OSError as e:
            raise DefineHtmlGenerationError(f"Unable to write {html_file}.\n{e}") from e

    def _transform(self) -> etree._XSLTResultTree:
        """
        parses the define.xml, confirms it is Define-XML v2.1, applies the stylesheet and reduces any
        unsafe link to text; the result is cached so both output methods transform once
        :return: html result tree
        """
        if self._result is None:
            xml_tree = self._parse_define()
            self._check_define_version(xml_tree)
            try:
                result_tree = self._transformer(xml_tree, **self._params)
            except etree.XSLTApplyError as e:
                raise DefineHtmlGenerationError(self._transform_error_message(e)) from e
            _neutralize_unsafe_links(result_tree)
            self._result = result_tree
        return self._result

    def _parse_define(self) -> etree._ElementTree:
        """
        parses the define.xml
        :return: the define.xml tree
        """
        try:
            return etree.parse(self.define)
        except etree.ParseError as e:
            raise DefineHtmlGenerationError(
                f"Unable to parse {self.define}: it is not well-formed XML.\n"
                f"  {e}\n\n"
                f"No HTML was generated. Run the validate utility to identify the problems:\n\n"
                f"    definevalidate -d {self.define}") from e
        except OSError as e:
            raise DefineHtmlGenerationError(f"Unable to read {self.define}.\n  {e}") from e

    def _check_define_version(self, xml_tree: etree._ElementTree) -> None:
        """
        the stylesheet binds def: to the Define-XML v2.1 namespace, so any other input would render
        without an error but with most of its content silently missing; it is refused instead
        :param xml_tree: the parsed define.xml
        """
        root = xml_tree.getroot()
        mdv = root.find(f"{{{ODM_NS}}}Study/{{{ODM_NS}}}MetaDataVersion")
        if root.tag != f"{{{ODM_NS}}}ODM":
            reason = f"its root element is {root.tag}, not the ODM v1.3 ODM element"
        elif mdv is None:
            reason = "it has no Study/MetaDataVersion element"
        elif mdv.get(f"{{{DEF_NS}}}DefineVersion") is not None:
            return
        else:
            other = [(etree.QName(name).namespace, value) for name, value in mdv.attrib.items()
                     if etree.QName(name).localname == "DefineVersion"]
            if other:
                namespace, version = other[0]
                reason = (f"its MetaDataVersion declares DefineVersion {version} in the namespace "
                          f"{namespace}, not {DEF_NS}")
            else:
                reason = "its MetaDataVersion has no def:DefineVersion attribute"
        raise DefineHtmlGenerationError(
            f"{self.define} is not a Define-XML v2.1 document: {reason}.\n\n"
            f"No HTML was generated. The bundled stylesheet renders Define-XML v2.1 only, and would\n"
            f"silently drop most of the content of any other file. Run the validate utility to check\n"
            f"the file:\n\n"
            f"    definevalidate -d {self.define}")

    def _transform_error_message(self, e: etree.XSLTApplyError) -> str:
        """
        builds the transform failure message; str(e) can be a single word (on the recursion limit it
        is 'first'), so the distinct messages in the stylesheet's error log are added
        :param e: the exception raised by the transform
        :return: string
        """
        messages = list(dict.fromkeys(entry.message.strip() for entry in self._transformer.error_log
                                      if entry.message.strip()))
        message = f"The stylesheet failed while transforming {self.define}.\n  {e}"
        for line in messages[:MAX_XSLT_MESSAGES]:
            message += "\n  " + line.replace("\n", "\n  ")
        if len(messages) > MAX_XSLT_MESSAGES:
            message += f"\n  ... {len(messages) - MAX_XSLT_MESSAGES} more"
        return message

    def _load_stylesheet(self) -> etree.XSLT:
        """
        compiles the stylesheet once so every transform reuses it
        :return: the compiled stylesheet
        """
        try:
            return etree.XSLT(etree.parse(self.xslt))
        except (etree.LxmlError, OSError) as e:
            raise DefineHtmlGenerationError(f"Unable to load the stylesheet {self.xslt}.\n  {e}") from e

    def _check_html_file(self, html_file: Path) -> None:
        """
        refuses an output path that is the input define.xml (writing there would overwrite it), is a
        directory, or is in a directory that does not exist
        :param html_file: Path to the file to save the HTML output
        """
        try:
            if html_file.exists() and html_file.samefile(self.define):
                raise DefineHtmlGenerationError(
                    f"The output file {html_file} is the input define.xml; writing the HTML there would "
                    f"overwrite it. Choose a different output file.")
            if html_file.is_dir():
                raise DefineHtmlGenerationError(f"Error attempting to write to a directory {html_file}.")
            if not html_file.parent.is_dir():
                raise DefineHtmlGenerationError(
                    f"The output directory {html_file.parent} does not exist or is not a directory.")
        except OSError as e:
            raise DefineHtmlGenerationError(f"Unable to access the output file {html_file}.\n{e}") from e

    @staticmethod
    def _stylesheet_params(codelist_items: int, methods_table: bool, comments_table: bool,
                           prefixes: bool, length_format: bool) -> dict:
        """
        maps the options onto the stylesheet's xsl:params; lxml evaluates each value as an XPath
        expression, so only validated integers are ever passed
        :return: dict of stylesheet parameter name to XPath value
        """
        if isinstance(codelist_items, bool) or not isinstance(codelist_items, int) or codelist_items < 0:
            raise DefineHtmlGenerationError(
                f"The number of codelist items to display must be a non-negative integer, not "
                f"{codelist_items!r}.")
        return {"nCodeListItemDisplay": str(codelist_items),
                "displayMethodsTable": "1" if methods_table else "0",
                "displayCommentsTable": "1" if comments_table else "0",
                "displayPrefix": "1" if prefixes else "0",
                "displayLengthDFormatSD": "1" if length_format else "0"}

    def _does_define_file_exist(self):
        """
        confirms that the define-xml file exists before attempting to transform it to HTML
        and raises a DefineHtmlGenerationError if it does not or cannot be accessed
        """
        try:
            exists = self.define.is_file()
        except OSError as e:
            raise DefineHtmlGenerationError(f"Unable to access {self.define}.\n{e}") from e
        if not exists:
            raise DefineHtmlGenerationError(f"File {str(self.define)} not found.")


def _is_safe_href(href: str) -> bool:
    """
    reports whether a link may keep its href: no scheme (a relative path or #fragment), an allowed
    scheme, or a one-letter Windows drive
    :param href: the href value
    :return: bool
    """
    match = _URL_SCHEME.match(_URL_IGNORED.sub("", href))
    if match is None:
        return True
    scheme = match.group(1).lower()
    return scheme in SAFE_SCHEMES or len(scheme) == 1


def _neutralize_unsafe_links(result_tree: etree._XSLTResultTree) -> None:
    """
    hrefs are copied verbatim from the define.xml (def:leaf/@xlink:href, ExternalCodeList/@href), so a
    hostile file could plant a clickable javascript: link. Each link whose scheme is not allowed
    becomes a span, which the stylesheet's a{} rule no longer styles as a link, and the external-link
    icon that follows it is removed
    :param result_tree: the HTML result tree, changed in place
    """
    root = result_tree.getroot()
    if root is None:
        return
    unsafe = [link for link in root.iter("a")
              if link.get("href") is not None and not _is_safe_href(link.get("href"))]
    for link in unsafe:
        link.tag = "span"
        del link.attrib["href"]
        classes = [name for name in (link.get("class") or "").split() if name != "external"]
        if classes:
            link.set("class", " ".join(classes))
        else:
            link.attrib.pop("class", None)
        icon = link.getnext()
        if (icon is not None and icon.tag == "span" and icon.get("class") == "external-link-gif"
                and not (link.tail or "").strip()):
            link.tail = (link.tail or "") + (icon.tail or "")
            link.getparent().remove(icon)
