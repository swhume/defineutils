import os
import sys
import traceback
from pathlib import Path
import argparse
from defineutils import __version__
from defineutils.conformance import DefineConformanceChecker, DefineConformanceError
from defineutils.conformance.report import render_rule_list

def main():
    """
    runs the conformance rule checks and returns the exit code: 0 when no rule failed, 1 when
    at least one rule failed, 2 when the check could not be run -- the define.xml is missing,
    not well-formed or a Define-XML 2.0 document, a rule id is unknown, or the report could not
    be written -- and 3 when an unexpected error occurred, with its traceback on stderr so it
    can be reported. 1 means what it means in definevalidate and definerefs, a failed check,
    so a crash cannot be mistaken for one
    :return: int exit code
    """
    args = set_cmd_line_args()
    try:
        if args.list_rules:
            print(render_rule_list(DefineConformanceChecker.all_rules()))
            return 0
        checker = DefineConformanceChecker(Path(args.define), rules=_ids(args.rules),
                                           skip_rules=_ids(args.skip_rules))
        if args.out:
            checker.check_to_file(Path(args.out), max_locations=args.max_locations, as_json=args.json)
        elif args.json:
            print(checker.check_to_json())
        else:
            checker.check_to_console(max_locations=args.max_locations)
        return 1 if checker.check().has_errors else 0
    except DefineConformanceError as e:
        # stderr keeps the message out of a redirected report
        print(e, file=sys.stderr)
        return 2
    except BrokenPipeError:
        # quitting a pager is not a crash; the entry point exits 0 for it
        raise
    except Exception:
        traceback.print_exc()
        return 3

def _ids(value):
    """the comma-separated rule ids as a list, or None when the option was not given"""
    if value is None:
        return None
    return [rule_id.strip() for rule_id in value.split(",") if rule_id.strip()]

def _quiet_exit(code):
    """Terminate immediately via os._exit, bypassing interpreter shutdown, so a late write to
    a closed pipe -- or a Ctrl-C during finalization -- cannot print an 'Exception ignored ...'
    message or traceback at exit. The report is long enough to be paged, so both are reachable.
    130 == 128 + SIGINT, the conventional Ctrl-C status; a broken pipe exits 0 since quitting the
    pager is not an error."""
    os._exit(code)

def set_cmd_line_args():
    """
    get the command-line arguments needed to check the define.xml input file
    :return: return the argparse object with the command-line parameters
    """
    parser = argparse.ArgumentParser(prog="defineconform")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("-d", "--define", help="path and file name of the define.xml file to check",
                        required=False, dest="define", default=None)
    parser.add_argument("-o", "--out", help="path and file name of the report to create; "
                        "omit to print to the console", required=False, dest="out", default=None)
    parser.add_argument("--json", help="emit JSON instead of the text listing",
                        required=False, dest="json", action="store_true")
    parser.add_argument("-L", "--max-locations", help="max example locations shown per finding "
                        "(0 shows all)", required=False, dest="max_locations", type=int, default=5)
    parser.add_argument("--rules", help="comma-separated rule ids to run; every other rule is "
                        "reported as skipped", required=False, dest="rules", default=None)
    parser.add_argument("--skip-rules", help="comma-separated rule ids to leave out",
                        required=False, dest="skip_rules", default=None)
    parser.add_argument("--list-rules", help="list the rules, one per line, and exit",
                        required=False, dest="list_rules", action="store_true")
    args = parser.parse_args()
    if not args.define and not args.list_rules:
        # a usage error exits 2, as argparse does for a missing required option
        parser.error("the following arguments are required: -d/--define (or --list-rules)")
    return args

def run():
    """the entry point for both the defineconform command and python -m: exits with main()'s
    code. The command calls run() directly, never this module's __main__ block, so Ctrl-C and a
    closed pager are handled here"""
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        _quiet_exit(130)
    except BrokenPipeError:
        _quiet_exit(0)

if __name__ == "__main__":
    run()
