import inspect
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

import pytest
from lxml import etree
from odmlib.odm_element import ODMElement

from defineutils.metrics import DefineMetrics, DefineMetricsError

ODM_NS = "http://www.cdisc.org/ns/odm/v1.3"
DEF_NS = "http://www.cdisc.org/ns/def/v2.1"
NS = {"odm": ODM_NS, "def": DEF_NS}


def data_path() -> Path:
    return Path(__file__).parent


def define_file() -> Path:
    return data_path() / "define.xml"


def _mdv(tree):
    return tree.getroot().find(".//odm:MetaDataVersion", NS)


def _write(tree, path: Path) -> Path:
    tree.write(str(path), xml_declaration=True, encoding="UTF-8")
    return path


def _raw_counts() -> Counter:
    """An independent census of tests/define.xml: every element counted by local name,
    with no odmlib involved. The metrics traversal has to agree with this exactly. The
    file's comments are skipped -- lxml yields them from iter() with a callable tag, and
    odmlib drops them at load, so they are not document content on either side."""
    counts = Counter()
    for element in etree.parse(str(define_file())).getroot().iter():
        if isinstance(element.tag, str):
            counts[etree.QName(element).localname] += 1
    return counts


def _model_element_classes() -> set:
    """The element classes the odmlib define_2_1 model itself declares."""
    import odmlib.define_2_1.model as model

    return {name for name, obj in vars(model).items()
            if inspect.isclass(obj) and issubclass(obj, ODMElement)
            and obj.__module__ == model.__name__}


@pytest.fixture(scope="module")
def result():
    return DefineMetrics(define_file()).collect()


@pytest.fixture
def no_methods_define(tmp_path: Path) -> Path:
    """A copy of tests/define.xml with every MethodDef removed. The MethodOID references
    left behind are dangling, which metrics does not care about -- it counts, it does not
    check -- and the file still strict-loads, so MethodDef must be reported as 0."""
    tree = etree.parse(str(define_file()))
    mdv = _mdv(tree)
    for method in mdv.findall("odm:MethodDef", NS):
        mdv.remove(method)
    return _write(tree, tmp_path / "no_methods.xml")


@pytest.fixture
def non_conformant_define(tmp_path: Path) -> Path:
    """A copy with a required attribute removed, so odmlib refuses to strict-load it."""
    tree = etree.parse(str(define_file()))
    del _mdv(tree).findall("odm:ItemDef", NS)[0].attrib["DataType"]
    return _write(tree, tmp_path / "no_datatype.xml")


# 1. every count cross-checked against an independent census

def test_counts_match_an_independent_census(result):
    raw = _raw_counts()

    assert {e.element: e.count for e in result.elements if e.count} == \
           {name: count for name, count in raw.items()}


def test_total_elements_matches_the_raw_total(result):
    assert result.total_elements == sum(_raw_counts().values())
    assert result.total_elements == 2090


def test_headline_counts(result):
    assert result.count("ItemGroupDef") == 11
    assert result.count("ItemDef") == 179
    assert result.count("CodeList") == 40
    assert result.count("MethodDef") == 33
    assert result.count("leaf") == 12
    assert result.count("TranslatedText") == 357


# 2. an element the document does not use is reported as 0, never omitted

def test_absent_elements_are_reported_as_zero(result):
    absent = {e.element: e.count for e in result.elements if e.count == 0}

    assert absent == {"AnnotatedCRF": 0, "SubClass": 0}


def test_removing_every_method_def_leaves_a_zero_row(no_methods_define: Path):
    result = DefineMetrics(no_methods_define).collect()

    method_def = [e for e in result.elements if e.element == "MethodDef"]
    assert [(e.count, e.section) for e in method_def] == [(0, "definitions")]
    # every FormalExpression in this file belongs to a MethodDef, so it zeroes out too
    assert result.count("FormalExpression") == 0
    assert result.element_types_absent == 4


# 3. the inventory comes from the model, so it cannot silently change

def test_inventory_is_every_model_element_class(result):
    assert {e.element for e in result.elements} == _model_element_classes()
    assert result.element_types == 39


def test_inventory_sections(result):
    sections = {}
    for element in result.elements:
        sections.setdefault(element.section, []).append(element.element)

    assert sections["document"] == ["ODM", "Study", "GlobalVariables", "MetaDataVersion",
                                    "StudyName", "StudyDescription", "ProtocolName"]
    # the definitions section is exactly the MetaDataVersion's own children
    assert sections["definitions"] == ["Standards", "AnnotatedCRF", "SupplementalDoc",
                                       "ValueListDef", "WhereClauseDef", "ItemGroupDef",
                                       "ItemDef", "CodeList", "MethodDef", "CommentDef",
                                       "leaf"]
    assert len(sections["nested"]) == 21


def test_define_namespace_elements_are_displayed_with_their_prefix(result):
    displays = {e.element: e.display for e in result.elements}

    assert displays["leaf"] == "def:leaf"
    assert displays["Origin"] == "def:Origin"
    assert displays["ItemDef"] == "ItemDef"


def test_item_def_keeps_its_define_xml_shape(result):
    """Regression test for the inherited-descriptor trap: define_2_1.MetaDataVersion holds
    ODM 1.3.2 descriptors for ItemDef and friends, so a walk that followed
    descriptor.element_class instead of resolving by name would pull in the ODM-only
    Question/ExternalQuestion/MeasurementUnitRef/ErrorMessage and drop def:Origin."""
    counted = {e.element for e in result.elements}

    assert {"Origin", "ValueListRef", "Class", "leaf"} <= counted
    assert not counted & {"Question", "ExternalQuestion", "MeasurementUnitRef", "ErrorMessage"}


# 4. file and study identity

def test_file_metrics(result):
    assert result.size_bytes == define_file().stat().st_size
    assert result.size_bytes == 174322
    assert result.file_modified  # ISO 8601 from the file system, not from the document
    assert result.define_file == str(define_file())


def test_document_metrics(result):
    assert result.creation_datetime == "2024-11-21T16:27:00"
    assert result.file_oid == "www.cdisc.org/StudyCDISC01_1/1/Define-XML_2.1.0"
    assert result.odm_version == "1.3.2"
    assert result.define_version == "2.1.9"
    assert result.context == "Other"
    assert result.model_package == "define_2_1"
    assert result.permissive is False


def test_study_metrics(result):
    assert result.study_name == "CDISC01_1"
    assert result.protocol_name == "CDISC01-1"
    assert result.study_oid == "STDY.www.cdisc.org.CDISC01_1"
    assert result.study_description.startswith("CDISC Test Study Modified")
    assert result.mdv_oid == "MDV.CDISC01_1.1.SDTMIG.3.1.2.SDTM.1.2_X"
    assert result.mdv_name == "Study CDISC01_1, Data Definitions V-1"


def test_standards(result):
    assert len(result.standards) == 6
    assert result.count("Standard") == 6
    first = result.standards[0]
    assert (first.oid, first.name, first.type, first.version, first.status) == \
           ("STD.1", "SDTMIG", "IG", "3.1.2", "Final")


# 5. the per-dataset table

def test_dataset_count_and_variable_counts(result):
    mdv = _mdv(etree.parse(str(define_file())))
    expected = [(group.get("OID"), len(group.findall("odm:ItemRef", NS)))
                for group in mdv.findall("odm:ItemGroupDef", NS)]

    assert [(d.oid, d.variable_count) for d in result.datasets] == expected
    assert len(result.datasets) == 11


def test_variable_references_total_counts_dataset_item_refs_only(result):
    """The dataset total is the ItemRefs under ItemGroupDefs (155). The document holds 199
    ItemRefs in all -- the other 44 belong to def:ValueListDefs, which are value-level
    metadata rather than dataset variables -- so the two numbers differ by design."""
    mdv = _mdv(etree.parse(str(define_file())))
    in_datasets = sum(len(g.findall("odm:ItemRef", NS))
                      for g in mdv.findall("odm:ItemGroupDef", NS))

    assert result.total_variable_refs == in_datasets == 155
    assert result.count("ItemRef") == 199


def test_dataset_attributes(result):
    dataset = {d.oid: d for d in result.datasets}["IG.TS"]

    assert (dataset.name, dataset.domain, dataset.dataset_class) == ("TS", "TS", "TRIAL DESIGN")
    assert (dataset.repeating, dataset.purpose) == ("No", "Tabulation")
    assert dataset.archive_location_id == "LF.TS"
    assert dataset.structure == "One record per trial summary parameter value"
    assert dataset.has_no_data is None            # optional and not set on this dataset
    assert {d.oid for d in result.datasets if d.has_no_data == "Yes"} == {"IG.XX", "IG.SUPPVS"}


# 6. report plumbing

def test_result_is_cached():
    metrics = DefineMetrics(define_file())

    assert metrics.collect() is metrics.collect()


def test_text_report_sections_and_zero_rows():
    listing = DefineMetrics(define_file()).collect_to_string()

    for heading in ("Define-XML metrics", "STUDY", "ELEMENT COUNTS", "Document",
                    "MetaDataVersion definitions", "Nested elements", "DATASETS (11)",
                    "SUMMARY"):
        assert heading in listing
    assert "def:AnnotatedCRF       0" in listing
    assert "2,090 elements across 39 element types (37 present, 2 absent)" in listing
    assert "NOTE: loaded in permissive mode" not in listing


def test_text_report_dataset_table():
    listing = DefineMetrics(define_file()).collect_to_string()

    assert "OID        Name    Class            Repeating  No data  Variables" in listing
    assert "IG.TS      TS      TRIAL DESIGN     No         -                6" in listing
    assert "Total          155" in listing


def test_no_datasets_omits_the_table():
    listing = DefineMetrics(define_file()).collect_to_string(show_datasets=False)

    assert "DATASETS" not in listing
    assert "ELEMENT COUNTS" in listing
    assert "SUMMARY" in listing


def test_json_report_structure():
    report = json.loads(DefineMetrics(define_file()).collect_to_json())

    assert list(report) == ["define_file", "model_package", "odmlib_version", "permissive",
                            "file", "document", "study", "standards", "element_counts",
                            "datasets", "totals"]
    assert report["file"]["size_bytes"] == define_file().stat().st_size
    assert report["document"]["creation_datetime"] == "2024-11-21T16:27:00"
    assert report["study"]["study_name"] == "CDISC01_1"
    assert report["totals"] == {"elements": 2090, "element_types": 39,
                                "element_types_present": 37, "element_types_absent": 2,
                                "datasets": 11, "variable_references": 155}


def test_json_report_keeps_every_element_type_in_model_order():
    report = json.loads(DefineMetrics(define_file()).collect_to_json())
    counts = report["element_counts"]

    assert len(counts) == 39
    assert counts[0] == {"element": "ODM", "display": "ODM", "namespace": "odm",
                         "section": "document", "count": 1}
    assert {c["element"] for c in counts if c["count"] == 0} == {"AnnotatedCRF", "SubClass"}


def test_json_report_keeps_long_free_text_whole():
    """The JSON report never truncates. This file's MetaDataVersion description runs to
    several hundred characters -- longer than the text report's column -- and has to
    survive intact for a consumer that reads the JSON."""
    report = json.loads(DefineMetrics(define_file()).collect_to_json())

    description = report["study"]["metadata_version"]["description"]
    assert len(description) > 600
    assert description.startswith("Data Definitions for CDISC01-01 SDTM datasets.")


def test_text_report_truncates_a_long_description(tmp_path: Path):
    """tests/define.xml has a short StudyDescription, so truncation needs a longer one."""
    tree = etree.parse(str(define_file()))
    description = tree.getroot().find(".//odm:StudyDescription", NS)
    description.text = "long description " * 20
    padded = _write(tree, tmp_path / "long_description.xml")

    listing = DefineMetrics(padded).collect_to_string()

    assert "…" in listing
    assert len(json.loads(DefineMetrics(padded).collect_to_json())
               ["study"]["study_description"]) == len(description.text)


def test_collect_to_file_text(tmp_path: Path):
    out_file = tmp_path / "metrics.txt"

    DefineMetrics(define_file()).collect_to_file(out_file)

    assert "ELEMENT COUNTS" in out_file.read_text(encoding="utf-8")


def test_collect_to_file_json(tmp_path: Path):
    out_file = tmp_path / "metrics.json"

    DefineMetrics(define_file()).collect_to_file(out_file, as_json=True)

    assert json.loads(out_file.read_text(encoding="utf-8"))["totals"]["elements"] == 2090


def test_collect_to_console(capsys):
    DefineMetrics(define_file()).collect_to_console()

    assert "Define-XML metrics" in capsys.readouterr().out


# 7. failure paths

def test_missing_file_raises():
    with pytest.raises(DefineMetricsError, match="not found"):
        DefineMetrics(Path("does_not_exist.xml"))


def test_malformed_file_recommends_the_validate_utility(tmp_path: Path):
    bad_xml = tmp_path / "bad.xml"
    bad_xml.write_text("<ODM><broken></ODM>", encoding="utf-8")

    with pytest.raises(DefineMetricsError, match="python -m defineutils.validate"):
        DefineMetrics(bad_xml).collect()


def test_non_conformant_file_suggests_permissive(non_conformant_define: Path):
    with pytest.raises(DefineMetricsError, match="add --permissive"):
        DefineMetrics(non_conformant_define).collect()


def test_permissive_collects_metrics_from_a_non_conformant_file(non_conformant_define: Path):
    result = DefineMetrics(non_conformant_define, permissive=True).collect()

    assert result.permissive is True
    assert result.count("ItemDef") == 179
    assert "NOTE: loaded in permissive mode" in \
           DefineMetrics(non_conformant_define, permissive=True).collect_to_string()


def test_unwritable_out_file_raises(tmp_path: Path):
    with pytest.raises(DefineMetricsError, match="directory"):
        DefineMetrics(define_file()).collect_to_file(tmp_path)


# the CLI

def _run_cli(*cli_args) -> subprocess.CompletedProcess:
    """Run `python -m defineutils.metrics` from the repo root so the package resolves
    whether or not it is installed."""
    return subprocess.run([sys.executable, "-m", "defineutils.metrics", *cli_args],
                          capture_output=True, cwd=str(data_path().parent))


def test_cli_exit_code_success():
    completed = _run_cli("-d", str(define_file()))

    assert completed.returncode == 0
    assert b"Define-XML metrics" in completed.stdout
    assert b"Traceback" not in completed.stderr


def test_cli_exit_code_missing_file():
    completed = _run_cli("-d", "does_not_exist.xml")

    assert completed.returncode == 2
    assert b"not found" in completed.stderr
    assert completed.stdout == b""


def test_cli_exit_code_load_failure(tmp_path: Path):
    bad_xml = tmp_path / "bad.xml"
    bad_xml.write_text("<ODM><broken></ODM>", encoding="utf-8")

    completed = _run_cli("-d", str(bad_xml))

    assert completed.returncode == 2
    assert b"python -m defineutils.validate" in completed.stderr
    assert b"Traceback" not in completed.stderr


def test_cli_exit_code_unwritable_out(tmp_path: Path):
    completed = _run_cli("-d", str(define_file()), "-o", str(tmp_path))

    assert completed.returncode == 2
    assert b"Traceback" not in completed.stderr


def test_cli_json_to_file(tmp_path: Path):
    out_file = tmp_path / "metrics.json"

    completed = _run_cli("-d", str(define_file()), "-o", str(out_file), "--json")

    assert completed.returncode == 0
    assert json.loads(out_file.read_text(encoding="utf-8"))["totals"]["datasets"] == 11


def test_cli_no_datasets():
    completed = _run_cli("-d", str(define_file()), "--no-datasets")

    assert completed.returncode == 0
    assert b"DATASETS" not in completed.stdout
    assert b"ELEMENT COUNTS" in completed.stdout


def test_cli_permissive(non_conformant_define: Path):
    completed = _run_cli("-d", str(non_conformant_define), "--permissive")

    assert completed.returncode == 0
    assert b"NOTE: loaded in permissive mode" in completed.stdout
