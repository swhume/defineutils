import xmlschema as XSD
from pathlib import Path

from xmlschema.exceptions import XMLResourceOSError


class DefineSchemaValidationError(Exception):
    pass

class DefineSchemaValidator():
    def __init__(self, define_file: Path, xsd_file: Path = None):
        self.define_file = Path(define_file)
        if xsd_file is None:
            xsd_file = Path(__file__).parent.joinpath("schema").joinpath("cdisc-define-2.1").joinpath("define2-1-0.xsd")
        self.xsd = XSD.XMLSchema(xsd_file)

    def validate_define_file(self) -> str:
        """
        returns a string stating that the file is valid or raises a DefineSchemaValidationError exception
        :return: string stating that the define.xml is valid
        """
        try:
            self.xsd.validate(self.define_file)
        except XSD.validators.exceptions.XMLSchemaValidationError as e:
            raise DefineSchemaValidationError(f"Schema validation errors in {self.define_file}:\n{e}")
        except XMLResourceOSError as e:
            raise DefineSchemaValidationError(f"Define-XML file not found: {self.define_file}.\n{e}")
        else:
            return f"{self.define_file} is valid"
