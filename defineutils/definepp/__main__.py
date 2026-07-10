import os
import sys
from pathlib import Path
import argparse
from defineutils.definepp import DefinePrettyPrinter, DefinePrettyPrintError

def main():
    args = set_cmd_line_args()
    try:
        pp = DefinePrettyPrinter(Path(args.define))
        if args.out:
            pp.pretty_print_to_file(Path(args.out))
        else:
            pp.pretty_print_to_console(head=args.head)
    except DefinePrettyPrintError as e:
        print(e)
    except BrokenPipeError:
        # the reader (e.g. more/less/head) closed the pipe early
        _silence_stdout()
        sys.exit(0)
    except KeyboardInterrupt:
        # the user pressed Ctrl-C (e.g. to quit the pager)
        _silence_stdout()
        sys.exit(130)

def _silence_stdout():
    """Redirect stdout's fd to os.devnull so the interpreter's shutdown flush of any
    remaining buffered output does not raise a second BrokenPipeError. Best effort."""
    try:
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, sys.stdout.fileno())
    except OSError:
        pass

def set_cmd_line_args():
    """
    get the command-line arguments needed to pretty-print the define.xml input file
    :return: return the argparse object with the command-line parameters
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--define", help="path and file name of the define.xml file to pretty-print",
                        required=True, dest="define")
    parser.add_argument("-o", "--out", help="path and file name of the formatted define.xml to create; "
                        "omit to print to the console", required=False, dest="out", default=None)
    parser.add_argument("-H", "--head", help="max number of lines to print to the console (ignored when -o is set)",
                        required=False, dest="head", type=int, default=None)
    args = parser.parse_args()
    return args

if __name__ == "__main__":
    main()
