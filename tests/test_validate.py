import json
import subprocess
import sys
from pathlib import Path
import pytest
import xmlschema
from lxml import etree

from defineutils.validate import (DefineSchemaValidator, DefineSchemaValidationError,
                                  DefineSchemaLoadError)

ODM_NS = "http://www.cdisc.org/ns/odm/v1.3"
NS = {"odm": ODM_NS}

BAD_DATATYPE = "NOT_A_DATATYPE"


def data_path() -> Path:
    return Path(__file__).parent


def define_file() -> Path:
    return data_path() / "define.xml"


def bundled_schema() -> Path:
    """the Define-XML v2.1 schema shipped in the package -- the default when no schema is given"""
    return (data_path().parent / "defineutils" / "validate" / "schema"
            / "cdisc-define-2.1" / "define2-1-0.xsd")


def odm_schema() -> Path:
    """the ODM 1.3.2 schema, also shipped; a define.xml fails it in bulk, which makes it a
    fixture-free source of hundreds of real errors"""
    return (data_path().parent / "defineutils" / "validate" / "schema"
            / "cdisc-odm-1.3.2" / "ODM1-3-2.xsd")


def _item_def(mdv, oid):
    return [d for d in mdv.findall("odm:ItemDef", NS) if d.get("OID") == oid][0]


def _write_simple_schema(tmp_path: Path) -> tuple:
    """a standalone schema and a document that matches it, so the schema override can be tested
    without depending on the semantics of any CDISC schema"""
    xsd_file = tmp_path / "simple.xsd"
    xsd_file.write_text("""<?xml version="1.0" encoding="UTF-8"?>
<xs:schema xmlns:xs="http://www.w3.org/2001/XMLSchema">
    <xs:element name="Greeting" type="xs:string"/>
</xs:schema>""", encoding="utf-8")
    xml_file = tmp_path / "simple.xml"
    xml_file.write_text("<Greeting>hello</Greeting>", encoding="utf-8")
    return xsd_file, xml_file


@pytest.fixture
def broken_define(tmp_path: Path) -> Path:
    """A copy of tests/define.xml broken in four ways that stay well-formed, so the validator runs
    end to end: the same invalid DataType on two ItemDefs (which must group into one finding), a
    removed required attribute, and an unexpected child element."""
    tree = etree.parse(str(define_file()))
    mdv = tree.getroot().find(".//odm:MetaDataVersion", NS)
    # the same invalid enumeration value twice -- identical reason, so one finding, two locations
    _item_def(mdv, "IT.DM.AGE").set("DataType", BAD_DATATYPE)
    _item_def(mdv, "IT.DM.SEX").set("DataType", BAD_DATATYPE)
    # a missing required attribute
    del _item_def(mdv, "IT.DM.ARM").attrib["DataType"]
    # an unexpected child element
    item_group = mdv.findall("odm:ItemGroupDef", NS)[0]
    item_group.append(etree.SubElement(item_group, f"{{{ODM_NS}}}Bogus"))
    out_file = tmp_path / "broken_define.xml"
    tree.write(str(out_file), xml_declaration=True, encoding="UTF-8")
    return out_file


def _raw_error_count(define: Path, schema: Path) -> int:
    """the ground truth: what xmlschema itself finds, independent of the code under test"""
    xsd = xmlschema.XMLSchema(str(schema))
    return len(list(xsd.iter_errors(etree.parse(str(define), etree.XMLParser(remove_comments=True)))))


def _checks(result) -> set:
    return {f.check for f in result.findings}


def _run_cli(*cli_args) -> subprocess.CompletedProcess:
    """Run `python -m defineutils.validate` from the repo root so the package resolves
    whether or not it is installed."""
    return subprocess.run([sys.executable, "-m", "defineutils.validate", *cli_args],
                          capture_output=True, cwd=str(data_path().parent))


def test_validate_define_xml_success():
    # Use the provided valid define.xml in tests directory
    define_path = Path(__file__).parent / "define.xml"
    validator = DefineSchemaValidator(define_path)
    result = validator.validate_define_file()
    assert isinstance(result, str)
    assert str(define_path) in result
    assert "is valid" in result


def test_validate_define_xml_missing_file():
    missing_define = Path(__file__).parent / "does_not_exist.xml"
    validator = DefineSchemaValidator(missing_define)
    with pytest.raises(DefineSchemaValidationError) as excinfo:
        validator.validate_define_file()
    msg = str(excinfo.value)
    assert "Define-XML file not found" in msg or "not found" in msg
    # the validation could not be run, so it is the load subclass
    assert isinstance(excinfo.value, DefineSchemaLoadError)


def test_validate_define_xml_invalid_content(tmp_path: Path):
    # Create an invalid define xml that should not pass schema (malformed or wrong root)
    invalid_xml = tmp_path / "invalid_define.xml"
    invalid_xml.write_text("""
    <NotDefine xmlns="http://www.w3.org/2001/XMLSchema-instance">
        <Something>bad</Something>
    </NotDefine>
    """.strip())

    validator = DefineSchemaValidator(invalid_xml)
    with pytest.raises(DefineSchemaValidationError) as excinfo:
        validator.validate_define_file()
    # Should report schema validation errors
    assert "Schema validation errors" in str(excinfo.value)


def test_default_schema_is_bundled_define_21():
    validator = DefineSchemaValidator(define_file())

    assert validator.xsd_file == bundled_schema()


def test_explicit_bundled_schema_validates():
    validator = DefineSchemaValidator(define_file(), bundled_schema())

    result = validator.validate_define_file()

    assert validator.xsd_file == bundled_schema()
    assert "is valid" in result


def test_custom_schema_validates_matching_document(tmp_path: Path):
    # the override really swaps the schema: a document that no Define-XML schema would accept
    # validates against the schema it was written for
    xsd_file, xml_file = _write_simple_schema(tmp_path)

    result = DefineSchemaValidator(xml_file, xsd_file).validate_define_file()

    assert "is valid" in result


def test_custom_document_fails_against_default_schema(tmp_path: Path):
    # so the previous test cannot pass by accident with the default schema still in force
    _, xml_file = _write_simple_schema(tmp_path)

    with pytest.raises(DefineSchemaValidationError) as excinfo:
        DefineSchemaValidator(xml_file).validate_define_file()

    assert "Schema validation errors" in str(excinfo.value)


def test_missing_schema_raises_load_error(tmp_path: Path):
    missing_schema = tmp_path / "no_such_schema.xsd"

    with pytest.raises(DefineSchemaLoadError) as excinfo:
        DefineSchemaValidator(define_file(), missing_schema)

    assert "Could not load the schema" in str(excinfo.value)
    assert str(missing_schema) in str(excinfo.value)
    # the subclass contract: catching the parent still catches this
    with pytest.raises(DefineSchemaValidationError):
        DefineSchemaValidator(define_file(), missing_schema)


def test_non_schema_file_as_schema_raises_load_error():
    # well-formed XML, but not a schema
    with pytest.raises(DefineSchemaLoadError) as excinfo:
        DefineSchemaValidator(define_file(), define_file())

    assert "Could not load the schema" in str(excinfo.value)


def test_malformed_define_raises_load_error(tmp_path: Path):
    bad_xml = tmp_path / "bad.xml"
    bad_xml.write_text("<ODM><broken></ODM>", encoding="utf-8")
    validator = DefineSchemaValidator(bad_xml)

    with pytest.raises(DefineSchemaLoadError) as excinfo:
        validator.validate_define_file()

    assert "not well-formed" in str(excinfo.value)


def test_validate_collects_every_error(broken_define: Path):
    # the reason for the collecting API: validate_define_file() raises on the first error, so it
    # can only ever report one, whatever is actually wrong with the file
    result = DefineSchemaValidator(broken_define).validate()

    assert result.error_count == _raw_error_count(broken_define, bundled_schema())
    assert result.error_count > 1
    assert len(result.findings) > 1
    assert result.has_errors is True
    assert result.is_valid is False


def test_validate_groups_identical_errors(broken_define: Path):
    # the same invalid DataType on two ItemDefs is one problem in two places, not two problems
    result = DefineSchemaValidator(broken_define).validate()

    grouped = [f for f in result.findings if BAD_DATATYPE in f.reason]
    assert len(grouped) == 1
    assert len(grouped[0].locations) == 2
    assert grouped[0].element == "ItemDef"
    # grouping never loses an occurrence
    assert sum(len(f.locations) for f in result.findings) == result.error_count


def test_findings_carry_line_numbers(broken_define: Path):
    result = DefineSchemaValidator(broken_define).validate()

    assert all(location.line for f in result.findings for location in f.locations)
    # the reported line is the real source line of the element that was broken
    tree = etree.parse(str(broken_define), etree.XMLParser(remove_comments=True))
    expected = _item_def(tree.getroot().find(".//odm:MetaDataVersion", NS), "IT.DM.AGE").sourceline
    grouped = [f for f in result.findings if BAD_DATATYPE in f.reason][0]
    assert expected in [location.line for location in grouped.locations]


def test_findings_carry_oid_paths(broken_define: Path):
    result = DefineSchemaValidator(broken_define).validate()

    grouped = [f for f in result.findings if BAD_DATATYPE in f.reason][0]
    path = grouped.locations[0].path
    assert "ItemDef[IT.DM.AGE]" in path
    assert path.startswith("MetaDataVersion[")
    # the constant ODM/Study prefix is trimmed, as in the definerefs listing
    assert not path.startswith("ODM")


def test_check_ids_are_classified(broken_define: Path):
    result = DefineSchemaValidator(broken_define).validate()

    assert {"invalid_value", "attribute_error", "unexpected_child"} <= _checks(result)
    # the fallback is not reached for any of these
    assert "schema_validation" not in _checks(result)


def test_validate_clean_define_has_no_findings():
    result = DefineSchemaValidator(define_file()).validate()

    assert result.findings == []
    assert result.error_count == 0
    assert result.is_valid is True
    assert result.has_errors is False


def test_validate_against_other_bundled_schema():
    # end to end on shipped files only: a Define-XML v2.1 file against the ODM 1.3.2 schema is
    # wrong in hundreds of places, every one of which is now reported
    result = DefineSchemaValidator(define_file(), odm_schema()).validate()

    assert result.error_count > 400
    assert len(result.findings) > 100
    assert result.error_count == _raw_error_count(define_file(), odm_schema())


def test_result_is_cached():
    validator = DefineSchemaValidator(define_file())

    assert validator.validate() is validator.validate()


def test_validate_to_string_formatting(broken_define: Path):
    listing = DefineSchemaValidator(broken_define).validate_to_string()

    assert listing.startswith("Define-XML schema validation")
    assert "  File:   " in listing
    assert "  Schema: " in listing
    assert "  Scope:  " in listing
    assert "\nERRORS (" in listing
    assert "\nSUMMARY" in listing
    assert "line " in listing


def test_validate_to_string_clean_define():
    listing = DefineSchemaValidator(define_file()).validate_to_string()

    assert "No schema validation errors found." in listing
    assert "ERRORS (" not in listing
    assert "0 errors in" in listing


def test_max_locations_truncates_with_count():
    validator = DefineSchemaValidator(define_file(), odm_schema())
    total = len(validator.validate().findings[0].locations)

    listing = validator.validate_to_string(max_locations=2)

    assert f"({total} occurrences)" in listing
    assert f"... and {total - 2} more" in listing
    # 0 shows every location, so nothing is truncated
    assert "... and" not in validator.validate_to_string(max_locations=0)


def test_validate_to_json_is_valid_and_complete(broken_define: Path):
    validator = DefineSchemaValidator(broken_define)

    report = json.loads(validator.validate_to_json())

    result = validator.validate()
    assert report["define_file"] == str(broken_define)
    assert report["schema_file"] == str(bundled_schema())
    assert report["valid"] is False
    assert report["counts"]["errors"] == result.error_count
    assert report["counts"]["findings"] == len(result.findings)
    finding = [f for f in report["findings"] if BAD_DATATYPE in f["reason"]][0]
    assert finding["severity"] == "error"
    assert finding["element"] == "ItemDef"
    assert finding["check"] == "invalid_value"
    assert set(finding["locations"][0]) == {"path", "line"}


def test_validate_to_json_never_truncates_locations():
    validator = DefineSchemaValidator(define_file(), odm_schema())
    biggest = validator.validate().findings[0]

    report = json.loads(validator.validate_to_json())

    finding = [f for f in report["findings"] if f["reason"] == biggest.reason][0]
    assert len(finding["locations"]) == len(biggest.locations) > 5


def test_validate_to_json_clean_define():
    report = json.loads(DefineSchemaValidator(define_file()).validate_to_json())

    assert report["valid"] is True
    assert report["counts"] == {"errors": 0, "findings": 0}
    assert report["findings"] == []


def test_validate_to_file_basic(tmp_path: Path, broken_define: Path):
    validator = DefineSchemaValidator(broken_define)
    out_file = tmp_path / "validation_report.txt"

    validator.validate_to_file(out_file)

    assert out_file.exists()
    assert out_file.read_text(encoding="utf-8").rstrip("\n") == validator.validate_to_string()


def test_validate_to_file_json(tmp_path: Path, broken_define: Path):
    validator = DefineSchemaValidator(broken_define)
    out_file = tmp_path / "validation_report.json"

    validator.validate_to_file(out_file, as_json=True)

    assert json.loads(out_file.read_text(encoding="utf-8"))["define_file"] == str(broken_define)


def test_validate_to_file_errors_graceful(tmp_path: Path):
    validator = DefineSchemaValidator(define_file())

    # writing to a directory path triggers the IsADirectoryError branch
    with pytest.raises(DefineSchemaValidationError):
        validator.validate_to_file(tmp_path)


def test_validate_to_console(capsys):
    DefineSchemaValidator(define_file()).validate_to_console()

    captured = capsys.readouterr()
    assert "Define-XML schema validation" in captured.out
    assert "SUMMARY" in captured.out


def test_cli_exit_code_valid():
    completed = _run_cli("-d", str(define_file()))

    assert completed.returncode == 0
    assert b"Define-XML schema validation" in completed.stdout
    assert b"No schema validation errors found." in completed.stdout
    assert b"Traceback" not in completed.stderr


def test_cli_schema_argument_accepted():
    completed = _run_cli("-d", str(define_file()), "-s", str(bundled_schema()))

    assert completed.returncode == 0
    assert b"No schema validation errors found." in completed.stdout
    assert b"Traceback" not in completed.stderr


def test_cli_exit_code_invalid_define(broken_define: Path):
    completed = _run_cli("-d", str(broken_define))

    assert completed.returncode == 1
    assert b"ERRORS (" in completed.stdout
    assert b"Traceback" not in completed.stderr


def test_cli_exit_code_bad_schema(tmp_path: Path):
    missing_schema = tmp_path / "no_such_schema.xsd"

    completed = _run_cli("-d", str(define_file()), "-s", str(missing_schema))

    assert completed.returncode == 2
    assert b"Could not load the schema" in completed.stderr
    assert b"Traceback" not in completed.stderr


def test_cli_report_to_file(tmp_path: Path, broken_define: Path):
    out_file = tmp_path / "report.txt"

    completed = _run_cli("-d", str(broken_define), "-o", str(out_file))

    assert completed.returncode == 1
    assert "ERRORS (" in out_file.read_text(encoding="utf-8")
    # the report went to the file, not the console
    assert completed.stdout == b""


def test_cli_json_to_file(tmp_path: Path, broken_define: Path):
    out_file = tmp_path / "report.json"

    completed = _run_cli("-d", str(broken_define), "-o", str(out_file), "--json")

    assert completed.returncode == 1
    assert json.loads(out_file.read_text(encoding="utf-8"))["counts"]["errors"] > 1


def test_cli_max_locations():
    completed = _run_cli("-d", str(define_file()), "-s", str(odm_schema()), "-L", "0")

    assert completed.returncode == 1
    assert b"... and" not in completed.stdout


def test_cli_broken_pipe_exits_cleanly():
    # a reader (e.g. `more`/`head`) that quits after one line closes the pipe early; the CLI
    # should exit 0 with no traceback. The JSON report against the ODM schema is ~100KB, larger
    # than the OS pipe buffer, so the writer is still writing when the read end closes.
    p = subprocess.Popen(
        [sys.executable, "-m", "defineutils.validate", "-d", str(define_file()),
         "-s", str(odm_schema()), "--json"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=str(data_path().parent))
    try:
        p.stdout.readline()          # read one line, like a pager's first screen
        p.stdout.close()             # reader goes away -> next write hits a broken pipe
        err = p.stderr.read()
        rc = p.wait(timeout=30)
    finally:
        if p.poll() is None:
            p.kill()
        p.stderr.close()

    assert rc == 0
    assert b"Traceback" not in err
    assert b"BrokenPipeError" not in err
