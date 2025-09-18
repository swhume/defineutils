from lxml import etree
from pathlib import Path
from typing import Union

class DefineHtmlGenerationError(Exception):
    pass

class DefineHtml:
    def __init__(self, define_xml_file: Path) -> None:
        self.define = Path(define_xml_file)
        self._does_define_file_exist()
        self.xslt = Path(__file__).parent.joinpath("define2-1.xsl")

    def transform_to_html_string(self, pretty_print: bool = True) -> str:
        """
        transforms define-xml to html and returns html as a string
        :param pretty_print: boolean that defaults to True
        :return: string
        """
        result_tree = self._transform()
        if not result_tree:
            return ""
        return etree.tostring(result_tree, pretty_print=pretty_print)

    def transform_to_html_file(self, html_file: Path,  pretty_print: bool = True) -> None:
        """
        transforms define-xml to html and returns html as a string
        :param html_file: Path to the file to save the html output
        :param pretty_print: Boolean that defaults to True
        :return: None
        """
        result_tree = self._transform()
        if not result_tree:
            return
        try:
            with open(html_file, 'wb') as f:
                f.write(etree.tostring(result_tree, pretty_print=pretty_print))
        except FileNotFoundError as e:
            raise DefineHtmlGenerationError(f"File {html_file} not found.\n{e}")
        except PermissionError as e:
            raise DefineHtmlGenerationError(f"Permission error attempting to write to {html_file}.\n{e}")
        except IsADirectoryError as e:
            raise DefineHtmlGenerationError(f"Error attempting to write to a directory {html_file}.\n{e}")

    def _transform(self) -> Union[etree.ElementTree, None]:
        """
        transforms a define.xml to an HTML file using the define2-1 XSL stylesheet.
        :return: html result tree
        """
        result_tree = None
        try:
            xml_tree = etree.parse(self.define)
            xsl_tree = etree.parse(self.xslt)
            transform = etree.XSLT(xsl_tree)
            result_tree = transform(xml_tree)
        except etree.XMLSyntaxError as e:
            raise DefineHtmlGenerationError(f"XML syntax error:\n{e}")
        except etree.ParseError as e:
            raise DefineHtmlGenerationError(f"XML parsing error:\n{e}")
        except etree.XSLTApplyError as e:
            raise DefineHtmlGenerationError(f"XSLT apply error:\n{e}")
        finally:
            return result_tree

    def _does_define_file_exist(self):
        """
        confirms that the define-xml file exists before attempting to transform it to HTML
        and raises a FileNotFoundError if the file does not exist
        """
        if not self.define.is_file():
            raise DefineHtmlGenerationError(f"File {str(self.define)} not found.")
