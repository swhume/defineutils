"""Fixtures shared by the definehtml tests."""
import itertools
from pathlib import Path

import pytest
from lxml import etree, html

from defineutils.definehtml import DefineHtml

DATA = Path(__file__).parent


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
