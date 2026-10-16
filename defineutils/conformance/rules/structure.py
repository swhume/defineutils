"""Rules on the document structure: ODM, Study, GlobalVariables, MetaDataVersion, def:Standards,
the document references (def:AnnotatedCRF, def:SupplementalDoc, def:DocumentRef, def:PDFPageRef),
Description/TranslatedText, and the document-wide OID and element-order rules."""
from . import Violation, rule, not_evaluated, SUBMISSION, NEEDS_IG
from . import values as V
from .checks import (allowed_values, at_most_in_document, attr_matches, element_order, max_one_child,
                     present_when, ref_to, required_attr, required_child, root_is, unique_among_siblings,
                     unique_in_document)

ROOT = "/*"
ODM = "/odm:ODM"
STUDY = "//odm:Study"
GLOBALS = "//odm:GlobalVariables"
MDV = "//odm:MetaDataVersion"
STANDARD = "//def:Standards/def:Standard"
PAGE_REF = "//def:PDFPageRef"

DATETIME = "an ISO 8601 date-time (YYYY-MM-DDThh:mm:ss)"
INTEGER = "an integer"

# -- the document ------------------------------------------------------------------------------

rule("1", "ALL elements", None, "//*[*]", element_order())
rule("2", "ODM", None, ROOT, root_is("ODM"))
rule("3", "ODM", None, ROOT, at_most_in_document("//odm:ODM", 1, "ODM elements"))
rule("230", "All", "OID", ROOT, unique_in_document("//*[@OID]", "OID"))

# -- ODM ---------------------------------------------------------------------------------------

rule("4", "ODM", "CreationDateTime", ODM, attr_matches("CreationDateTime", V.DATETIME, DATETIME))
rule("5", "ODM", "AsOfDateTime", ODM, attr_matches("AsOfDateTime", V.DATETIME, DATETIME))
rule("6", "ODM", "ODMVersion", ODM, required_attr("ODMVersion"))
rule("7", "ODM", "ODMVersion", ODM, allowed_values("ODMVersion", V.ODM_VERSIONS))
rule("8", "ODM", "FileType", ODM, allowed_values("FileType", V.FILE_TYPES))
rule("9", "ODM", "FileOID", ODM, required_attr("FileOID"))
rule("13", "ODM", "CreationDateTime", ODM, required_attr("CreationDateTime"))
rule("16", "ODM", "def:Context", ODM, required_attr("def:Context"))
rule("17", "ODM", "def:Context", ODM, allowed_values("def:Context", V.CONTEXTS))
rule("254", "ODM", "CreationDateTime", ODM, required_attr("CreationDateTime"))
rule("255", "ODM", "FileType", ODM, required_attr("FileType"))

# -- Study and GlobalVariables -----------------------------------------------------------------

rule("10", "Study", None, ODM, required_child("Study"))
rule("11", "Study", None, ODM, max_one_child("Study"))
rule("12", "Study", "OID", STUDY, required_attr("OID"))
rule("14", "GlobalVariables", None, STUDY, required_child("GlobalVariables"))
rule("15", "GlobalVariables", None, STUDY, max_one_child("GlobalVariables"))
rule("18", "StudyName", None, GLOBALS, required_child("StudyName"))
rule("19", "StudyName", None, GLOBALS, max_one_child("StudyName"))
rule("20", "StudyDescription", None, GLOBALS, required_child("StudyDescription"))
rule("21", "StudyDescription", None, GLOBALS, max_one_child("StudyDescription"))
rule("22", "ProtocolName", None, GLOBALS, required_child("ProtocolName"))
rule("23", "ProtocolName", None, GLOBALS, max_one_child("ProtocolName"))

# -- MetaDataVersion ---------------------------------------------------------------------------

rule("24", "MetaDataVersion", None, STUDY, required_child("MetaDataVersion"))
rule("25", "MetaDataVersion", None, STUDY, max_one_child("MetaDataVersion"))
rule("26", "MetaDataVersion", "OID", MDV, required_attr("OID"))
rule("27", "MetaDataVersion", "Name", MDV, required_attr("Name"))
rule("28", "MetaDataVersion", "def:DefineVersion", MDV,
     attr_matches("def:DefineVersion", V.DEFINE_VERSION, '"2.0.0" or "2.1.<n>"'))
rule("29", "MetaDataVersion", "def:DefineVersion", MDV, required_attr("def:DefineVersion"))
rule("30", "MetaDataVersion", "def:CommentOID", MDV, ref_to("def:CommentOID", "def:CommentDef"))

# -- def:Standards -----------------------------------------------------------------------------

rule("31", "def:Standards", None, MDV, required_child("def:Standards"), context=SUBMISSION)
rule("32", "def:Standards", None, MDV, max_one_child("def:Standards"))
rule("33", "def:Standard", "Name", STANDARD, required_attr("Name"))
rule("34", "def:Standard", "Type", STANDARD, required_attr("Type"))
rule("35", "def:Standard", "PublishingSet", STANDARD,
     present_when("PublishingSet", lambda doc, e: doc.attr(e, "Type") == "CT", because='@Type is "CT"'))
rule("36", "def:Standard", "Version", STANDARD, required_attr("Version"))
rule("233", "def:Standard", None, "//def:Standards", required_child("def:Standard"))
rule("256", "def:Standard", "def:CommentOID", STANDARD, ref_to("def:CommentOID", "def:CommentDef"))
rule("257", "def:Standard", "OID", STANDARD, required_attr("OID"))
rule("258", "def:Standard", None, "//def:Standards", required_child("def:Standard"))
rule("263", "def:Standard", "Version", STANDARD, not_evaluated, requires=NEEDS_IG)
rule("264", "def:Standard", "Status", STANDARD, allowed_values("Status", V.STANDARD_STATUSES))

# -- documents ---------------------------------------------------------------------------------

rule("38", "def:AnnotatedCRF", None, MDV, max_one_child("def:AnnotatedCRF"))
rule("39", "def:DocumentRef", None, "//def:AnnotatedCRF", required_child("def:DocumentRef"))
rule("42", "def:DocumentRef", "leafID", "//def:DocumentRef", required_attr("leafID"))
rule("43", "def:DocumentRef", "leafID", "//def:DocumentRef", ref_to("leafID", "def:leaf"))
rule("51", "def:SupplementalDoc", None, MDV, max_one_child("def:SupplementalDoc"))
rule("54", "def:DocumentRef", None, "//def:SupplementalDoc", required_child("def:DocumentRef"))


@rule("44", "def:PDFPageRef", None,
      "//def:Origin[@Type='Collected'][@Source='Investigator' or @Source='Subject']/def:DocumentRef")
def page_ref_required_for_collected_origin(doc, document_ref):
    if not doc.children(document_ref, "def:PDFPageRef"):
        source = doc.attr(document_ref.getparent(), "Source")
        yield Violation(document_ref, f"has no def:PDFPageRef child element, but the def:Origin is "
                                      f'@Type="Collected" with @Source="{source}"')


def _physical_without_page_refs(doc, page_ref) -> bool:
    return doc.attr(page_ref, "PageRefs") is None and doc.attr(page_ref, "Type") == "PhysicalRef"


rule("45", "def:PDFPageRef", "Type", PAGE_REF, allowed_values("Type", V.PDF_PAGE_TYPES))
rule("46", "def:PDFPageRef", "Type", PAGE_REF, required_attr("Type"))
rule("47", "def:PDFPageRef", "FirstPage", PAGE_REF, attr_matches("FirstPage", V.INTEGER, INTEGER))
rule("48", "def:PDFPageRef", "FirstPage", PAGE_REF,
     present_when("FirstPage", _physical_without_page_refs,
                  because='@PageRefs is absent and @Type is "PhysicalRef"'))
rule("49", "def:PDFPageRef", "LastPage", PAGE_REF, attr_matches("LastPage", V.INTEGER, INTEGER))
rule("50", "def:PDFPageRef", "LastPage", PAGE_REF,
     present_when("LastPage", _physical_without_page_refs,
                  because='@PageRefs is absent and @Type is "PhysicalRef"'))

# -- Description and TranslatedText ------------------------------------------------------------

rule("60", "Description", None, "//odm:Description", required_child("TranslatedText"))
rule("61", "Description", None, "//odm:Description", required_child("TranslatedText"))
rule("62", "Decode", None, "//odm:Decode", required_child("TranslatedText"))
rule("63", "TranslatedText", "xml:lang", "//odm:Description | //odm:Decode",
     unique_among_siblings("TranslatedText", "xml:lang", absent_is_value=True))
