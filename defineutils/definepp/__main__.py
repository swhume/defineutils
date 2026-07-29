import os
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
    except (BrokenPipeError, OSError) as e:
        # a reader (e.g. more/less/head) closed the pipe early. Windows may surface this
        # as a bare OSError (e.g. [Errno 22]) rather than a BrokenPipeError. A genuine -o
        # output-file error is not a broken pipe, so let it surface normally.
        if args.out and not isinstance(e, BrokenPipeError):
            raise
        _quiet_exit(0)
    except KeyboardInterrupt:
        # the user pressed Ctrl-C (e.g. to quit the pager)
        _quiet_exit(130)

def _quiet_exit(code):
    """Terminate immediately via os._exit, bypassing interpreter shutdown. Because Python
    never gets to flush its std streams, no stray write to the closed pipe -- nor a late
    Ctrl-C during finalization -- can print an 'Exception ignored ...' message or traceback
    at exit (the failure seen on Windows). 130 == 128 + SIGINT, the conventional Ctrl-C
    status; a broken pipe exits 0 since quitting the pager is not an error."""
    os._exit(code)

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
    # Outer safety net: catch a Ctrl-C / broken pipe raised while main()'s own handlers
    # are running or in the small window outside its try (observed on Windows).
    try:
        main()
    except KeyboardInterrupt:
        _quiet_exit(130)
    except BrokenPipeError:
        _quiet_exit(0)
