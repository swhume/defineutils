from pathlib import Path
import argparse
from validate.validate import DefineSchemaValidator, DefineSchemaValidationError

def main():
    args = set_cmd_line_args()
    try:
        validator = DefineSchemaValidator(Path(args.define))
        result = validator.validate_define_file()
    except DefineSchemaValidationError as e:
        print(e)
    else:
        print(result)


def set_cmd_line_args():
    """
    get the define.xml from the command-line - defaults to "define.xml" in the current directory
    :return: return the argparse object with the command-line parameters
    """
    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--define", help="path and file name of the define.xml file", required=False,
                        dest="define", default=str(Path(__file__).parent.joinpath("define.xml")))
    args = parser.parse_args()
    return args

if __name__ == "__main__":
    main()