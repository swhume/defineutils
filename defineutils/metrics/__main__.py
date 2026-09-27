import os
import sys
from pathlib import Path
import argparse
from defineutils.metrics import DefineMetrics, DefineMetricsError

def main():
    """
    collects the define.xml metrics and returns the exit code: 0 when the report was produced
    and 2 when it could not be -- the file is missing, the define.xml would not load, or the
    report could not be written. 1 is deliberately unused: a metrics report describes a file
    rather than judging it, so unlike validate and definerefs it has no failed outcome
    :return: int exit code
    """
    args = set_cmd_line_args()
    try:
        metrics = DefineMetrics(Path(args.define), permissive=args.permissive)
        if args.out:
            metrics.collect_to_file(Path(args.out), show_datasets=not args.no_datasets,
                                    as_json=args.json)
        elif args.json:
            print(metrics.collect_to_json())
        else:
            metrics.collect_to_console(show_datasets=not args.no_datasets)
        return 0
    except DefineMetricsError as e:
        # the load failure message carries the validate utility guidance; stderr keeps it out
        # of a redirected report
        print(e, file=sys.stderr)
        return 2

def _quiet_exit(code):
    """Terminate immediately via os._exit, bypassing interpreter shutdown, so a late write to
    a closed pipe -- or a Ctrl-C during finalization -- cannot print an 'Exception ignored ...'
    message or traceback at exit. The report is long enough to be paged, so both are reachable.
    130 == 128 + SIGINT, the conventional Ctrl-C status; a broken pipe exits 0 since quitting the
    pager is not an error."""
    os._exit(code)

def set_cmd_line_args():
    """
    get the command-line arguments needed to report metrics on the define.xml input file
    :return: return the argparse object with the command-line parameters
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--define", help="path and file name of the define.xml file to "
                        "report on", required=True, dest="define")
    parser.add_argument("-o", "--out", help="path and file name of the report to create; "
                        "omit to print to the console", required=False, dest="out", default=None)
    parser.add_argument("--json", help="emit JSON instead of the text report",
                        required=False, dest="json", action="store_true")
    parser.add_argument("--no-datasets", help="omit the per-dataset table from the text report",
                        required=False, dest="no_datasets", action="store_true")
    parser.add_argument("--permissive", help="best-effort metrics for a non-conformant define.xml",
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
