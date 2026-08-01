import xmlschema as XSD
from pathlib import Path

from xmlschema.exceptions import XMLResourceOSError, XMLResourceParseError, XMLSchemaException

DEFAULT_SCHEMA = Path(__file__).parent.joinpath("schema").joinpath("cdisc-define-2.1").joinpath("define2-1-0.xsd")


class DefineSchemaValidationError(Exception):
    pass

class DefineSchemaLoadError(DefineSchemaValidationError):
    """raised when the validation could not be run at all -- the schema could not be loaded, or the
    define.xml could not be read or parsed -- as opposed to the define.xml being invalid. A subclass
    of DefineSchemaValidationError so callers that catch the parent keep working unchanged."""
    pass

class DefineSchemaValidator():
    def __init__(self, define_file: Path, xsd_file: Path = None):
        self.define_file = Path(define_file)
        self.xsd_file = Path(xsd_file) if xsd_file is not None else DEFAULT_SCHEMA
        try:
            self.xsd = XSD.XMLSchema(self.xsd_file)
        except XMLSchemaException as e:
            # XMLSchemaException covers the missing/unreadable path, the not-well-formed file, and
            # the well-formed file that is not a schema
            raise DefineSchemaLoadError(f"Could not load the schema {self.xsd_file}:\n{e}")

    def validate_define_file(self) -> str:
        """
        returns a string stating that the file is valid or raises a DefineSchemaValidationError exception
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
