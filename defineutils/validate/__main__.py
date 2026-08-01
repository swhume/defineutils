import sys
from pathlib import Path
import argparse
from defineutils.validate import DefineSchemaValidator, DefineSchemaValidationError, DefineSchemaLoadError

def main():
    """
    schema validates the define.xml and returns the exit code: 0 when the file is valid, 1 when it
    is invalid, and 2 when the validation could not be run at all -- the schema would not load, or
    the define.xml could not be read or parsed
    :return: int exit code
    """
    args = set_cmd_line_args()
    try:
        schema = Path(args.schema) if args.schema else None
        validator = DefineSchemaValidator(Path(args.define), schema)
        result = validator.validate_define_file()
    except DefineSchemaLoadError as e:
        # DefineSchemaLoadError subclasses DefineSchemaValidationError, so it must be caught first
        print(e, file=sys.stderr)
        return 2
    except DefineSchemaValidationError as e:
        print(e, file=sys.stderr)
        return 1
    else:
        print(result)
        return 0


def set_cmd_line_args():
    """
    get the define.xml to validate, and optionally the schema to validate it against, from the
    command-line
    :return: return the argparse object with the command-line parameters
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--define", help="path and file name of the define.xml file", required=False,
                        dest="define", default=str(Path(__file__).parent.joinpath("define.xml")))
    parser.add_argument("-s", "--schema", help="path and file name of the schema (.xsd) to validate "
                        "against; omit to use the bundled Define-XML v2.1 schema", required=False,
                        dest="schema", default=None)
    args = parser.parse_args()
    return args

if __name__ == "__main__":
    sys.exit(main())
