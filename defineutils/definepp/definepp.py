import os
import sys
from lxml import etree
from pathlib import Path
from typing import Union

class DefinePrettyPrintError(Exception):
    pass

class DefinePrettyPrinter:
    def __init__(self, define_xml_file: Path) -> None:
        self.define = Path(define_xml_file)
        self._does_define_file_exist()

    def pretty_print_to_string(self) -> str:
        """
        pretty-prints the define-xml and returns the formatted xml as a string
        :return: string
        """
        return self._pretty_print_bytes().decode("utf-8")

    def pretty_print_to_file(self, out_file: Path) -> None:
        """
        pretty-prints the define-xml and writes the formatted xml to out_file
        :param out_file: Path to the file to save the formatted define.xml output
        :return: None
        """
        pretty = self._pretty_print_bytes()
        try:
            with open(out_file, 'wb') as f:
                f.write(pretty)
        except FileNotFoundError as e:
            raise DefinePrettyPrintError(f"File {out_file} not found.\n{e}")
        except PermissionError as e:
            raise DefinePrettyPrintError(f"Permission error attempting to write to {out_file}.\n{e}")
        except IsADirectoryError as e:
            raise DefinePrettyPrintError(f"Error attempting to write to a directory {out_file}.\n{e}")

    def pretty_print_to_console(self, head: Union[int, None] = None) -> None:
        """
        pretty-prints the define-xml and writes the formatted xml to stdout, optionally
        limited to the first head lines so the output can be piped into a pager (e.g. more)
        :param head: optional maximum number of lines to print to the console
        :return: None
        """
        lines = self.pretty_print_to_string().splitlines()
        if head is not None:
            lines = lines[:head]
        out = "\n".join(lines)
        if out:
            out += "\n"
        try:
            sys.stdout.write(out)
            sys.stdout.flush()
        except BrokenPipeError:
            # the reader (e.g. more/less/head) closed the pipe early; suppress the traceback
            # by redirecting the remaining stdout to devnull, then exit cleanly
            devnull = os.open(os.devnull, os.O_WRONLY)
            os.dup2(devnull, sys.stdout.fileno())
            sys.exit(0)

    def _pretty_print_bytes(self) -> bytes:
        """
        parses the define.xml and returns a pretty-printed (indented) UTF-8 xml byte string.
        The reformat is byte-preserving apart from whitespace: comments, processing
        instructions, element/attribute order and namespaces are all retained.
        :return: bytes
        """
        try:
            parser = etree.XMLParser(remove_blank_text=True)
            tree = etree.parse(self.define, parser)
        except etree.XMLSyntaxError as e:
            raise DefinePrettyPrintError(f"Unable to parse {self.define} as XML.\n{e}")
        return etree.tostring(tree, pretty_print=True, xml_declaration=True, encoding="UTF-8")

    def _does_define_file_exist(self):
        """
        confirms that the define-xml file exists before attempting to pretty-print it
        and raises a DefinePrettyPrintError if the file does not exist
        """
        if not self.define.is_file():
            raise DefinePrettyPrintError(f"File {str(self.define)} not found.")
