"""Rules on codelists: CodeList, CodeListItem, EnumeratedItem, ExternalCodeList and the codelist
Aliases."""
from . import Violation, rule, not_evaluated, SUBMISSION, NEEDS_CT
from . import values as V
from .checks import (all_or_none, allowed_values, attr_matches, max_one_child, present_when, ref_to,
                     required_attr, required_child, unique_in_document)
from ..document import NCI_EXT_CODE_ID

CODELIST = "//odm:CodeList"
ENUMERATED_ITEM = "//odm:EnumeratedItem"
CODELIST_ITEM = "//odm:CodeListItem"
EXTERNAL = "//odm:ExternalCodeList"

INTEGER = "an integer"


def nci_aliases(doc, codelist) -> list:
    """the CodeList's Alias children with @Context="nci:ExtCodeID" """
    return [a for a in doc.children(codelist, "Alias") if doc.attr(a, "Context") == NCI_EXT_CODE_ID]


# -- CodeList ----------------------------------------------------------------------------------

rule("152", "CodeList", "def:StandardOID", CODELIST,
     ref_to("def:StandardOID", "def:Standard", where=lambda doc, standard: doc.attr(standard, "Type") == "CT",
            because='the def:Standard must have @Type="CT"'))
rule("153", "CodeList", "def:IsNonStandard", CODELIST,
     present_when("def:IsNonStandard", lambda doc, e: not nci_aliases(doc, e),
                  because=f'the CodeList has no Alias[@Context="{NCI_EXT_CODE_ID}"]'))


@rule("165", "CodeList", None, CODELIST)
def codelist_has_items(doc, codelist):
    if not (doc.children(codelist, "EnumeratedItem") or doc.children(codelist, "CodeListItem")
            or doc.children(codelist, "ExternalCodeList")):
        yield Violation(codelist, "has no EnumeratedItem, CodeListItem or ExternalCodeList child element")


rule("166", "CodeList", "OID", CODELIST, required_attr("OID"))
rule("167", "CodeList", "def:IsNonStandard", CODELIST, allowed_values("def:IsNonStandard", V.YES_ONLY))
rule("171", "CodeList", "Name", CODELIST, required_attr("Name"))
rule("172", "CodeList", "Name", "/*", unique_in_document(CODELIST, "Name"))
rule("173", "CodeList", "DataType", CODELIST, required_attr("DataType"))
rule("174", "CodeList", "DataType", CODELIST, allowed_values("DataType", V.CODELIST_DATA_TYPES))


@rule("175", "CodeList", "SASFormatName", f"{CODELIST}[@SASFormatName]")
def sas_format_name_is_valid(doc, codelist):
    name = doc.attr(codelist, "SASFormatName")
    if V.SAS_FORMAT.fullmatch(name) is None:
        yield Violation(codelist, f'@SASFormatName="{name}" is not a SAS format name (a letter, underscore or $, '
                                  f"then letters, digits, underscores or periods, 8 characters at most)")
    elif doc.attr(codelist, "DataType") == "text" and not name.startswith("$"):
        yield Violation(codelist, f'@SASFormatName="{name}" does not start with $, but @DataType is "text"')


rule("176", "CodeList", "def:StandardOID", CODELIST,
     present_when("def:StandardOID", lambda doc, e: bool(nci_aliases(doc, e)),
                  because=f'an Alias[@Context="{NCI_EXT_CODE_ID}"] is present and the document is a submission'),
     context=SUBMISSION)
rule("177", "CodeList", "def:CommentOID", CODELIST, ref_to("def:CommentOID", "def:CommentDef"))
rule("244", "Description", None, CODELIST, max_one_child("Description"))


@rule("249", "Alias", "Context", f"{CODELIST}[@def:StandardOID]")
def standard_codelist_has_one_nci_alias(doc, codelist):
    count = len(nci_aliases(doc, codelist))
    if count == 0:
        yield Violation(codelist, f'has no Alias[@Context="{NCI_EXT_CODE_ID}"], but @def:StandardOID is present')
    elif count > 1:
        yield Violation(codelist, f'has {count} Alias[@Context="{NCI_EXT_CODE_ID}"] elements; exactly one is '
                                  f"expected with @def:StandardOID")


rule("250", "ExternalCodeList", None, CODELIST, max_one_child("ExternalCodeList"))

# -- EnumeratedItem ----------------------------------------------------------------------------

rule("178", "EnumeratedItem", "def:ExtendedValue", ENUMERATED_ITEM, allowed_values("def:ExtendedValue", V.YES_ONLY))
rule("179", "EnumeratedItem", "CodedValue", ENUMERATED_ITEM, not_evaluated, requires=NEEDS_CT)
rule("180", "EnumeratedItem", "CodedValue", ENUMERATED_ITEM, required_attr("CodedValue"))
rule("182", "EnumeratedItem", "Rank", ENUMERATED_ITEM, attr_matches("Rank", V.INTEGER, INTEGER))
rule("183", "EnumeratedItem", "Rank", CODELIST, all_or_none("EnumeratedItem", "Rank"))
rule("184", "EnumeratedItem", "OrderNumber", ENUMERATED_ITEM, attr_matches("OrderNumber", V.INTEGER, INTEGER))
rule("185", "EnumeratedItem", "OrderNumber", CODELIST, all_or_none("EnumeratedItem", "OrderNumber"))
rule("186", "EnumeratedItem", "def:ExtendedValue", ENUMERATED_ITEM, not_evaluated, requires=NEEDS_CT)
rule("187", "EnumeratedItem", "def:ExtendedValue", ENUMERATED_ITEM, not_evaluated, requires=NEEDS_CT)
rule("245", "Description", None, ENUMERATED_ITEM, max_one_child("Description"))

# -- CodeListItem ------------------------------------------------------------------------------

rule("191", "CodeListItem", "CodedValue", CODELIST_ITEM, required_attr("CodedValue"))
rule("192", "CodeListItem", "CodedValue", CODELIST_ITEM, not_evaluated, requires=NEEDS_CT)
rule("193", "CodeListItem", "Rank", CODELIST_ITEM, attr_matches("Rank", V.INTEGER, INTEGER))
rule("194", "CodeListItem", "Rank", CODELIST, all_or_none("CodeListItem", "Rank"))
rule("195", "CodeListItem", "OrderNumber", CODELIST_ITEM, attr_matches("OrderNumber", V.INTEGER, INTEGER))
rule("196", "CodeListItem", "OrderNumber", CODELIST, all_or_none("CodeListItem", "OrderNumber"))
rule("197", "CodeListItem", "def:ExtendedValue", CODELIST_ITEM, allowed_values("def:ExtendedValue", V.YES_ONLY))
rule("198", "Decode", None, CODELIST_ITEM, max_one_child("Decode"))
rule("199", "Decode", None, CODELIST_ITEM, required_child("Decode"))
rule("201", "CodeListItem", "def:ExtendedValue", CODELIST_ITEM, not_evaluated, requires=NEEDS_CT)
rule("202", "CodeListItem", "def:ExtendedValue", CODELIST_ITEM, not_evaluated, requires=NEEDS_CT)
rule("246", "Description", None, CODELIST_ITEM, max_one_child("Description"))

# -- ExternalCodeList --------------------------------------------------------------------------

rule("203", "ExternalCodeList", "Dictionary", EXTERNAL, required_attr("Dictionary"))
rule("204", "ExternalCodeList", "Version", EXTERNAL, required_attr("Version"))
