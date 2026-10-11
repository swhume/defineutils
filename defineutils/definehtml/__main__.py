import sys
import traceback
from pathlib import Path
import argparse
from defineutils.definehtml import DefineHtml, DefineHtmlGenerationError

def main():
    """
    generates the define.html and returns the exit code: 0 when the HTML was written; 2 when it
    was not -- the define.xml is missing, is not well-formed Define-XML v2.1, the transform
    failed, or the HTML could not be written; and 1 when an unexpected error occurred, with its
    traceback on stderr so it can be reported. Ctrl-C exits 130
    :return: int exit code
    """
    args = set_cmd_line_args()
    # -o defaults to <define stem>.html beside the input; DefineHtml refuses an -o that is the input
    out = Path(args.out) if args.out else Path(args.define).with_suffix(".html")
    try:
        dh = DefineHtml(Path(args.define), codelist_items=args.codelist_items,
                        methods_table=not args.no_methods_table, comments_table=args.comments_table,
                        prefixes=args.prefixes, length_format=args.length_format)
        dh.transform_to_html_file(out)
        return 0
    except DefineHtmlGenerationError as e:
        print(e, file=sys.stderr)
        return 2
    except Exception:
        traceback.print_exc()
        return 1

def set_cmd_line_args():
    """
    get the command-line arguments needed to convert the define.xml input file into HTML using XSL
    :return: return the argparse object with the command-line parameters
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--define", help="path and file name of the define.xml file",
                        required=True, dest="define")
    parser.add_argument("-o", "--out", help="path and file name of HTML file to create; omit to "
                        "write <define name>.html beside the define.xml", required=False, dest="out",
                        default=None)
    parser.add_argument("--codelist-items", help="list a codelist's terms in the Controlled Terms "
                        "column when it has at most N terms, otherwise link to the codelist "
                        "(default 5)", required=False, dest="codelist_items", type=int, default=5,
                        metavar="N")
    parser.add_argument("--comments-table", help="add the Comments table", required=False,
                        dest="comments_table", action="store_true")
    parser.add_argument("--no-methods-table", help="omit the Methods table", required=False,
                        dest="no_methods_table", action="store_true")
    parser.add_argument("--prefixes", help="label comments, methods and origins with [Comment], "
                        "[Method] and [Origin]", required=False, dest="prefixes", action="store_true")
    parser.add_argument("--length-format", help="show Length [Significant Digits] : Display Format "
                        "in the length column", required=False, dest="length_format",
                        action="store_true")
    args = parser.parse_args()
    return args

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        # 130 == 128 + SIGINT, the conventional Ctrl-C status
        sys.exit(130)
