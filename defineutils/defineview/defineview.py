"""
Renders a define.xml with definehtml, writes the HTML and opens it in the default browser: what double-clicking a
define.xml runs once defineview has been chosen to open it.
"""
import hashlib
import html
import os
import tempfile
import webbrowser
from pathlib import Path

from defineutils import __version__
from defineutils.definehtml import DefineHtml, DefineHtmlWriteError

ISSUES = "https://github.com/swhume/defineutils/issues"

# the page shown instead of the HTML when the define.xml can't be shown
ERROR_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{heading}</title>
<style>
body {{ font-family: Arial, sans-serif; max-width: 60em; margin: 2em auto; padding: 0 1em; line-height: 1.5; }}
pre {{ white-space: pre-wrap; background: #f4f4f4; padding: 1em; }}
</style>
</head>
<body>
<h1>{heading}</h1>
{advice}
<pre>{message}</pre>
{link}
<p>defineview {version}</p>
</body>
</html>
"""


class DefineViewError(Exception):
    """the HTML, or the page saying why there is none, could not be written or opened"""
    pass


class DefineViewer:
    def __init__(self, define_xml_file: Path, temp: bool = False, out_file: Path = None) -> None:
        """
        :param define_xml_file: Path to the define.xml to show
        :param temp: when True, the HTML is written to temp_folder rather than beside the define.xml
        :param out_file: when given, the HTML is written there; it can't be combined with temp
        """
        if temp and out_file is not None:
            raise DefineViewError("Choose the temp folder or an output file, not both.")
        self.define = Path(define_xml_file)
        self.temp = temp
        self.out_file = None if out_file is None else Path(out_file)

    @property
    def temp_folder(self) -> Path:
        """
        this define.xml's folder in the per-user temp folder, <temp>/defineutils/<12 hex digits>, named from a hash of
        the define.xml's path, so each define.xml has its own and showing it again overwrites it
        """
        key = hashlib.sha256(_folder_key(self.define).encode("utf-8")).hexdigest()[:12]
        return Path(tempfile.gettempdir(), "defineutils", key)

    def write_html(self) -> Path:
        """
        renders the define.xml and writes the HTML: to out_file; with temp, to temp_folder; otherwise beside the
        define.xml as <name>.html, replacing any file there, or to temp_folder when it can't be written there. HTML in
        a folder other than the define.xml's gets absolute links, so its dataset and document links still work
        :return: the path of the HTML
        :raises DefineHtmlGenerationError: the define.xml could not be rendered, or the HTML could not be written
        """
        if self.out_file is not None:
            return self._write(self.out_file)
        if not self.temp:
            try:
                return self._write(self.define.with_suffix(".html"))
            except DefineHtmlWriteError:
                # a read-only share, an email attachment's folder: the define.xml is rendered again, for the temp
                # folder, with absolute links
                pass
        folder = self.temp_folder
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            raise DefineHtmlWriteError(f"Unable to create the folder {folder}.\n{e}") from e
        return self._write(folder / f"{self.define.stem}.html")

    def write_error_page(self, message: str, unexpected: bool = False) -> Path:
        """
        writes the page saying why the define.xml was not shown to <name>.error.html in temp_folder, never beside the
        define.xml, with a link that shows the file as plain XML in the browser when it exists
        :param message: why it was not shown: the error message, or for an unexpected error the traceback
        :param unexpected: when True, the page asks for the error to be reported
        :return: the path of the page
        :raises DefineViewError: the page could not be written
        """
        name = html.escape(self.define.name)
        if unexpected:
            heading = f"defineview failed unexpectedly while showing {name}"
            advice = f'<p>Please report this, with the details below, at <a href="{ISSUES}">{ISSUES}</a>.</p>'
        else:
            heading, advice = f"{name} could not be shown", ""
        try:
            exists = self.define.is_file()
        except OSError:
            exists = False
        # a link the browser follows itself: handing an .xml file to the operating system would start defineview
        # again when it is the default for .xml files
        link = (f'<p><a href="{html.escape(_absolute(self.define).as_uri())}">View {name} as plain XML</a></p>'
                if exists else "")
        page = ERROR_PAGE.format(heading=heading, advice=advice, message=html.escape(message.rstrip()), link=link,
                                 version=__version__)
        path = self.temp_folder / f"{self.define.stem}.error.html"
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(page, encoding="utf-8")
        except OSError as e:
            raise DefineViewError(f"Unable to write {path}.\n{e}") from e
        return path

    def _write(self, html_file: Path) -> Path:
        """renders the define.xml to html_file, with absolute links unless it is in the define.xml's folder"""
        absolute_links = _folder_key(html_file.parent) != _folder_key(self.define.parent)
        DefineHtml(self.define, absolute_links=absolute_links).transform_to_html_file(html_file)
        return html_file


def open_in_browser(page: Path) -> None:
    """
    opens an HTML page in the default browser; on Windows, webbrowser hands its URL to the program that opens .html
    files. Only ever pass it an .html page: an .xml file would start defineview again when it is the default for .xml
    :param page: the page to open
    :raises DefineViewError: no browser could be started
    """
    if not webbrowser.open(_absolute(page).as_uri()):
        raise DefineViewError(f"No browser could be started to show {page}. Open that file in a browser.")


def _absolute(path: Path) -> Path:
    """the absolute path; abspath, not resolve(), which turns a mapped network drive into its UNC path"""
    return Path(os.path.abspath(path))


def _folder_key(path: Path) -> str:
    """a path in one spelling, for comparing paths: absolute, and on Windows lower case with \\ separators"""
    return os.path.normcase(os.path.abspath(path))
