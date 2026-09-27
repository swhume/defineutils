import os
import sys
from pathlib import Path
import argparse
from defineutils.definerefs import DefineRefChecker, DefineRefCheckError

def main():
    """
    runs the OID reference/definition checks and returns the exit code: 0 when there are no
    errors (a clean file, or one with orphan warnings only), 1 when there are errors, and 2
    when the check could not be run -- the define.xml would not load, or the report could not
    be written. This is the first defineutils module to set an exit code, so it can gate CI.
    :return: int exit code
    """
    args = set_cmd_line_args()
    try:
        checker = DefineRefChecker(Path(args.define), permissive=args.permissive)
        if args.out:
            checker.check_to_file(Path(args.out), errors_only=args.errors_only,
                                  max_locations=args.max_locations, as_json=args.json)
        elif args.json:
            print(checker.check_to_json(errors_only=args.errors_only))
        else:
            checker.check_to_console(errors_only=args.errors_only,
                                     max_locations=args.max_locations)
        return 1 if checker.check().has_errors else 0
    except DefineRefCheckError as e:
        # the load failure message carries the validate utility guidance; stderr keeps it out
        # of a redirected report
        print(e, file=sys.stderr)
        return 2

def _quiet_exit(code):
    """Terminate immediately via os._exit, bypassing interpreter shutdown, so a late write to
    a closed pipe -- or a Ctrl-C during finalization -- cannot print an 'Exception ignored ...'
    message or traceback at exit. 130 == 128 + SIGINT, the conventional Ctrl-C status; a broken
    pipe exits 0 since quitting the pager is not an error."""
    os._exit(code)

def set_cmd_line_args():
    """
    get the command-line arguments needed to check the define.xml input file
    :return: return the argparse object with the command-line parameters
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--define", help="path and file name of the define.xml file to check",
                        required=True, dest="define")
    parser.add_argument("-o", "--out", help="path and file name of the report to create; "
                        "omit to print to the console", required=False, dest="out", default=None)
    parser.add_argument("--json", help="emit JSON instead of the text listing",
                        required=False, dest="json", action="store_true")
    parser.add_argument("--errors-only", help="suppress the orphan definition warnings",
                        required=False, dest="errors_only", action="store_true")
    parser.add_argument("-L", "--max-locations", help="max example locations shown per finding "
                        "(0 shows all)", required=False, dest="max_locations", type=int, default=5)
    parser.add_argument("--permissive", help="best-effort check of a non-conformant define.xml",
                        required=False, dest="permissive", action="store_true")
    args = parser.parse_args()
    return args

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        _quiet_exit(130)
    except BrokenPipeError:
        _quiet_exit(0)
