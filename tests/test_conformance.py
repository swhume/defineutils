"""
The conformance rule checker: the registry, the check factories, the baseline on tests/define.xml,
the conformant fixture, one mutation per implemented rule, the enumerations against the bundled
schema, loading, the CLI and the reports.
"""
import copy
import json
import re
import sys
from pathlib import Path

import pytest
import xmlschema
from lxml import etree

from defineutils.conformance import (DefineConformanceChecker, DefineConformanceError,
                                     DefineConformanceLoadError)
from defineutils.conformance.document import Document, qualified
from defineutils.conformance.rules import (all_rules, METADATA, REGISTRY, SUBMISSION, NEEDS_CT, NEEDS_IG,
                                           NEEDS_DATASETS)
from defineutils.conformance.rules import checks
from defineutils.conformance.rules import values as V
from defineutils.conformance.rules.order import expected_child_order
from defineutils.validate.validate import DEFAULT_SCHEMA

ODM_NS = "http://www.cdisc.org/ns/odm/v1.3"
DEF_NS = "http://www.cdisc.org/ns/def/v2.1"
DEF_20_NS = "http://www.cdisc.org/ns/def/v2.0"
XLINK_NS = "http://www.w3.org/1999/xlink"
NS = {"odm": ODM_NS, "def": DEF_NS, "xlink": XLINK_NS}

NOT_EVALUATED = {"179": NEEDS_CT, "186": NEEDS_CT, "187": NEEDS_CT, "192": NEEDS_CT, "201": NEEDS_CT,
                 "202": NEEDS_CT, "67": NEEDS_IG, "97": NEEDS_IG, "98": NEEDS_IG, "99": NEEDS_IG, "149": NEEDS_IG,
                 "263": NEEDS_IG, "265": NEEDS_IG, "266": NEEDS_IG, "76": NEEDS_DATASETS}
SUBMISSION_RULES = {"31", "70", "93", "96", "108", "119", "125", "128", "131", "147", "154", "168", "176"}

# what tests/define.xml fails: rule id -> occurrences
BASELINE = {"73": 2, "153": 11, "159": 30, "240": 1, "249": 11}

MDV_CHILDREN = ["def:Standards", "def:AnnotatedCRF", "def:SupplementalDoc", "def:ValueListDef",
                "def:WhereClauseDef", "ItemGroupDef", "ItemDef", "CodeList", "MethodDef", "def:CommentDef",
                "def:leaf"]


def data_path() -> Path:
    return Path(__file__).parent


def define_file() -> Path:
    return data_path() / "define.xml"


def conformant_file() -> Path:
    return data_path() / "define_conformant.xml"


def adam_file() -> Path:
    return data_path() / "define-adam.xml"


def failed_rules(path: Path, **options) -> dict:
    """rule id -> Finding for the rules the file fails"""
    return {f.rule: f for f in DefineConformanceChecker(path, **options).check().findings}


# -- lxml helpers for the mutations ------------------------------------------------------------

def find(node, xpath: str) -> list:
    return node.xpath(xpath, namespaces=NS)


def one(node, xpath: str):
    found = find(node, xpath)
    assert len(found) == 1, f"{xpath} matched {len(found)} elements"
    return found[0]


def mdv(tree):
    return one(tree, "//odm:MetaDataVersion")


def group(tree, oid: str):
    return one(tree, f"//odm:ItemGroupDef[@OID='{oid}']")


def item(tree, oid: str):
    return one(tree, f"//odm:ItemDef[@OID='{oid}']")


def item_ref(tree, group_oid: str, item_oid: str):
    return one(tree, f"//odm:ItemGroupDef[@OID='{group_oid}']/odm:ItemRef[@ItemOID='{item_oid}']")


def codelist(tree, oid: str):
    return one(tree, f"//odm:CodeList[@OID='{oid}']")


def standard(tree, oid: str):
    return one(tree, f"//def:Standard[@OID='{oid}']")


def comment(tree, oid: str):
    return one(tree, f"//def:CommentDef[@OID='{oid}']")


def leaf(tree, leaf_id: str):
    return one(tree, f"//def:leaf[@ID='{leaf_id}']")


def origin(tree, item_oid: str):
    return one(tree, f"//odm:ItemDef[@OID='{item_oid}']/def:Origin")


def page_ref(tree, item_oid: str):
    return one(tree, f"//odm:ItemDef[@OID='{item_oid}']/def:Origin/def:DocumentRef/def:PDFPageRef")


def description(parent):
    return one(parent, "odm:Description")


def remove(elem) -> None:
    elem.getparent().remove(elem)


def duplicate(elem) -> None:
    parent = elem.getparent()
    parent.insert(parent.index(elem) + 1, copy.deepcopy(elem))


def set_attr(elem, name: str, value: str) -> None:
    elem.set(qualified(name), value)


def del_attr(elem, name: str) -> None:
    del elem.attrib[qualified(name)]


def tag(name: str) -> str:
    return qualified(name) if ":" in name else f"{{{ODM_NS}}}{name}"


def add(parent, name: str, index: int = None, text: str = None, attrs: dict = None):
    """adds a child element, at the end or at the index, with attributes named as in the document"""
    child = etree.Element(tag(name))
    for attribute, value in (attrs or {}).items():
        set_attr(child, attribute, value)
    if text is not None:
        child.text = text
    if index is None:
        parent.append(child)
    else:
        parent.insert(index, child)
    return child


def add_description(parent, index: int = 0, text: str = "Added") -> None:
    desc = add(parent, "Description", index=index)
    add(desc, "TranslatedText", text=text, attrs={"xml:lang": "en"})


def add_range_check(where_clause, item_oid: str) -> None:
    check = add(where_clause, "RangeCheck", attrs={"Comparator": "EQ", "SoftHard": "Soft", "def:ItemOID": item_oid})
    add(check, "CheckValue", text="X")


def set_leaf_id(tree, old: str, new: str) -> None:
    """renames a leaf and every reference to it, so only the ID's lexical form changes"""
    set_attr(leaf(tree, old), "ID", new)
    for ref in find(tree, f"//def:DocumentRef[@leafID='{old}']"):
        set_attr(ref, "leafID", new)


def make_non_standard(tree, oid: str) -> None:
    del_attr(group(tree, oid), "def:StandardOID")
    set_attr(group(tree, oid), "def:IsNonStandard", "Yes")


def inline(xml: str) -> Document:
    """a Document parsed from a snippet, for the factory tests"""
    return Document(etree.ElementTree(etree.fromstring(xml)), Path("inline.xml"))


# ---------------------------------------------------------------------------------------------
# 1. the registry
# ---------------------------------------------------------------------------------------------

def test_every_metadata_rule_is_registered_exactly_once():
    rules = all_rules()
    assert len(rules) == 225
    assert [r.id for r in rules] == sorted(METADATA, key=int)
    assert len({r.id for r in rules}) == len(rules)


def test_the_rules_that_need_external_content():
    assert {r.id: r.requires for r in all_rules() if r.requires} == NOT_EVALUATED


def test_the_submission_rules():
    assert {r.id for r in all_rules() if r.context} == SUBMISSION_RULES
    assert all(r.context == SUBMISSION for r in all_rules() if r.context)


def test_every_select_compiles():
    for r in all_rules():
        etree.XPath(r.select, namespaces=NS)


def test_rule_metadata_is_joined():
    rule = REGISTRY["73"]
    assert rule.element == "ItemRef" and rule.attribute == "MethodOID"
    assert rule.subject == "ItemRef/@MethodOID"
    assert rule.source_type == "Specification" and rule.versions == "Both 2.0 and 2.1"
    assert rule.text.startswith("The MethodOID attribute must be provided")
    assert rule.cdisc_message.startswith("ItemRef[@ItemOID] is missing the MethodOID")
    assert rule.status == "document"
    assert REGISTRY["70"].status == "submission" and REGISTRY["179"].status == "needs ct"


def test_rule_121_uses_its_rule_text_as_the_message():
    # the spreadsheet's message cell is empty for 121
    assert METADATA["121"]["message"] == METADATA["121"]["rule"]


def test_expected_child_order_comes_from_the_define_model():
    order = expected_child_order()
    assert order["MetaDataVersion"] == MDV_CHILDREN
    # the Define-XML shape, not the ODM 1.3.2 one the descriptors would give
    assert order["ItemDef"] == ["Description", "CodeListRef", "def:Origin", "def:ValueListRef", "Alias"]
    assert order["ItemGroupDef"] == ["Description", "ItemRef", "Alias", "def:Class", "def:leaf"]
    assert order["ODM"] == ["Study"]


# ---------------------------------------------------------------------------------------------
# 2. the check factories
# ---------------------------------------------------------------------------------------------

SNIPPET = f"""<ODM xmlns="{ODM_NS}" xmlns:def="{DEF_NS}" xmlns:xlink="{XLINK_NS}" def:Context="Other" OID="X">
  <Study OID="S">
    <MetaDataVersion OID="MDV">
      <def:Standards><def:Standard OID="STD.1" Type="CT"/></def:Standards>
      <ItemGroupDef OID="IG.A" Name="A" Domain="B" def:ArchiveLocationID="LF.A">
        <Description><TranslatedText xml:lang="en">a</TranslatedText><TranslatedText xml:lang="en">b</TranslatedText></Description>
        <ItemRef ItemOID="IT.1" OrderNumber="1" KeySequence="1"/>
        <ItemRef ItemOID="IT.2" KeySequence="1"/>
        <ItemRef ItemOID="IT.3"/>
        <def:leaf ID="LF.A" xlink:href="a.xpt"/>
      </ItemGroupDef>
      <ItemGroupDef OID="IG.B" Name="B" def:ArchiveLocationID="LF.A"/>
      <ItemDef OID="IT.1" Name="ONE" DataType="float" Length="x"/>
      <ItemDef OID="IT.2" Name="TWO" DataType="text" Length=""/>
      <ItemDef OID="IT.2" Name="TWO-AGAIN"/>
      <CodeList OID="CL.1"><EnumeratedItem CodedValue="a"/><EnumeratedItem CodedValue="b"/></CodeList>
      <def:CommentDef OID="COM.1"><Description/><Description/></def:CommentDef>
      <def:leaf ID="LF.B" xlink:href="b.pdf"/>
    </MetaDataVersion>
  </Study>
</ODM>"""


@pytest.fixture(scope="module")
def doc() -> Document:
    return inline(SNIPPET)


def violations(check, doc, xpath) -> list:
    return [v for node in doc.xpath(doc.root, xpath) for v in check(doc, node)]


def test_required_attr(doc):
    assert violations(checks.required_attr("Name"), doc, "//odm:ItemDef") == []
    missing = violations(checks.required_attr("DataType"), doc, "//odm:ItemDef")
    assert [v.node.get("Name") for v in missing] == ["TWO-AGAIN"]
    assert missing[0].detail == "@DataType is missing"
    # an empty value counts as missing
    assert len(violations(checks.required_attr("Length"), doc, "//odm:ItemDef")) == 2


def test_absent_attr(doc):
    assert len(violations(checks.absent_attr("Domain"), doc, "//odm:ItemGroupDef")) == 1


def test_allowed_values(doc):
    bad = violations(checks.allowed_values("DataType", {"text", "integer"}), doc, "//odm:ItemDef")
    assert [v.detail for v in bad] == ['@DataType="float" is not one of "integer", "text"']
    single = violations(checks.allowed_values("DataType", {"text"}), doc, "//odm:ItemDef")
    assert single[0].detail == '@DataType="float" is not "text"'


def test_attr_matches(doc):
    bad = violations(checks.attr_matches("Length", V.POSITIVE_INTEGER, "a positive integer"), doc, "//odm:ItemDef")
    assert [v.detail for v in bad] == ['@Length="x" is not a positive integer', '@Length="" is not a positive integer']


def test_required_and_max_one_child(doc):
    assert violations(checks.required_child("ItemRef"), doc, "//odm:ItemGroupDef[@OID='IG.A']") == []
    assert [v.detail for v in violations(checks.required_child("ItemRef"), doc, "//odm:ItemGroupDef[@OID='IG.B']")] \
        == ["has no ItemRef child element"]
    assert [v.detail for v in violations(checks.required_child("ItemRef", 4), doc, "//odm:ItemGroupDef[@OID='IG.A']")] \
        == ["has 3 ItemRef child elements; at least 4 are required"]
    assert [v.detail for v in violations(checks.max_one_child("Description"), doc, "//def:CommentDef")] \
        == ["has 2 Description child elements; at most one is allowed"]
    assert violations(checks.max_one_child("Description"), doc, "//odm:ItemGroupDef") == []


def test_forbidden_child(doc):
    bad = violations(checks.forbidden_child("def:leaf", "no leaves here"), doc, "//odm:ItemGroupDef")
    assert [v.detail for v in bad] == ["has a def:leaf child element, but no leaves here"]


def test_attrs_equal(doc):
    bad = violations(checks.attrs_equal("Domain", "Name"), doc, "//odm:ItemGroupDef")
    assert [v.detail for v in bad] == ['@Domain="B" differs from @Name="A"']


def test_conditional_presence(doc):
    is_float = lambda doc, e: doc.attr(e, "DataType") == "float"
    assert [v.detail for v in violations(checks.present_when("SignificantDigits", is_float, because="it is a float"),
                                         doc, "//odm:ItemDef")] == ["@SignificantDigits is missing, but it is a float"]
    assert [v.detail for v in violations(checks.absent_when("Length", is_float, because="it is a float"),
                                         doc, "//odm:ItemDef")] == ["@Length is present, but it is a float"]
    assert [v.detail for v in violations(checks.value_when("Length", "8", is_float, because="it is a float"),
                                         doc, "//odm:ItemDef")] == ['@Length="x" must be "8", because it is a float']
    missing = violations(checks.value_when("Name", "A", lambda doc, e: True, because="always"), doc, "//odm:Study")
    assert missing[0].detail == '@Name is missing and must be "A", because always'
    has_domain = lambda doc, e: doc.attr(e, "Domain") is not None
    assert [v.detail for v in violations(checks.child_present_when("Alias", has_domain, because="@Domain is present"),
                                         doc, "//odm:ItemGroupDef")] == \
        ["has no Alias child element, but @Domain is present"]


def test_unique_among_siblings(doc):
    keys = violations(checks.unique_among_siblings("ItemRef", "KeySequence"), doc, "//odm:ItemGroupDef")
    # the ItemRef without a KeySequence is not a duplicate of anything
    assert [v.node.get("ItemOID") for v in keys] == ["IT.1", "IT.2"]
    assert keys[0].detail == '@KeySequence="1" is shared by 2 ItemRef elements under the same ItemGroupDef'
    langs = violations(checks.unique_among_siblings("TranslatedText", "xml:lang", absent_is_value=True), doc,
                       "//odm:Description")
    assert len(langs) == 2
    # two TranslatedText without xml:lang share the one default value
    doc2 = inline(f'<Description xmlns="{ODM_NS}"><TranslatedText/><TranslatedText/></Description>')
    assert len(violations(checks.unique_among_siblings("TranslatedText", "xml:lang", absent_is_value=True), doc2,
                          "/*")) == 2
    assert violations(checks.unique_among_siblings("TranslatedText", "xml:lang"), doc2, "/*") == []


def test_all_or_none(doc):
    bad = violations(checks.all_or_none("ItemRef", "OrderNumber"), doc, "//odm:ItemGroupDef")
    assert [v.node.get("ItemOID") for v in bad] == ["IT.2", "IT.3"]
    assert bad[0].detail == ("@OrderNumber is missing, but 1 of the 3 ItemRef elements under this ItemGroupDef "
                             "have one")
    assert violations(checks.all_or_none("EnumeratedItem", "Rank"), doc, "//odm:CodeList") == []


def test_unique_in_document(doc):
    bad = violations(checks.unique_in_document("//*[@OID]", "OID"), doc, "/*")
    assert [v.node.get("Name") for v in bad] == ["TWO", "TWO-AGAIN"]
    assert bad[0].detail == '@OID="IT.2" is defined 2 times'


def test_at_most_in_document(doc):
    assert violations(checks.at_most_in_document("//odm:ItemGroupDef", 2, "datasets"), doc, "/*") == []
    assert [v.detail for v in violations(checks.at_most_in_document("//odm:ItemGroupDef", 1, "datasets"), doc, "/*")] \
        == ["the document has 2 datasets; at most 1 allowed"]


def test_ref_to(doc):
    refs = violations(checks.ref_to("ItemOID", "ItemDef"), doc, "//odm:ItemRef")
    assert [v.detail for v in refs] == ['@ItemOID="IT.3" references no ItemDef']
    # the wrong kind of element
    doc2 = inline(SNIPPET.replace('ItemOID="IT.3"', 'ItemOID="CL.1"'))
    assert [v.detail for v in violations(checks.ref_to("ItemOID", "ItemDef"), doc2, "//odm:ItemRef")] == \
        ['@ItemOID="CL.1" is defined by CodeList, not ItemDef']
    # a condition on the target
    is_ig = lambda doc, s: doc.attr(s, "Type") == "IG"
    doc3 = inline(SNIPPET.replace('Domain="B"', 'Domain="B" def:StandardOID="STD.1"'))
    assert [v.detail for v in violations(checks.ref_to("def:StandardOID", "def:Standard", where=is_ig,
                                                       because='it must be an "IG"'), doc3, "//odm:ItemGroupDef")] \
        == ['@def:StandardOID="STD.1" resolves to a def:Standard, but it must be an "IG"']
    # leaf references resolve through ID, and scope="self" wants the leaf inside the context node
    assert violations(checks.ref_to("def:ArchiveLocationID", "def:leaf"), doc, "//odm:ItemGroupDef") == []
    scoped = violations(checks.ref_to("def:ArchiveLocationID", "def:leaf", scope="self"), doc, "//odm:ItemGroupDef")
    assert [v.detail for v in scoped] == ['@def:ArchiveLocationID="LF.A" references no def:leaf inside this ItemGroupDef']


def test_root_is(doc):
    assert violations(checks.root_is("ODM"), doc, "/*") == []
    doc2 = inline(f'<Study xmlns="{ODM_NS}"/>')
    assert [v.detail for v in violations(checks.root_is("ODM"), doc2, "/*")] == \
        ["the root element is Study, not ODM"]


def test_element_order():
    doc2 = inline(f"""<ODM xmlns="{ODM_NS}" xmlns:def="{DEF_NS}" xmlns:arm="urn:arm"><Study><MetaDataVersion>
        <ItemDef OID="IT.1"/><arm:Unknown/><def:leaf ID="L"/><ItemGroupDef OID="IG"/><CodeList OID="CL"/>
        </MetaDataVersion></Study></ODM>""")
    bad = violations(checks.element_order(), doc2, "//*[*]")
    assert [(doc2.display_name(v.node), v.detail.split(";")[0]) for v in bad] == \
        [("ItemGroupDef", "ItemGroupDef comes after def:leaf"), ("CodeList", "CodeList comes after def:leaf")]
    assert bad[0].detail.endswith("the order under MetaDataVersion is " + ", ".join(MDV_CHILDREN))


# ---------------------------------------------------------------------------------------------
# 3. the baseline, 4. the conformant fixture
# ---------------------------------------------------------------------------------------------

def test_baseline_on_the_sdtm_sample():
    result = DefineConformanceChecker(define_file()).check()
    assert {f.rule: len(f.locations) for f in result.findings} == BASELINE
    assert result.not_applicable == sorted(SUBMISSION_RULES, key=int)
    assert dict(result.not_evaluated) == NOT_EVALUATED
    assert result.context == "Other" and result.define_version == "2.1.9"
    assert result.rule_count == 225 and result.evaluated_count == 197 and len(result.passed) == 192
    assert result.has_errors and result.occurrence_count == 55


def test_baseline_locations_carry_lines_and_paths():
    finding = failed_rules(define_file())["73"]
    assert [loc.line for loc in finding.locations] == [556, 557]
    assert finding.locations[0].path.startswith("MetaDataVersion[MDV.CDISC01_1.1.SDTMIG.3.1.2.SDTM.1.2_X]/ItemGroupDef[IG.EC]/ItemRef[IT.EC.EXDOSE]")
    assert finding.locations[0].detail == \
        'ItemDef IT.EC.EXDOSE has def:Origin/@Type="Derived" but the ItemRef has no @MethodOID'
    assert finding.element == "ItemRef" and finding.attribute == "MethodOID" and finding.severity == "error"


def test_the_conformant_fixture_passes_every_evaluated_rule():
    result = DefineConformanceChecker(conformant_file()).check()
    assert result.findings == []
    assert result.not_applicable == [] and result.context == "Submission"
    assert result.evaluated_count == 210 and len(result.not_evaluated) == 15


def test_the_adam_sample_passes():
    # a Submission-context CDISC sample with ARM content and a Study OID containing "/"
    result = DefineConformanceChecker(adam_file()).check()
    assert result.findings == []
    assert result.evaluated_count == 210


def test_the_conformant_fixture_is_schema_valid_and_the_odm_shape_is_in_order():
    assert xmlschema.XMLSchema(str(DEFAULT_SCHEMA)).is_valid(str(conformant_file()))


# ---------------------------------------------------------------------------------------------
# 5. one mutation per implemented rule
# ---------------------------------------------------------------------------------------------

def _move_leaf_first(t):
    g = group(t, "IG.DM")
    lf = one(g, "def:leaf")
    g.remove(lf)
    g.insert(0, lf)


def _rename_root(t):
    t.getroot().tag = f"{{{ODM_NS}}}Foo"


def _second_odm(t):
    add(one(t, "//odm:Study"), "ODM")


def _two_descriptions(parent):
    add_description(parent, 0, "one")
    add_description(parent, 0, "two")


def _sub_class(t, attrs):
    add(one(group(t, "IG.DM"), "def:Class"), "def:SubClass", attrs=attrs)


def _leaf_id_with_a_digit_first(t):
    set_leaf_id(t, "LF.RG", "1.RG")


def _duplicate_comment(t):
    duplicate(comment(t, "COM.MDV"))


# rule id -> (the edit of the conformant fixture, the other rules the edit must also fail)
MUTATIONS = {
    # the document
    "1": (_move_leaf_first, ()),
    "2": (_rename_root, ()),
    "3": (_second_odm, ()),
    "230": (lambda t: set_attr(codelist(t, "CL.MEDDRA"), "OID", "CL.QNAM"), ()),
    # ODM
    "4": (lambda t: set_attr(t.getroot(), "CreationDateTime", "2026-01-15"), ()),
    "5": (lambda t: set_attr(t.getroot(), "AsOfDateTime", "yesterday"), ()),
    "6": (lambda t: del_attr(t.getroot(), "ODMVersion"), ()),
    "7": (lambda t: set_attr(t.getroot(), "ODMVersion", "1.3.1"), ()),
    "8": (lambda t: set_attr(t.getroot(), "FileType", "Transactional"), ()),
    "9": (lambda t: del_attr(t.getroot(), "FileOID"), ()),
    "13": (lambda t: del_attr(t.getroot(), "CreationDateTime"), ("254",)),
    "16": (lambda t: del_attr(t.getroot(), "def:Context"), ()),
    "17": (lambda t: set_attr(t.getroot(), "def:Context", "Draft"), ()),
    "254": (lambda t: del_attr(t.getroot(), "CreationDateTime"), ("13",)),
    "255": (lambda t: del_attr(t.getroot(), "FileType"), ()),
    # Study and GlobalVariables
    "10": (lambda t: remove(one(t, "//odm:Study")), ()),
    "11": (lambda t: duplicate(one(t, "//odm:Study")), ("230", "213", "216", "172")),
    "12": (lambda t: del_attr(one(t, "//odm:Study"), "OID"), ()),
    "14": (lambda t: remove(one(t, "//odm:GlobalVariables")), ()),
    "15": (lambda t: duplicate(one(t, "//odm:GlobalVariables")), ()),
    "18": (lambda t: remove(one(t, "//odm:StudyName")), ()),
    "19": (lambda t: duplicate(one(t, "//odm:StudyName")), ()),
    "20": (lambda t: remove(one(t, "//odm:StudyDescription")), ()),
    "21": (lambda t: duplicate(one(t, "//odm:StudyDescription")), ()),
    "22": (lambda t: remove(one(t, "//odm:ProtocolName")), ()),
    "23": (lambda t: duplicate(one(t, "//odm:ProtocolName")), ()),
    # MetaDataVersion
    "24": (lambda t: remove(mdv(t)), ()),
    "25": (lambda t: duplicate(mdv(t)), ("230", "213", "216", "172")),
    "26": (lambda t: del_attr(mdv(t), "OID"), ()),
    "27": (lambda t: del_attr(mdv(t), "Name"), ()),
    "28": (lambda t: set_attr(mdv(t), "def:DefineVersion", "2.1"), ()),
    "29": (lambda t: del_attr(mdv(t), "def:DefineVersion"), ()),
    "30": (lambda t: set_attr(mdv(t), "def:CommentOID", "COM.NONE"), ()),
    # def:Standards
    "31": (lambda t: remove(one(t, "//def:Standards")), ("124", "152")),
    "32": (lambda t: duplicate(one(t, "//def:Standards")), ("230",)),
    "33": (lambda t: del_attr(standard(t, "STD.SDTMIG"), "Name"), ()),
    "34": (lambda t: del_attr(standard(t, "STD.SDTMIG"), "Type"), ("124",)),
    "35": (lambda t: del_attr(standard(t, "STD.CT"), "PublishingSet"), ()),
    "36": (lambda t: del_attr(standard(t, "STD.SDTMIG"), "Version"), ()),
    "233": (lambda t: [remove(s) for s in find(t, "//def:Standard")], ("258", "124", "152")),
    "256": (lambda t: set_attr(standard(t, "STD.SDTMIG"), "def:CommentOID", "COM.NONE"), ()),
    "257": (lambda t: del_attr(standard(t, "STD.CT"), "OID"), ("152",)),
    "258": (lambda t: [remove(s) for s in find(t, "//def:Standard")], ("233", "124", "152")),
    "264": (lambda t: set_attr(standard(t, "STD.SDTMIG"), "Status", "Published"), ()),
    # documents
    "38": (lambda t: duplicate(one(t, "//def:AnnotatedCRF")), ()),
    "39": (lambda t: remove(one(t, "//def:AnnotatedCRF/def:DocumentRef")), ("159",)),
    "42": (lambda t: del_attr(one(t, "//def:AnnotatedCRF/def:DocumentRef"), "leafID"), ("159",)),
    "43": (lambda t: set_attr(one(t, "//def:AnnotatedCRF/def:DocumentRef"), "leafID", "LF.NONE"), ("159",)),
    "44": (lambda t: remove(page_ref(t, "IT.DM.SEX")), ()),
    "45": (lambda t: set_attr(page_ref(t, "IT.DM.SEX"), "Type", "Physical"), ()),
    "46": (lambda t: del_attr(page_ref(t, "IT.SUPPDM.QVAL.RACEOTH"), "Type"), ()),
    "47": (lambda t: set_attr(page_ref(t, "IT.SUPPDM.QVAL.RACEOTH"), "FirstPage", "four"), ()),
    "48": (lambda t: del_attr(page_ref(t, "IT.SUPPDM.QVAL.RACEOTH"), "FirstPage"), ()),
    "49": (lambda t: set_attr(page_ref(t, "IT.SUPPDM.QVAL.RACEOTH"), "LastPage", "x"), ()),
    "50": (lambda t: del_attr(page_ref(t, "IT.SUPPDM.QVAL.RACEOTH"), "LastPage"), ()),
    "51": (lambda t: duplicate(one(t, "//def:SupplementalDoc")), ()),
    "54": (lambda t: remove(one(t, "//def:SupplementalDoc/def:DocumentRef")), ()),
    # Description and TranslatedText
    "60": (lambda t: remove(one(description(group(t, "IG.DM")), "odm:TranslatedText")), ("61",)),
    "61": (lambda t: remove(one(description(comment(t, "COM.MDV")), "odm:TranslatedText")), ("60",)),
    "62": (lambda t: remove(one(t, "//odm:CodeListItem[@CodedValue='F']/odm:Decode/odm:TranslatedText")), ()),
    "63": (lambda t: duplicate(one(description(group(t, "IG.DM")), "odm:TranslatedText")), ()),
    # ItemGroupDef
    "93": (lambda t: [remove(g) for g in find(t, "//odm:ItemGroupDef")], ()),
    "94": (lambda t: del_attr(group(t, "IG.SUPPDM"), "OID"), ()),
    "104": (lambda t: del_attr(group(t, "IG.SUPPDM"), "Name"), ()),
    "105": (lambda t: del_attr(group(t, "IG.DM"), "Domain"), ()),
    "106": (lambda t: set_attr(standard(t, "STD.SDTMIG"), "Name", "ADaMIG"), ("252",)),
    "108": (lambda t: del_attr(group(t, "IG.DM"), "SASDatasetName"), ()),
    "109": (lambda t: set_attr(group(t, "IG.DM"), "SASDatasetName", "DEMOGRAPHICS1"), ("110", "112")),
    "110": (lambda t: set_attr(group(t, "IG.DM"), "SASDatasetName", "DM2"), ("112",)),
    "112": (lambda t: set_attr(leaf(t, "LF.DM"), "xlink:href", "demo.xpt"), ()),
    "113": (lambda t: del_attr(group(t, "IG.DM"), "Repeating"), ()),
    "114": (lambda t: set_attr(group(t, "IG.DM"), "Repeating", "Maybe"), ()),
    "115": (lambda t: set_attr(group(t, "IG.DM"), "IsReferenceData", "Maybe"), ()),
    "116": (lambda t: set_attr(group(t, "IG.DM"), "Purpose", "Other"), ("251",)),
    "117": (lambda t: del_attr(group(t, "IG.DM"), "Purpose"), ("251",)),
    "118": (lambda t: del_attr(group(t, "IG.DM"), "def:Structure"), ()),
    "119": (lambda t: del_attr(group(t, "IG.DM"), "def:ArchiveLocationID"), ("125",)),
    "120": (lambda t: set_attr(group(t, "IG.DM"), "def:ArchiveLocationID", "LF.NONE"), ()),
    "121": (lambda t: set_attr(group(t, "IG.DM"), "def:IsNonStandard", "Yes"), ()),
    "122": (lambda t: del_attr(group(t, "IG.DM"), "def:StandardOID"), ()),
    "123": (lambda t: (make_non_standard(t, "IG.SUPPDM"), set_attr(group(t, "IG.SUPPDM"), "def:IsNonStandard", "No")),
            ()),
    "124": (lambda t: set_attr(group(t, "IG.DM"), "def:StandardOID", "STD.CT"), ()),
    "125": (lambda t: del_attr(group(t, "IG.DM"), "def:ArchiveLocationID"), ("119",)),
    "126": (lambda t: set_attr(group(t, "IG.SUPPDM"), "def:HasNoData", "No"), ()),
    "127": (lambda t: set_attr(group(t, "IG.DM"), "def:CommentOID", "COM.NONE"), ()),
    "128": (lambda t: remove(description(group(t, "IG.DM"))), ()),
    "129": (lambda t: duplicate(description(group(t, "IG.DM"))), ()),
    "131": (lambda t: remove(one(group(t, "IG.DM"), "def:Class")), ()),
    "132": (lambda t: set_attr(one(group(t, "IG.DM"), "def:Class"), "Name", "DEMOGRAPHICS"), ()),
    "134": (lambda t: _sub_class(t, {}), ()),
    "238": (lambda t: del_attr(item_ref(t, "IG.DM", "IT.DM.SEX"), "OrderNumber"), ()),
    "239": (lambda t: set_attr(one(group(t, "IG.DM"), "def:Class"), "Name", "TRIAL DESIGN"), ()),
    "240": (lambda t: set_attr(group(t, "IG.SUPPDM"), "def:HasNoData", "Yes"), ()),
    "241": (lambda t: [remove(r) for r in find(group(t, "IG.SUPPDM"), "odm:ItemRef")], ("70",)),
    "251": (lambda t: set_attr(group(t, "IG.DM"), "Purpose", "Analysis"), ()),
    "252": (lambda t: set_attr(standard(t, "STD.SDTMIG"), "Name", "ADaMIG"), ("106",)),
    "260": (lambda t: set_attr(group(t, "IG.SUPPDM"), "IsReferenceData", "Yes"), ()),
    "261": (lambda t: _sub_class(t, {"Name": "OTHER"}), ()),
    "262": (lambda t: _sub_class(t, {"Name": "TIME-TO-EVENT", "ParentClass": "OTHER"}), ()),
    # Description on datasets, Alias, def:Class
    "57": (lambda t: (make_non_standard(t, "IG.SUPPDM"), remove(description(group(t, "IG.SUPPDM")))), ("128",)),
    "95": (lambda t: remove(one(group(t, "IG.SUPPDM"), "odm:Alias")), ("96",)),
    "96": (lambda t: remove(one(group(t, "IG.SUPPDM"), "odm:Alias")), ("95",)),
    "100": (lambda t: del_attr(one(group(t, "IG.SUPPDM"), "odm:Alias"), "Context"), ()),
    "101": (lambda t: del_attr(one(group(t, "IG.SUPPDM"), "odm:Alias"), "Name"), ()),
    # ItemRef
    "65": (lambda t: set_attr(item_ref(t, "IG.DM", "IT.DM.AGE"), "ItemOID", "IT.NONE"), ()),
    "66": (lambda t: set_attr(item_ref(t, "IG.DM", "IT.DM.AGE"), "OrderNumber", "first"), ()),
    "68": (lambda t: set_attr(item_ref(t, "IG.DM", "IT.DM.AGE"), "Mandatory", "Maybe"), ()),
    "69": (lambda t: del_attr(item_ref(t, "IG.DM", "IT.DM.AGE"), "Mandatory"), ()),
    "70": (lambda t: [del_attr(r, "KeySequence") for r in find(group(t, "IG.DM"), "odm:ItemRef[@KeySequence]")], ()),
    "71": (lambda t: set_attr(item_ref(t, "IG.DM", "IT.DM.USUBJID"), "KeySequence", "1"), ()),
    "72": (lambda t: set_attr(item_ref(t, "IG.DM", "IT.DM.USUBJID"), "KeySequence", "one"), ()),
    "73": (lambda t: del_attr(item_ref(t, "IG.DM", "IT.DM.AGE"), "MethodOID"), ()),
    "74": (lambda t: set_attr(item_ref(t, "IG.DM", "IT.DM.AGE"), "MethodOID", "MT.NONE"), ()),
    "75": (lambda t: set_attr(item_ref(t, "IG.DM", "IT.DM.AGE"), "def:IsNonStandard", "No"), ()),
    "77": (lambda t: set_attr(item_ref(t, "IG.DM", "IT.DM.AGE"), "def:HasNoData", "No"), ()),
    "79": (lambda t: add(item_ref(t, "IG.DM", "IT.DM.SEX"), "def:WhereClauseRef",
                         attrs={"WhereClauseOID": "WC.SUPPDM.QNAM.RACEOTH"}), ()),
    # ItemDef
    "55": (lambda t: remove(one(item(t, "IT.SUPPDM.QVAL"), "def:ValueListRef")), ("154", "155")),
    "135": (lambda t: duplicate(one(item(t, "IT.DM.SEX"), "odm:CodeListRef")), ()),
    "137": (lambda t: del_attr(item(t, "IT.SUPPDM.QVAL.RACEOTH"), "OID"), ("65",)),
    "138": (lambda t: del_attr(item(t, "IT.DM.AGE"), "Name"), ()),
    "139": (lambda t: del_attr(item(t, "IT.DM.AGE"), "DataType"), ()),
    "140": (lambda t: set_attr(item(t, "IT.DM.AGE"), "DataType", "number"), ("143",)),
    "141": (lambda t: del_attr(item(t, "IT.DM.AGE"), "Length"), ()),
    "142": (lambda t: set_attr(item(t, "IT.SUPPDM.QVAL.RACEOTH"), "Length", "300"), ()),
    "143": (lambda t: set_attr(item(t, "IT.DM.USUBJID"), "DataType", "date"), ()),
    "144": (lambda t: set_attr(item(t, "IT.DM.AGE"), "Length", "0"), ()),
    "145": (lambda t: set_attr(item(t, "IT.DM.AGE"), "DataType", "float"), ()),
    "146": (lambda t: set_attr(item(t, "IT.DM.AGE"), "SignificantDigits", "-1"), ()),
    "147": (lambda t: del_attr(item(t, "IT.DM.AGE"), "SASFieldName"), ()),
    "148": (lambda t: set_attr(item(t, "IT.DM.AGE"), "def:CommentOID", "COM.NONE"), ()),
    "151": (lambda t: set_attr(one(item(t, "IT.DM.SEX"), "odm:CodeListRef"), "CodeListOID", "CL.NONE"), ()),
    "154": (lambda t: remove(origin(t, "IT.DM.STUDYID")), ("155",)),
    "155": (lambda t: remove(origin(t, "IT.SUPPDM.QVAL.RACEOTH")), ("154",)),
    "162": (lambda t: duplicate(one(item(t, "IT.SUPPDM.QVAL"), "def:ValueListRef")), ()),
    "163": (lambda t: set_attr(one(item(t, "IT.SUPPDM.QVAL"), "def:ValueListRef"), "ValueListOID", "VL.NONE"), ()),
    "164": (lambda t: del_attr(one(item(t, "IT.SUPPDM.QVAL"), "def:ValueListRef"), "ValueListOID"), ()),
    "168": (lambda t: remove(description(item(t, "IT.DM.AGE"))), ()),
    "169": (lambda t: duplicate(description(item(t, "IT.DM.AGE"))), ()),
    "242": (lambda t: set_attr(item_ref(t, "IG.DM", "IT.DM.AGE"), "def:HasNoData", "Yes"), ()),
    # def:Origin
    "158": (lambda t: del_attr(origin(t, "IT.DM.AGE"), "Type"), ()),
    "159": (lambda t: remove(one(origin(t, "IT.DM.SEX"), "def:DocumentRef")), ()),
    "160": (lambda t: set_attr(origin(t, "IT.DM.AGE"), "Type", "Other"), ()),
    "161": (lambda t: set_attr(origin(t, "IT.DM.USUBJID"), "Source", "CRO"), ()),
    "243": (lambda t: _two_descriptions(origin(t, "IT.DM.AGE")), ()),
    # def:ValueListDef
    "235": (lambda t: _two_descriptions(one(t, "//def:ValueListDef")), ()),
    "236": (lambda t: del_attr(one(t, "//def:ValueListDef"), "OID"), ("163",)),
    "237": (lambda t: remove(one(t, "//def:ValueListDef/odm:ItemRef")), ()),
    # def:WhereClauseDef and RangeCheck
    "80": (lambda t: del_attr(one(t, "//def:WhereClauseRef"), "WhereClauseOID"), ()),
    "81": (lambda t: set_attr(one(t, "//def:WhereClauseRef"), "WhereClauseOID", "WC.NONE"), ()),
    "82": (lambda t: del_attr(one(t, "//def:WhereClauseDef"), "OID"), ("81",)),
    "83": (lambda t: set_attr(one(t, "//def:WhereClauseDef"), "def:CommentOID", "COM.NONE"), ()),
    "84": (lambda t: add_range_check(one(t, "//def:WhereClauseDef"), "IT.DM.SEX"), ()),
    "85": (lambda t: remove(one(t, "//odm:RangeCheck")), ()),
    "86": (lambda t: set_attr(one(t, "//odm:RangeCheck"), "Comparator", "EQUALS"), ()),
    "87": (lambda t: del_attr(one(t, "//odm:RangeCheck"), "Comparator"), ()),
    "88": (lambda t: set_attr(one(t, "//odm:RangeCheck"), "SoftHard", "Firm"), ()),
    "89": (lambda t: del_attr(one(t, "//odm:RangeCheck"), "SoftHard"), ()),
    "90": (lambda t: del_attr(one(t, "//odm:RangeCheck"), "def:ItemOID"), ()),
    "91": (lambda t: set_attr(one(t, "//odm:RangeCheck"), "def:ItemOID", "IT.NONE"), ()),
    "92": (lambda t: remove(one(t, "//odm:CheckValue")), ()),
    # CodeList
    "152": (lambda t: set_attr(codelist(t, "CL.SEX"), "def:StandardOID", "STD.SDTMIG"), ()),
    "153": (lambda t: del_attr(codelist(t, "CL.QNAM"), "def:IsNonStandard"), ()),
    "165": (lambda t: remove(one(codelist(t, "CL.QNAM"), "odm:EnumeratedItem")), ()),
    "166": (lambda t: del_attr(codelist(t, "CL.MEDDRA"), "OID"), ()),
    "167": (lambda t: set_attr(codelist(t, "CL.QNAM"), "def:IsNonStandard", "No"), ()),
    "171": (lambda t: del_attr(codelist(t, "CL.MEDDRA"), "Name"), ()),
    "172": (lambda t: set_attr(codelist(t, "CL.MEDDRA"), "Name", "Sex"), ()),
    "173": (lambda t: del_attr(codelist(t, "CL.MEDDRA"), "DataType"), ()),
    "174": (lambda t: set_attr(codelist(t, "CL.MEDDRA"), "DataType", "string"), ()),
    "175": (lambda t: set_attr(codelist(t, "CL.SEX"), "SASFormatName", "SEX"), ()),
    "176": (lambda t: del_attr(codelist(t, "CL.SEX"), "def:StandardOID"), ()),
    "177": (lambda t: set_attr(codelist(t, "CL.SEX"), "def:CommentOID", "COM.NONE"), ()),
    "244": (lambda t: _two_descriptions(codelist(t, "CL.SEX")), ()),
    "249": (lambda t: remove(one(codelist(t, "CL.SEX"), "odm:Alias")), ("153",)),
    "250": (lambda t: duplicate(one(t, "//odm:ExternalCodeList")), ()),
    # EnumeratedItem
    "178": (lambda t: set_attr(one(t, "//odm:EnumeratedItem"), "def:ExtendedValue", "No"), ()),
    "180": (lambda t: del_attr(one(t, "//odm:EnumeratedItem"), "CodedValue"), ()),
    "182": (lambda t: set_attr(one(t, "//odm:EnumeratedItem"), "Rank", "first"), ()),
    "183": (lambda t: (set_attr(one(t, "//odm:EnumeratedItem"), "Rank", "1"),
                       add(codelist(t, "CL.QNAM"), "EnumeratedItem", attrs={"CodedValue": "X", "OrderNumber": "2"})),
            ()),
    "184": (lambda t: set_attr(one(t, "//odm:EnumeratedItem"), "OrderNumber", "x"), ()),
    "185": (lambda t: add(codelist(t, "CL.QNAM"), "EnumeratedItem", attrs={"CodedValue": "X"}), ()),
    "245": (lambda t: _two_descriptions(one(t, "//odm:EnumeratedItem")), ()),
    # CodeListItem
    "191": (lambda t: del_attr(one(t, "//odm:CodeListItem[@CodedValue='F']"), "CodedValue"), ()),
    "193": (lambda t: set_attr(one(t, "//odm:CodeListItem[@CodedValue='F']"), "Rank", "x"), ("194",)),
    "194": (lambda t: set_attr(one(t, "//odm:CodeListItem[@CodedValue='F']"), "Rank", "1"), ()),
    "195": (lambda t: set_attr(one(t, "//odm:CodeListItem[@CodedValue='F']"), "OrderNumber", "x"), ()),
    "196": (lambda t: del_attr(one(t, "//odm:CodeListItem[@CodedValue='F']"), "OrderNumber"), ()),
    "197": (lambda t: set_attr(one(t, "//odm:CodeListItem[@CodedValue='F']"), "def:ExtendedValue", "No"), ()),
    "198": (lambda t: duplicate(one(t, "//odm:CodeListItem[@CodedValue='F']/odm:Decode")), ()),
    "199": (lambda t: remove(one(t, "//odm:CodeListItem[@CodedValue='F']/odm:Decode")), ()),
    "246": (lambda t: _two_descriptions(one(t, "//odm:CodeListItem[@CodedValue='F']")), ()),
    # ExternalCodeList
    "203": (lambda t: del_attr(one(t, "//odm:ExternalCodeList"), "Dictionary"), ()),
    "204": (lambda t: del_attr(one(t, "//odm:ExternalCodeList"), "Version"), ()),
    # MethodDef
    "56": (lambda t: remove(description(one(t, "//odm:MethodDef"))), ("210",)),
    "205": (lambda t: duplicate(description(one(t, "//odm:MethodDef"))), ()),
    "206": (lambda t: del_attr(one(t, "//odm:MethodDef"), "OID"), ("74",)),
    "207": (lambda t: del_attr(one(t, "//odm:MethodDef"), "Name"), ()),
    "208": (lambda t: del_attr(one(t, "//odm:MethodDef"), "Type"), ()),
    "209": (lambda t: set_attr(one(t, "//odm:MethodDef"), "Type", "Transpose"), ()),
    "210": (lambda t: remove(description(one(t, "//odm:MethodDef"))), ("56",)),
    "221": (lambda t: del_attr(one(t, "//odm:FormalExpression"), "Context"), ()),
    # def:CommentDef
    "212": (lambda t: del_attr(comment(t, "COM.MDV"), "OID"), ("30",)),
    "213": (_duplicate_comment, ("230",)),
    "214": (lambda t: remove(description(comment(t, "COM.MDV"))), ()),
    "215": (lambda t: duplicate(description(comment(t, "COM.MDV"))), ()),
    # def:leaf
    "216": (lambda t: duplicate(leaf(t, "LF.RG")), ()),
    "218": (lambda t: remove(one(leaf(t, "LF.RG"), "def:title")), ()),
    "219": (lambda t: duplicate(one(leaf(t, "LF.RG"), "def:title")), ()),
    "248": (lambda t: del_attr(leaf(t, "LF.RG"), "xlink:href"), ()),
    "259": (_leaf_id_with_a_digit_first, ()),
}


def test_the_mutation_table_covers_every_implemented_rule():
    implemented = {r.id for r in all_rules() if not r.requires}
    assert set(MUTATIONS) == implemented
    assert len(MUTATIONS) == 210


@pytest.mark.parametrize("rule_id", sorted(MUTATIONS, key=int))
def test_mutation_fails_exactly_that_rule(rule_id, edited_define):
    edit, also = MUTATIONS[rule_id]
    path = edited_define(edit, source=conformant_file())
    result = DefineConformanceChecker(path).check()
    assert {f.rule for f in result.findings} == {rule_id, *also}
    assert all(loc.line for f in result.findings for loc in f.locations)


# ---------------------------------------------------------------------------------------------
# 6. the enumerations and patterns against the bundled schema
# ---------------------------------------------------------------------------------------------

@pytest.fixture(scope="module")
def schema():
    return xmlschema.XMLSchema(str(DEFAULT_SCHEMA))


def _enumeration(xsd_type) -> set:
    """the enumeration facet of a simple type, through a union's member types"""
    values = set(getattr(xsd_type, "enumeration", None) or [])
    for member in getattr(xsd_type, "member_types", None) or []:
        values |= _enumeration(member)
    return values


def _simple_type(schema, name: str):
    for namespace in (DEF_NS, ODM_NS):
        xsd_type = schema.maps.types.get(f"{{{namespace}}}{name}")
        if xsd_type is not None:
            return xsd_type
    raise AssertionError(f"no simple type {name} in the bundled schemas")


@pytest.mark.parametrize("name", [name for name, values in V.XSD_TYPES.items() if values is not None])
def test_enumeration_matches_the_schema(schema, name):
    assert V.XSD_TYPES[name] == _enumeration(_simple_type(schema, name))


@pytest.mark.parametrize("name", sorted(V.XSD_DIVERGENCES))
def test_documented_divergences_from_the_schema(schema, name):
    # the rule text narrows these; the hand-coded set must be a strict subset of the schema's
    assert V.XSD_DIVERGENCES[name] < _enumeration(_simple_type(schema, name))


@pytest.mark.parametrize("name", sorted(V.XSD_PATTERNS))
@pytest.mark.parametrize("sample", ["AE", "ae_1", "_X", "1AE", "A" * 8, "A" * 9, "$SEX", "$SEX.", "A.B", "", "-A",
                                    "A-B", "$", "ab cd"])
def test_pattern_agrees_with_the_schema(schema, name, sample):
    xsd_type = _simple_type(schema, name)
    assert (V.XSD_PATTERNS[name].fullmatch(sample) is not None) == xsd_type.is_valid(sample)


def test_define_version_pattern_matches_the_schema(schema):
    xsd_type = _simple_type(schema, "DefineVersion")
    for sample in ["2.1.0", "2.1.9", "2.1.10", "2.1", "2.1.01", "2.0.0", "3.0.0"]:
        expected = xsd_type.is_valid(sample) or sample == "2.0.0"      # rule 28 admits 2.0.0 as well
        assert (V.DEFINE_VERSION.fullmatch(sample) is not None) == expected, sample


# ---------------------------------------------------------------------------------------------
# 7. loading and the CLI
# ---------------------------------------------------------------------------------------------

def test_missing_file_raises():
    with pytest.raises(DefineConformanceLoadError, match="not found"):
        DefineConformanceChecker(data_path() / "does_not_exist.xml")


def test_malformed_file_raises(tmp_path):
    bad_xml = tmp_path / "bad.xml"
    bad_xml.write_text("<ODM><broken></ODM>", encoding="utf-8")
    with pytest.raises(DefineConformanceLoadError, match="not well-formed"):
        DefineConformanceChecker(bad_xml).check()


def test_a_define_20_document_is_refused(tmp_path):
    define_20 = tmp_path / "define20.xml"
    define_20.write_text(f'<ODM xmlns="{ODM_NS}" xmlns:def="{DEF_20_NS}"><Study OID="S">'
                         f'<MetaDataVersion OID="M" def:DefineVersion="2.0.0"/></Study></ODM>', encoding="utf-8")
    with pytest.raises(DefineConformanceLoadError, match="Define-XML 2.0"):
        DefineConformanceChecker(define_20).check()


def test_a_non_odm_root_fails_only_rule_2(tmp_path):
    other = tmp_path / "other.xml"
    other.write_text("<Greeting>hello</Greeting>", encoding="utf-8")
    result = DefineConformanceChecker(other).check()
    assert [f.rule for f in result.findings] == ["2"]
    assert result.findings[0].locations[0].path == "Greeting"
    assert result.define_version is None and result.context is None


def test_unknown_rule_ids_raise():
    with pytest.raises(DefineConformanceError, match="Unknown rule id"):
        DefineConformanceChecker(define_file(), rules=["73", "999"])
    with pytest.raises(DefineConformanceError, match="999"):
        DefineConformanceChecker(define_file(), skip_rules=["999"])


def test_rule_selection():
    result = DefineConformanceChecker(define_file(), rules=["73", "110", "179"]).check()
    assert [f.rule for f in result.findings] == ["73"]
    assert result.passed == ["110"] and result.not_evaluated == [("179", NEEDS_CT)]
    assert len(result.skipped) == 222 and result.evaluated_count == 2
    skipped = DefineConformanceChecker(define_file(), skip_rules=["73", "159"]).check()
    assert {f.rule for f in skipped.findings} == {"153", "240", "249"}
    assert skipped.skipped == ["73", "159"]


def test_result_is_cached():
    checker = DefineConformanceChecker(define_file())
    assert checker.check() is checker.check()


def test_cli_exit_code_failed(run_cli):
    completed = run_cli("defineconform", "-d", str(define_file()))
    assert completed.returncode == 1
    assert b"[73]   ItemRef/@MethodOID   (2 occurrences)" in completed.stdout
    assert b"NOT APPLICABLE (13 rules)" in completed.stdout
    assert b"225 rules: 197 evaluated, 192 passed, 5 failed (55 occurrences), 13 not applicable, 15 not evaluated" \
        in completed.stdout
    assert completed.stderr == b""


def test_cli_exit_code_passed(run_cli):
    completed = run_cli("defineconform", "-d", str(conformant_file()))
    assert completed.returncode == 0
    assert b"No conformance rule violations found." in completed.stdout
    assert b"NOT APPLICABLE" not in completed.stdout


def test_cli_exit_code_missing_file(run_cli):
    completed = run_cli("defineconform", "-d", "does_not_exist.xml")
    assert completed.returncode == 2
    assert b"not found" in completed.stderr and b"Traceback" not in completed.stderr


def test_cli_exit_code_malformed_file(tmp_path, run_cli):
    bad_xml = tmp_path / "bad.xml"
    bad_xml.write_text("<ODM><broken></ODM>", encoding="utf-8")
    completed = run_cli("defineconform", "-d", str(bad_xml))
    assert completed.returncode == 2
    assert b"not well-formed" in completed.stderr and b"Traceback" not in completed.stderr


def test_cli_exit_code_unknown_rule(run_cli):
    completed = run_cli("defineconform", "-d", str(define_file()), "--rules", "73,999")
    assert completed.returncode == 2
    assert b"Unknown rule id(s): 999" in completed.stderr


def test_cli_exit_code_unwritable_out(tmp_path, run_cli):
    completed = run_cli("defineconform", "-d", str(define_file()), "-o", str(tmp_path))
    assert completed.returncode == 2
    assert b"directory" in completed.stderr


def test_cli_requires_a_define_or_list_rules(run_cli):
    completed = run_cli("defineconform")
    assert completed.returncode == 2
    assert b"-d/--define" in completed.stderr and b"Traceback" not in completed.stderr


def test_cli_list_rules(run_cli):
    completed = run_cli("defineconform", "--list-rules")
    assert completed.returncode == 0
    lines = completed.stdout.decode().splitlines()
    assert len(lines) == 225
    assert lines[0].startswith("  1  document") and "ALL elements" in lines[0]
    assert re.search(r"^ 70  submission\s+ItemRef/@KeySequence", "\n".join(lines), re.MULTILINE)
    assert re.search(r"^179  needs ct\s+EnumeratedItem/@CodedValue\s+Specification\s+2.1 only", "\n".join(lines),
                     re.MULTILINE)


def test_cli_json(run_cli):
    completed = run_cli("defineconform", "-d", str(define_file()), "--json")
    assert completed.returncode == 1
    report = json.loads(completed.stdout)
    assert report["counts"] == {"rules": 225, "evaluated": 197, "passed": 192, "failed": 5, "occurrences": 55,
                                "not_applicable": 13, "not_evaluated": 15, "skipped": 0}
    assert {f["rule"]: len(f["locations"]) for f in report["findings"]} == BASELINE
    first = report["findings"][0]
    assert first["locations"][0] == {"path": "MetaDataVersion[MDV.CDISC01_1.1.SDTMIG.3.1.2.SDTM.1.2_X]/"
                                             "ItemGroupDef[IG.EC]/ItemRef[IT.EC.EXDOSE]",
                                     "line": 556,
                                     "detail": 'ItemDef IT.EC.EXDOSE has def:Origin/@Type="Derived" but the ItemRef '
                                               "has no @MethodOID"}
    assert first["cdisc_message"].startswith("ItemRef[@ItemOID] is missing the MethodOID")
    assert report["not_evaluated"][0] == {"rule": "67", "requires": "ig"}
    assert report["context"] == "Other" and report["define_version"] == "2.1.9"


def test_cli_out_file_round_trip(tmp_path, run_cli):
    out_file = tmp_path / "report.json"
    completed = run_cli("defineconform", "-d", str(define_file()), "-o", str(out_file), "--json")
    assert completed.returncode == 1 and completed.stdout == b""
    assert json.loads(out_file.read_text(encoding="utf-8"))["counts"]["failed"] == 5
    text_file = tmp_path / "report.txt"
    run_cli("defineconform", "-d", str(define_file()), "-o", str(text_file), "-L", "0")
    text = text_file.read_text(encoding="utf-8")
    assert text.count("- line ") == 55 and "... and" not in text


def test_cli_rules_and_skip_rules(run_cli):
    completed = run_cli("defineconform", "-d", str(define_file()), "--rules", "73,110")
    assert completed.returncode == 1
    assert b"SKIPPED (223 rules)" in completed.stdout
    assert b"225 rules: 2 evaluated, 1 passed, 1 failed (2 occurrences), 0 not applicable, 0 not evaluated, " \
           b"223 skipped" in completed.stdout
    completed = run_cli("defineconform", "-d", str(define_file()), "--skip-rules", "73,153,159,240,249")
    assert completed.returncode == 0
    assert b"No conformance rule violations found." in completed.stdout


def test_cli_unexpected_error_returns_3_with_a_traceback(monkeypatch, capsys):
    from defineutils.conformance import __main__ as conformance_cli

    def crash(self):
        raise RuntimeError("simulated defect")

    monkeypatch.setattr(DefineConformanceChecker, "check", crash)
    monkeypatch.setattr(sys, "argv", ["defineconform", "-d", str(define_file())])

    assert conformance_cli.main() == 3
    stderr = capsys.readouterr().err
    assert "Traceback" in stderr and "RuntimeError: simulated defect" in stderr


def test_cli_broken_pipe_is_left_to_the_entry_point(monkeypatch):
    # quitting a pager exits 0 at the entry point; main() must not report it as a crash
    from defineutils.conformance import __main__ as conformance_cli

    def closed_pipe(self):
        raise BrokenPipeError()

    monkeypatch.setattr(DefineConformanceChecker, "check", closed_pipe)
    monkeypatch.setattr(sys, "argv", ["defineconform", "-d", str(define_file())])

    with pytest.raises(BrokenPipeError):
        conformance_cli.main()


# ---------------------------------------------------------------------------------------------
# 8. the reports and the file-write errors
# ---------------------------------------------------------------------------------------------

def test_text_report_truncates_locations():
    text = DefineConformanceChecker(define_file()).check_to_string(max_locations=2)
    assert "  [159]  def:Origin/@Type   (30 occurrences)" in text
    assert "         ... and 28 more" in text
    assert text.count("- line ") == 2 + 2 + 2 + 1 + 2


def test_text_report_header_and_sections():
    text = DefineConformanceChecker(define_file()).check_to_string()
    assert text.startswith("Define-XML conformance check\n  File:     ")
    assert "  Version:  Define-XML 2.1.9    Context: Other\n" in text
    assert "  Rules:    CDISC Define-XML v2.1 Conformance Rules (225)\n" in text
    assert 'Require ODM/@def:Context="Submission"; this document declares "Other":' in text
    assert "  Need CDISC controlled terminology:      179, 186, 187, 192, 201, 202" in text
    assert "  Need implementation-guide metadata:     67, 97, 98, 99, 149, 263, 265, 266" in text
    assert "  Need the datasets:                      76" in text


def test_check_to_console(capsys):
    DefineConformanceChecker(conformant_file()).check_to_console()
    assert "No conformance rule violations found." in capsys.readouterr().out


def test_check_to_file_text_and_json(tmp_path):
    checker = DefineConformanceChecker(define_file())
    checker.check_to_file(tmp_path / "report.txt")
    assert (tmp_path / "report.txt").read_text(encoding="utf-8").startswith("Define-XML conformance check")
    checker.check_to_file(tmp_path / "report.json", as_json=True)
    assert json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))["counts"]["rules"] == 225


def test_unwritable_out_file_raises(tmp_path):
    with pytest.raises(DefineConformanceLoadError, match="not found"):
        DefineConformanceChecker(define_file()).check_to_file(tmp_path / "missing" / "report.txt")
    with pytest.raises(DefineConformanceLoadError, match="directory"):
        DefineConformanceChecker(define_file()).check_to_file(tmp_path)


def test_locations_drop_the_odm_and_study_prefix_even_with_a_slash_in_the_study_oid(tmp_path, edited_define):
    # define-adam.xml's Study OID is "CDISC-Sample/ADaM"; a path split on "/" would keep half of it
    path = edited_define(lambda t: del_attr(find(t, "//odm:MethodDef")[0], "Name"), source=adam_file())
    finding = failed_rules(path)["207"]
    assert finding.locations[0].path.startswith("MetaDataVersion[MDV.CDISC01.ADaMIG.1.1.ADaM.2.1]/MethodDef[")
