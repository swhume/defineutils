import subprocess
import sys
from pathlib import Path
import pytest

from defineutils.validate import (DefineSchemaValidator, DefineSchemaValidationError,
                                  DefineSchemaLoadError)


def data_path() -> Path:
    return Path(__file__).parent


def define_file() -> Path:
    return data_path() / "define.xml"


def bundled_schema() -> Path:
    """the Define-XML v2.1 schema shipped in the package -- the default when no schema is given"""
    return (data_path().parent / "defineutils" / "validate" / "schema"
            / "cdisc-define-2.1" / "define2-1-0.xsd")


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


def test_cli_exit_code_valid():
    completed = _run_cli("-d", str(define_file()))

    assert completed.returncode == 0
    assert b"is valid" in completed.stdout
    assert b"Traceback" not in completed.stderr


def test_cli_schema_argument_accepted():
    completed = _run_cli("-d", str(define_file()), "-s", str(bundled_schema()))

    assert completed.returncode == 0
    assert b"is valid" in completed.stdout
    assert b"Traceback" not in completed.stderr


def test_cli_exit_code_invalid_define(tmp_path: Path):
    invalid_xml = tmp_path / "invalid_define.xml"
    invalid_xml.write_text("<NotDefine><Something>bad</Something></NotDefine>", encoding="utf-8")

    completed = _run_cli("-d", str(invalid_xml))

    assert completed.returncode == 1
    assert b"Schema validation errors" in completed.stderr
    assert b"Traceback" not in completed.stderr


def test_cli_exit_code_bad_schema(tmp_path: Path):
    missing_schema = tmp_path / "no_such_schema.xsd"

    completed = _run_cli("-d", str(define_file()), "-s", str(missing_schema))

    assert completed.returncode == 2
    assert b"Could not load the schema" in completed.stderr
    assert b"Traceback" not in completed.stderr
