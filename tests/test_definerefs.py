import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest
from lxml import etree

from defineutils.definerefs import DefineRefChecker, DefineRefCheckError

ODM_NS = "http://www.cdisc.org/ns/odm/v1.3"
DEF_NS = "http://www.cdisc.org/ns/def/v2.1"
NS = {"odm": ODM_NS, "def": DEF_NS}


def data_path() -> Path:
    return Path(__file__).parent


def define_file() -> Path:
    return data_path() / "define.xml"


def _mdv(tree):
    return tree.getroot().find(".//odm:MetaDataVersion", NS)


def _item_group(mdv, oid):
    return [g for g in mdv.findall("odm:ItemGroupDef", NS) if g.get("OID") == oid][0]


def _item_def(mdv, oid):
    return [d for d in mdv.findall("odm:ItemDef", NS) if d.get("OID") == oid][0]


def _item_ref(parent, item_oid):
    return [r for r in parent.findall("odm:ItemRef", NS) if r.get("ItemOID") == item_oid][0]


def _write(tree, path: Path) -> Path:
    tree.write(str(path), xml_declaration=True, encoding="UTF-8")
    return path


def _checks(result, check: str) -> set:
    return {f.oid for f in result.findings if f.check == check}


@pytest.fixture
def broken_define(tmp_path: Path) -> Path:
    """A copy of tests/define.xml broken in six ways. It stays well-formed and conformant
    enough for odmlib to strict-load, so the checker runs end to end on it: two duplicate
    OIDs, two dangling OID references, a dangling document reference, a type mismatch, and
    orphans (IT.TS.TSSEQ and the def:leaf LF.TS fall out of the retargeted references)."""
    tree = etree.parse(str(define_file()))
    mdv = _mdv(tree)
    ts, dm = _item_group(mdv, "IG.TS"), _item_group(mdv, "IG.DM")
    # a dangling ItemOID, which also leaves IT.TS.TSSEQ referenced by nothing
    _item_ref(ts, "IT.TS.TSSEQ").set("ItemOID", "IT.DOES.NOT.EXIST")
    # a dangling MethodOID
    [r for r in mdv.iter(f"{{{ODM_NS}}}ItemRef") if r.get("MethodOID")][0].set(
        "MethodOID", "MT.DOES.NOT.EXIST")
    # an ItemOID pointing at a CodeList; IT.STUDYID stays referenced by the other datasets
    _item_ref(dm, "IT.STUDYID").set("ItemOID", "CL.AGEU")
    # a dangling def:ArchiveLocationID, which also leaves the def:leaf LF.TS referenced by nothing
    ts.set(f"{{{DEF_NS}}}ArchiveLocationID", "LF.NO.SUCH.LEAF")
    # duplicate OIDs on an ItemDef and a CodeList
    item_def = _item_def(mdv, "IT.DM.AGE")
    item_def.addnext(deepcopy(item_def))
    code_list = [c for c in mdv.findall("odm:CodeList", NS) if c.get("OID") == "CL.AGEU"][0]
    code_list.addnext(deepcopy(code_list))
    # an ItemDef nothing references
    orphan = deepcopy(item_def)
    orphan.set("OID", "IT.ORPHAN.NEVER.USED")
    mdv.findall("odm:ItemDef", NS)[-1].addnext(orphan)
    return _write(tree, tmp_path / "broken_define.xml")


@pytest.fixture
def duplicate_itemgroup_define(tmp_path: Path) -> Path:
    """A copy of tests/define.xml with a duplicated ItemGroupDef OID. odmlib 0.2.0 returns
    early for its skip_elem classes before the uniqueness test, so its own checker misses
    this; the checker under test does not."""
    tree = etree.parse(str(define_file()))
    item_group = _item_group(_mdv(tree), "IG.TS")
    item_group.addnext(deepcopy(item_group))
    return _write(tree, tmp_path / "duplicate_itemgroup.xml")


@pytest.fixture
def many_references_define(tmp_path: Path) -> Path:
    """A copy of tests/define.xml whose IT.STUDYID ItemDef is renamed, so the several
    ItemRefs that point at IT.STUDYID all dangle."""
    tree = etree.parse(str(define_file()))
    _item_def(_mdv(tree), "IT.STUDYID").set("OID", "IT.STUDYID.RENAMED")
    return _write(tree, tmp_path / "many_references.xml")


@pytest.fixture
def nonconformant_define(tmp_path: Path) -> Path:
    """A copy of tests/define.xml missing an attribute the model requires. It is well-formed
    XML, so it fails the strict load but loads in permissive mode."""
    tree = etree.parse(str(define_file()))
    del _item_def(_mdv(tree), "IT.DM.AGE").attrib["DataType"]
    return _write(tree, tmp_path / "nonconformant.xml")


def test_check_clean_define_has_no_errors():
    result = DefineRefChecker(define_file()).check()

    assert result.errors == []
    assert result.has_errors is False
    assert result.model_package == "define_2_1"


def test_check_clean_define_reports_known_orphan():
    # the shipped sample really does define Standard STD.5 without referencing it
    result = DefineRefChecker(define_file()).check()

    orphans = [f for f in result.warnings if f.check == "orphan_definition"]
    assert [f.oid for f in orphans] == ["STD.5"]
    assert orphans[0].severity == "warning"
    assert "StandardOID" in orphans[0].message


def test_check_counts_definitions_and_references():
    # the traversal counts every definition (including the 12 def:leaf elements) and every
    # reference occurrence, not odmlib's de-duplicated sets of OID values
    result = DefineRefChecker(define_file()).check()

    assert result.definition_count == 353
    assert result.reference_count == 546
    assert "leafID" in result.checked_attributes
    assert "ArchiveLocationID" in result.checked_attributes
    assert "FileOID" in result.skipped_attributes
    assert result.unmapped_attributes == []


def test_check_reports_all_findings_not_just_first(broken_define: Path):
    # the reason for the custom traversal: odmlib's checker raises on the first violation
    result = DefineRefChecker(broken_define).check()

    assert _checks(result, "duplicate_oid") == {"IT.DM.AGE", "CL.AGEU"}
    assert _checks(result, "undefined_reference") == {"IT.DOES.NOT.EXIST", "MT.DOES.NOT.EXIST"}
    assert _checks(result, "undefined_document_reference") == {"LF.NO.SUCH.LEAF"}
    assert _checks(result, "type_mismatch") == {"CL.AGEU"}
    assert {"STD.5", "IT.TS.TSSEQ", "IT.ORPHAN.NEVER.USED"} <= _checks(result, "orphan_definition")
    assert _checks(result, "orphan_document_leaf") == {"LF.TS"}
    assert result.has_errors is True


def test_check_reports_type_mismatch_details(broken_define: Path):
    result = DefineRefChecker(broken_define).check()

    mismatch = [f for f in result.errors if f.check == "type_mismatch"][0]
    assert mismatch.attribute == "ItemOID"
    assert mismatch.expected_element == "ItemDef"
    assert mismatch.actual_element == "CodeList"


def test_check_reports_duplicate_itemgroupdef_oid(duplicate_itemgroup_define: Path):
    result = DefineRefChecker(duplicate_itemgroup_define).check()

    duplicates = {f.oid: f for f in result.errors if f.check == "duplicate_oid"}
    assert "IG.TS" in duplicates
    # the message names both definitions and their position among their siblings
    assert "ItemGroupDef (#1)" in duplicates["IG.TS"].message
    assert "ItemGroupDef (#2)" in duplicates["IG.TS"].message
    # the copied ItemGroupDef brings its def:leaf with it, and a leaf ID must be unique too
    assert "LF.TS" in duplicates


def test_check_reports_dangling_archive_location_id(broken_define: Path):
    result = DefineRefChecker(broken_define).check()

    dangling = [f for f in result.errors if f.check == "undefined_document_reference"][0]
    assert dangling.attribute == "ArchiveLocationID"
    assert dangling.expected_element == "leaf"
    assert dangling.locations[0].element == "ItemGroupDef"
    assert "ItemGroupDef[IG.TS]" in dangling.locations[0].path


def test_check_groups_occurrences_into_one_finding(many_references_define: Path):
    result = DefineRefChecker(many_references_define).check()

    dangling = [f for f in result.errors if f.oid == "IT.STUDYID"]
    assert len(dangling) == 1
    assert len(dangling[0].locations) > 1


def test_findings_include_location_context(broken_define: Path):
    result = DefineRefChecker(broken_define).check()

    dangling = [f for f in result.errors if f.oid == "IT.DOES.NOT.EXIST"][0]
    assert dangling.locations[0].element == "ItemRef"
    assert "ItemGroupDef[IG.TS]" in dangling.locations[0].path


def test_check_to_string_formatting(broken_define: Path):
    listing = DefineRefChecker(broken_define).check_to_string()

    assert listing.startswith("Define-XML OID reference/definition check")
    assert "  File:  " in listing
    assert "\nERRORS (" in listing
    assert "\nWARNINGS (" in listing
    assert "\nSUMMARY" in listing
    assert "Checked attributes:" in listing
    assert "Skipped attributes:" in listing


def test_check_to_string_clean_define():
    listing = DefineRefChecker(define_file()).check_to_string()

    assert "No OID reference/definition problems found." not in listing
    assert "ERRORS (" not in listing
    assert "0 errors, 1 warning" in listing


def test_check_to_string_clean_define_errors_only():
    listing = DefineRefChecker(define_file()).check_to_string(errors_only=True)

    assert "No OID reference/definition errors found." in listing
    assert "warnings suppressed" in listing


def test_errors_only_suppresses_warnings(broken_define: Path):
    checker = DefineRefChecker(broken_define)

    listing = checker.check_to_string(errors_only=True)

    assert "WARNINGS (" not in listing
    assert "orphan_definition" not in listing
    assert "ERRORS (" in listing
    # the underlying result still carries the warnings
    assert checker.check().warnings


def test_max_locations_truncates_with_count(many_references_define: Path):
    checker = DefineRefChecker(many_references_define)
    total = len([f for f in checker.check().errors if f.oid == "IT.STUDYID"][0].locations)

    listing = checker.check_to_string(max_locations=2)

    assert f"({total} occurrences)" in listing
    assert f"... and {total - 2} more" in listing
    # 0 shows every location, so nothing is truncated
    assert "... and" not in checker.check_to_string(max_locations=0)


def test_check_to_json_is_valid_and_complete(many_references_define: Path):
    checker = DefineRefChecker(many_references_define)

    report = json.loads(checker.check_to_json())

    assert report["model_package"] == "define_2_1"
    assert report["permissive"] is False
    assert report["counts"]["errors"] == len(checker.check().errors)
    assert report["coverage"]["skipped_attributes"] == checker.check().skipped_attributes
    dangling = [f for f in report["findings"] if f["oid"] == "IT.STUDYID"][0]
    assert dangling["check"] == "undefined_reference"
    assert dangling["expected_element"] == "ItemDef"
    assert dangling["actual_element"] is None
    # JSON is never truncated, even where the text listing would stop at max_locations
    finding = [f for f in checker.check().errors if f.oid == "IT.STUDYID"][0]
    assert len(dangling["locations"]) == len(finding.locations) > 5


def test_check_to_json_errors_only(broken_define: Path):
    report = json.loads(DefineRefChecker(broken_define).check_to_json(errors_only=True))

    assert report["errors_only"] is True
    assert report["counts"]["warnings"] == 0
    assert all(f["severity"] == "error" for f in report["findings"])


def test_check_to_file_basic(tmp_path: Path, broken_define: Path):
    checker = DefineRefChecker(broken_define)
    out_file = tmp_path / "refdef_report.txt"

    checker.check_to_file(out_file)

    assert out_file.exists()
    assert out_file.read_text(encoding="utf-8").rstrip("\n") == checker.check_to_string()


def test_check_to_file_json(tmp_path: Path, broken_define: Path):
    checker = DefineRefChecker(broken_define)
    out_file = tmp_path / "refdef_report.json"

    checker.check_to_file(out_file, as_json=True)

    assert json.loads(out_file.read_text(encoding="utf-8"))["define_file"] == str(broken_define)


def test_check_to_console(capsys):
    DefineRefChecker(define_file()).check_to_console()

    captured = capsys.readouterr()
    assert "Define-XML OID reference/definition check" in captured.out
    assert "SUMMARY" in captured.out


def test_check_to_file_errors_graceful(tmp_path: Path):
    checker = DefineRefChecker(define_file())

    # writing to a directory path triggers the IsADirectoryError branch
    with pytest.raises(DefineRefCheckError):
        checker.check_to_file(tmp_path)


def test_init_raises_when_define_missing(tmp_path: Path):
    with pytest.raises(DefineRefCheckError):
        DefineRefChecker(tmp_path / "nope.xml")


def test_malformed_xml_raises_with_validate_guidance(tmp_path: Path):
    bad_xml = tmp_path / "bad.xml"
    bad_xml.write_text("<ODM><broken></ODM>", encoding="utf-8")

    with pytest.raises(DefineRefCheckError) as excinfo:
        DefineRefChecker(bad_xml).check()

    message = str(excinfo.value)
    assert "python -m defineutils.validate" in message
    # the underlying parser message survives, whatever exception type odmlib wraps it in
    assert "mismatched tag" in message
    # permissive mode cannot rescue malformed XML, so it is not suggested
    assert "--permissive" not in message


def test_nonconformant_raises_without_permissive(nonconformant_define: Path):
    with pytest.raises(DefineRefCheckError) as excinfo:
        DefineRefChecker(nonconformant_define).check()

    message = str(excinfo.value)
    assert "python -m defineutils.validate" in message
    assert "--permissive" in message


def test_nonconformant_checks_with_permissive(nonconformant_define: Path):
    checker = DefineRefChecker(nonconformant_define, permissive=True)

    result = checker.check()

    assert result.permissive is True
    assert result.definition_count == 353
    assert "permissive mode" in checker.check_to_string()
    assert json.loads(checker.check_to_json())["permissive"] is True


def _run_cli(*cli_args) -> subprocess.CompletedProcess:
    """Run `python -m defineutils.definerefs` from the repo root so the package resolves
    whether or not it is installed."""
    return subprocess.run([sys.executable, "-m", "defineutils.definerefs", *cli_args],
                          capture_output=True, cwd=str(data_path().parent))


def test_cli_exit_code_clean():
    completed = _run_cli("-d", str(define_file()))

    assert completed.returncode == 0
    assert b"Define-XML OID reference/definition check" in completed.stdout
    assert b"Traceback" not in completed.stderr


def test_cli_exit_code_errors(broken_define: Path):
    completed = _run_cli("-d", str(broken_define))

    assert completed.returncode == 1
    assert b"ERRORS (" in completed.stdout
    assert b"Traceback" not in completed.stderr


def test_cli_exit_code_load_failure(tmp_path: Path):
    bad_xml = tmp_path / "bad.xml"
    bad_xml.write_text("<ODM><broken></ODM>", encoding="utf-8")

    completed = _run_cli("-d", str(bad_xml))

    assert completed.returncode == 2
    assert b"python -m defineutils.validate" in completed.stderr
    assert b"Traceback" not in completed.stderr


def test_cli_json_to_file(tmp_path: Path, broken_define: Path):
    out_file = tmp_path / "report.json"

    completed = _run_cli("-d", str(broken_define), "-o", str(out_file), "--json")

    assert completed.returncode == 1
    assert json.loads(out_file.read_text(encoding="utf-8"))["counts"]["errors"] > 0
