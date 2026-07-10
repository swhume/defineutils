import os
import signal
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
    except (BrokenPipeError, OSError) as e:
        # a reader (e.g. more/less/head) closed the pipe early. Windows may surface this
        # as a bare OSError (e.g. [Errno 22]) rather than a BrokenPipeError. A genuine -o
        # output-file error is not a broken pipe, so let it surface normally.
        if args.out and not isinstance(e, BrokenPipeError):
            raise
        _abort_broken_pipe()
    except KeyboardInterrupt:
        # the user pressed Ctrl-C (e.g. to quit the pager)
        _abort_interrupt()

def _abort_broken_pipe():
    """Exit quietly after a reader closed the pipe."""
    _quiet_stdout()
    # os._exit skips interpreter shutdown, so no stray flush of the closed pipe can leak
    # an 'Exception ignored ... BrokenPipeError' at exit.
    os._exit(0)

def _abort_interrupt():
    """Exit after Ctrl-C. On POSIX, reset SIGINT to its default handler and re-raise it so
    the process dies *by* the signal: this tells the parent shell the pipeline was
    interrupted, so it restores the prompt immediately instead of waiting for a keystroke."""
    _quiet_stdout()
    if os.name == "posix":
        signal.signal(signal.SIGINT, signal.SIG_DFL)
        os.kill(os.getpid(), signal.SIGINT)
    # os._exit bypasses interpreter shutdown entirely, so no late flush or re-raised
    # interrupt during finalization can print a traceback (this is what leaked a
    # KeyboardInterrupt at exit on Windows). 130 == 128 + SIGINT.
    os._exit(130)

def _quiet_stdout():
    """Redirect stdout to os.devnull *and drain its buffer there*, so an in-flight write to
    the closed pipe does not keep raising. Best effort: a no-op if stdout has no real fd."""
    try:
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, sys.stdout.fileno())
    except OSError:
        return
    try:
        sys.stdout.flush()
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
    # Outer safety net: catch a Ctrl-C / broken pipe raised while main()'s own handlers
    # are running or in the small window outside its try (observed on Windows).
    try:
        main()
    except KeyboardInterrupt:
        _abort_interrupt()
    except BrokenPipeError:
        _abort_broken_pipe()
