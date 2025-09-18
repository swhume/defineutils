from pathlib import Path
import argparse
from definehtml.definehtml import DefineHtml
from definehtml.definehtml import DefineHtmlGenerationError

def main():
    args = set_cmd_line_args()
    try:
        dh = DefineHtml(Path(args.define))
        dh.transform_to_html_file(Path(args.out))
    except DefineHtmlGenerationError as e:
        print(e)

def set_cmd_line_args():
    """
    get the command-line arguments needed to convert the define.xml input file into HTML using XSL
    :return: return the argparse object with the command-line parameters
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--define", help="path and file name of the define.xml file", required=False,
                        dest="define", default=str(Path(__file__).parent.joinpath("define.xml")))
    parser.add_argument("-o", "--out", help="path and file name of HTML file to create", required=False,
                        dest="out", default=str(Path(__file__).parent.joinpath("define.html")))
    args = parser.parse_args()
    return args

if __name__ == "__main__":
    main()