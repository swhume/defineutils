from pathlib import Path
import pytest

from validate.validate import DefineSchemaValidator, DefineSchemaValidationError


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
