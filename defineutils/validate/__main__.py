import os
import sys
from pathlib import Path
import argparse
from defineutils.validate import DefineSchemaValidator, DefineSchemaValidationError, DefineSchemaLoadError

def main():
    """
    schema validates the define.xml, reporting every error, and returns the exit code: 0 when the
    file is valid, 1 when it is invalid, and 2 when the validation could not be run at all -- the
    schema would not load, the define.xml could not be read or parsed, or the report could not be
    written
    :return: int exit code
    """
    args = set_cmd_line_args()
    try:
        schema = Path(args.schema) if args.schema else None
        validator = DefineSchemaValidator(Path(args.define), schema)
        if args.out:
            validator.validate_to_file(Path(args.out), max_locations=args.max_locations,
                                       as_json=args.json)
        elif args.json:
            print(validator.validate_to_json())
        else:
            validator.validate_to_console(max_locations=args.max_locations)
        return 1 if validator.validate().has_errors else 0
    except DefineSchemaLoadError as e:
        # DefineSchemaLoadError subclasses DefineSchemaValidationError, so it must be caught first.
        # stderr keeps the message out of a redirected report
        print(e, file=sys.stderr)
        return 2
    except DefineSchemaValidationError as e:
        print(e, file=sys.stderr)
        return 1


def _quiet_exit(code):
    """Terminate immediately via os._exit, bypassing interpreter shutdown, so a late write to
    a closed pipe -- or a Ctrl-C during finalization -- cannot print an 'Exception ignored ...'
    message or traceback at exit. The report is long enough to be paged, so both are reachable.
    130 == 128 + SIGINT, the conventional Ctrl-C status; a broken pipe exits 0 since quitting the
    pager is not an error."""
    os._exit(code)

def set_cmd_line_args():
    """
    get the define.xml to validate, the schema to validate it against, and the reporting options
    from the command-line
    :return: return the argparse object with the command-line parameters
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--define", help="path and file name of the define.xml file", required=True,
                        dest="define")
    parser.add_argument("-s", "--schema", help="path and file name of the schema (.xsd) to validate "
                        "against; omit to use the bundled Define-XML v2.1 schema", required=False,
                        dest="schema", default=None)
    parser.add_argument("-o", "--out", help="path and file name of the report to create; "
                        "omit to print to the console", required=False, dest="out", default=None)
    parser.add_argument("--json", help="emit JSON instead of the text listing",
                        required=False, dest="json", action="store_true")
    parser.add_argument("-L", "--max-locations", help="max example locations shown per finding "
                        "(0 shows all)", required=False, dest="max_locations", type=int, default=5)
    args = parser.parse_args()
    return args

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        _quiet_exit(130)
    except BrokenPipeError:
        _quiet_exit(0)
