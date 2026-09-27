import xmlschema as XSD
from dataclasses import dataclass, field
from pathlib import Path
from typing import Union

from lxml import etree
from xmlschema.exceptions import XMLResourceOSError, XMLResourceParseError, XMLSchemaException
from xmlschema.validators.exceptions import (XMLSchemaChildrenValidationError,
                                             XMLSchemaDecodeError)

from . import report

DEFAULT_SCHEMA = Path(__file__).parent.joinpath("schema").joinpath("cdisc-define-2.1").joinpath("define2-1-0.xsd")

UNEXPECTED_CHILD = "unexpected_child"
INCOMPLETE_CONTENT = "incomplete_content"
INVALID_VALUE = "invalid_value"
ATTRIBUTE_ERROR = "attribute_error"
SCHEMA_VALIDATION = "schema_validation"

ERROR = "error"


class DefineSchemaValidationError(Exception):
    pass

class DefineSchemaLoadError(DefineSchemaValidationError):
    """raised when the validation could not be run at all -- the schema could not be loaded, the
    define.xml could not be read or parsed, or the report could not be written -- as opposed to the
    define.xml being invalid. A subclass of DefineSchemaValidationError so callers that catch the
    parent keep working unchanged; the CLI catches it first to return exit code 2 rather than 1."""
    pass


@dataclass(frozen=True)
class Location:
    path: str                   # OID-decorated, e.g. "MetaDataVersion[MDV.1]/ItemDef[IT.DM.AGE]"
    line: Union[int, None]      # source line of the offending element


@dataclass
class Finding:
    check: str                  # "unexpected_child" | "invalid_value" | "attribute_error" | ...
    severity: str               # always "error"; kept so both reports share a finding shape
    element: str                # element class name holding the error, e.g. "ItemDef"
    reason: str                 # the reason text as xmlschema phrased it
    message: str                # self-contained sentence, used in the JSON report
    detail: str                 # short form for the text listing, whose heading names the element
    locations: list = field(default_factory=list)


@dataclass
class ValidationResult:
    define_file: str
    schema_file: str
    xmlschema_version: str
    error_count: int            # raw errors, before identical ones are grouped
    findings: list

    @property
    def errors(self) -> list:
        return [f for f in self.findings if f.severity == ERROR]

    @property
    def has_errors(self) -> bool:
        return any(f.severity == ERROR for f in self.findings)

    @property
    def is_valid(self) -> bool:
        return not self.findings


class DefineSchemaValidator():
    def __init__(self, define_file: Path, xsd_file: Path = None):
        self.define_file = Path(define_file)
        self.xsd_file = Path(xsd_file) if xsd_file is not None else DEFAULT_SCHEMA
        self._result = None
        try:
            self.xsd = XSD.XMLSchema(self.xsd_file)
        except XMLSchemaException as e:
            # XMLSchemaException covers the missing/unreadable path, the not-well-formed file, and
            # the well-formed file that is not a schema
            raise DefineSchemaLoadError(f"Could not load the schema {self.xsd_file}:\n{e}")

    def validate_define_file(self) -> str:
        """
        returns a string stating that the file is valid or raises a DefineSchemaValidationError
        exception on the first error found. Use validate() to collect every error instead
        :return: string stating that the define.xml is valid
        """
        try:
            self.xsd.validate(self.define_file)
        except XSD.validators.exceptions.XMLSchemaValidationError as e:
            raise DefineSchemaValidationError(f"Schema validation errors in {self.define_file}:\n{e}")
        except XMLResourceParseError as e:
            raise DefineSchemaLoadError(f"Define-XML file is not well-formed XML: {self.define_file}.\n{e}")
        except XMLResourceOSError as e:
            raise DefineSchemaLoadError(f"Define-XML file not found: {self.define_file}.\n{e}")
        else:
            return f"{self.define_file} is valid"

    def validate(self) -> ValidationResult:
        """
        schema validates the define.xml and collects every error, grouping identical errors into
        one finding; the result is cached so the report methods and the CLI exit code do not
        re-parse the file
        :return: ValidationResult
        """
        if self._result is not None:
            return self._result
        errors = list(self.xsd.iter_errors(self._parse_define()))
        self._result = ValidationResult(
            define_file=str(self.define_file),
            schema_file=str(self.xsd_file),
            xmlschema_version=getattr(XSD, "__version__", "unknown"),
            error_count=len(errors),
            findings=self._group(errors),
        )
        return self._result

    def validate_to_string(self, max_locations: int = 5) -> str:
        """
        validates and returns the formatted text listing
        :param max_locations: max example locations shown per finding (0 shows all)
        :return: string
        """
        return report.render_text(self.validate(), max_locations)

    def validate_to_file(self, out_file: Path, max_locations: int = 5,
                         as_json: bool = False) -> None:
        """
        validates and writes the listing (text or JSON) to out_file
        :param out_file: Path to the file to save the report
        :param max_locations: max example locations shown per finding (0 shows all)
        :param as_json: when True, writes the JSON report instead of the text listing
        :return: None
        """
        if as_json:
            listing = self.validate_to_json()
        else:
            listing = self.validate_to_string(max_locations=max_locations)
        try:
            with open(out_file, "w", encoding="utf-8") as f:
                f.write(listing + "\n")
        except FileNotFoundError as e:
            raise DefineSchemaLoadError(f"File {out_file} not found.\n{e}")
        except PermissionError as e:
            raise DefineSchemaLoadError(f"Permission error attempting to write to {out_file}.\n{e}")
        except IsADirectoryError as e:
            raise DefineSchemaLoadError(f"Error attempting to write to a directory {out_file}.\n{e}")

    def validate_to_console(self, max_locations: int = 5) -> None:
        """
        validates and prints the formatted text listing to stdout
        :param max_locations: max example locations shown per finding (0 shows all)
        :return: None
        """
        print(self.validate_to_string(max_locations=max_locations))

    def validate_to_json(self, indent: int = 2) -> str:
        """
        validates and returns the results as a JSON string; every location is included even when
        the text listing truncates them
        :param indent: JSON indent
        :return: string
        """
        return report.render_json(self.validate(), indent)

    def _parse_define(self):
        """
        parses the define.xml with lxml so every error carries a source line number -- handing
        xmlschema the file path instead leaves sourceline unset. Comments are stripped because
        lxml keeps them as child nodes, which shifts the child positions xmlschema reports
        :return: lxml ElementTree
        """
        try:
            return etree.parse(str(self.define_file), etree.XMLParser(remove_comments=True))
        except etree.XMLSyntaxError as e:
            raise DefineSchemaLoadError(f"Define-XML file is not well-formed XML: {self.define_file}.\n{e}")
        except OSError as e:
            raise DefineSchemaLoadError(f"Define-XML file not found: {self.define_file}.\n{e}")

    def _group(self, errors: list) -> list:
        """
        groups errors that say the same thing about the same kind of element into one finding,
        keeping every occurrence as a location; the biggest problems are listed first
        :param errors: the XMLSchemaValidationError list from iter_errors
        :return: list of Finding
        """
        findings = {}
        for error in errors:
            check, element = self._classify(error), self._element_name(error)
            reason = str(error.reason)
            key = (check, element, reason)
            if key not in findings:
                detail, message = report.finding_text(element, reason)
                findings[key] = Finding(check=check, severity=ERROR, element=element, reason=reason,
                                        message=message, detail=detail)
            findings[key].locations.append(self._location(error))
        return sorted(findings.values(), key=lambda f: (-len(f.locations), f.check, f.element))

    @staticmethod
    def _classify(error) -> str:
        """
        names the kind of error from the structure of the exception -- its class, whether it
        carries an offending tag, and the kind of schema component that rejected it -- rather than
        by matching on the reason text, which xmlschema formats and is free to reword
        :param error: an XMLSchemaValidationError
        :return: string check id
        """
        if isinstance(error, XMLSchemaChildrenValidationError):
            return UNEXPECTED_CHILD if error.invalid_tag is not None else INCOMPLETE_CONTENT
        if isinstance(error, XMLSchemaDecodeError):
            return INVALID_VALUE
        validator = type(getattr(error, "validator", None)).__name__
        if validator == "XsdAttributeGroup":
            # covers both a missing required attribute and one that is not allowed; the reason
            # line says which, and telling them apart would mean matching on that text
            return ATTRIBUTE_ERROR
        if "Facet" in validator:
            return INVALID_VALUE
        return SCHEMA_VALIDATION

    @staticmethod
    def _element_name(error) -> str:
        element = getattr(error, "elem", None)
        return etree.QName(element).localname if element is not None else "(document)"

    @staticmethod
    def _location(error) -> Location:
        """
        builds an OID-decorated path by walking the offending element's ancestors, so a location
        reads MetaDataVersion[MDV.1]/ItemDef[IT.DM.AGE] rather than the positional path
        xmlschema reports
        :param error: an XMLSchemaValidationError
        :return: Location
        """
        segments, node = [], getattr(error, "elem", None)
        while node is not None:
            oid = node.get("OID")
            name = etree.QName(node).localname
            segments.append(f"{name}[{oid}]" if oid else name)
            node = node.getparent()
        return Location(path=report.display_path("/".join(reversed(segments))),
                        line=getattr(error, "sourceline", None))
