"""Rules on variables and values: ItemDef, def:Origin, def:ValueListDef and def:ValueListRef,
def:WhereClauseDef, def:WhereClauseRef and RangeCheck."""
from . import Violation, rule, not_evaluated, SUBMISSION, NEEDS_IG
from . import values as V
from .checks import (absent_when, allowed_values, attr_matches, child_present_when, max_one_child, present_when,
                     ref_to, required_attr, required_child)

ITEM = "//odm:ItemDef"
ORIGIN = "//def:Origin"
COLLECTED_ORIGIN = "//def:Origin[@Type='Collected'][@Source='Investigator' or @Source='Subject']"
VALUE_LIST = "//def:ValueListDef"
VALUE_LIST_REF = "//def:ValueListRef"
WHERE_CLAUSE = "//def:WhereClauseDef"
WHERE_CLAUSE_REF = "//def:WhereClauseRef"
RANGE_CHECK = "//odm:RangeCheck"

LENGTH_TYPES = {"text", "integer", "float"}
SUPPLEMENTAL = ("SUPP", "SQ")
XPT = ".xpt"


def _data_type_in(types):
    return lambda doc, e: doc.attr(e, "DataType") in types


def _data_type_not_in(types):
    return lambda doc, e: doc.attr(e, "DataType") is not None and doc.attr(e, "DataType") not in types


def _referenced_from_a_dataset(doc, item) -> bool:
    return any(doc.display_name(ref.getparent()) == "ItemGroupDef" for ref in doc.item_refs_for(item.get("OID")))


# -- ItemDef -----------------------------------------------------------------------------------

rule("135", "CodeListRef", None, ITEM, max_one_child("CodeListRef"))
rule("137", "ItemDef", "OID", ITEM, required_attr("OID"))
rule("138", "ItemDef", "Name", ITEM, required_attr("Name"))
rule("139", "ItemDef", "DataType", ITEM, required_attr("DataType"))
rule("140", "ItemDef", "DataType", ITEM, allowed_values("DataType", V.DATA_TYPES))
rule("141", "ItemDef", "Length", ITEM,
     present_when("Length", _data_type_in(LENGTH_TYPES), because='@DataType is "text", "integer" or "float"'))
rule("143", "ItemDef", "Length", ITEM,
     absent_when("Length", _data_type_not_in(LENGTH_TYPES),
                 because='@DataType is not "text", "integer" or "float"'))
rule("144", "ItemDef", "Length", ITEM, attr_matches("Length", V.POSITIVE_INTEGER, "a positive integer"))
rule("145", "ItemDef", "SignificantDigits", ITEM,
     present_when("SignificantDigits", _data_type_in({"float"}), because='@DataType is "float"'))
rule("146", "ItemDef", "SignificantDigits", ITEM,
     attr_matches("SignificantDigits", V.NON_NEGATIVE_INTEGER, "a non-negative integer"))
rule("148", "ItemDef", "def:CommentOID", ITEM, ref_to("def:CommentOID", "def:CommentDef"))
rule("149", "CodeListRef", None, ITEM, not_evaluated, requires=NEEDS_IG)
rule("151", "CodeListRef", "CodeListOID", "//odm:CodeListRef", ref_to("CodeListOID", "CodeList"))
rule("162", "def:ValueListRef", None, ITEM, max_one_child("def:ValueListRef"))
rule("163", "def:ValueListRef", "ValueListOID", VALUE_LIST_REF, ref_to("ValueListOID", "def:ValueListDef"))
rule("164", "def:ValueListRef", "ValueListOID", VALUE_LIST_REF, required_attr("ValueListOID"))
rule("169", "Description", None, ITEM, max_one_child("Description"))
rule("266", "Description", None, f"{ITEM}/odm:Description/odm:TranslatedText", not_evaluated, requires=NEEDS_IG)


@rule("55", "def:ValueListRef", None, f"{ITEM}[@Name='QVAL'][not(def:ValueListRef)]")
def qval_has_a_value_list(doc, item):
    # the dataset variable only, through a direct ItemRef: the value-level ItemDefs of QVAL are
    # named QVAL too, and they are what the value list holds
    groups = [ref.getparent() for ref in doc.item_refs_for(item.get("OID"))
              if doc.display_name(ref.getparent()) == "ItemGroupDef"
              and (doc.attr(ref.getparent(), "Name") or "").startswith(SUPPLEMENTAL)]
    if groups:
        names = ", ".join(doc.attr(g, "Name") for g in groups)
        yield Violation(item, f"has no def:ValueListRef, but it is the QVAL variable of supplemental qualifier "
                              f"dataset {names}")


@rule("142", "ItemDef", "Length", VALUE_LIST)
def value_length_within_variable_length(doc, value_list):
    variables = doc.variables_for_value_list(value_list.get("OID"))
    for ref in doc.children(value_list, "ItemRef"):
        value_item = doc.item_def(doc.attr(ref, "ItemOID"))
        if value_item is None or not (doc.attr(value_item, "Length") or "").isdigit():
            continue
        value_length = int(doc.attr(value_item, "Length"))
        for variable in variables:
            if (doc.attr(variable, "Length") or "").isdigit() and value_length > int(doc.attr(variable, "Length")):
                yield Violation(value_item, f'@Length="{value_length}" is greater than @Length='
                                            f'"{doc.attr(variable, "Length")}" of ItemDef {variable.get("OID")}, '
                                            f'the variable that references value list {value_list.get("OID")}')


@rule("147", "ItemDef", "SASFieldName", f"{ITEM}[not(@SASFieldName)]", context=SUBMISSION)
def sas_field_name_required_for_xpt(doc, item):
    # the dataset variables only: a value-level ItemDef has no parent ItemGroupDef, and the CDISC
    # ADaM sample gives its value-level ItemDefs no SASFieldName
    for ref in doc.item_refs_for(item.get("OID")):
        group = ref.getparent()
        if doc.display_name(group) != "ItemGroupDef":
            continue
        href = doc.archive_href(group)
        if href and href.lower().endswith(XPT):
            yield Violation(item, f"@SASFieldName is missing, but dataset {doc.attr(group, 'Name')} is supplied "
                                  f'as "{href}" and the document is a submission')
            return


rule("154", "def:Origin", None, ITEM,
     child_present_when("def:Origin", lambda doc, e: not doc.children(e, "def:ValueListRef"),
                        because="the ItemDef has no def:ValueListRef and the document is a submission"),
     context=SUBMISSION)


@rule("155", "def:Origin", None, f"{ITEM}[not(def:Origin)]")
def origin_at_variable_or_value_level(doc, item):
    if not _referenced_from_a_dataset(doc, item):
        return
    refs = doc.children(item, "def:ValueListRef")
    if not refs:
        yield Violation(item, "has neither a def:Origin nor a def:ValueListRef")
        return
    value_list = doc.value_list(doc.attr(refs[0], "ValueListOID") or "")
    if value_list is None:
        return
    for ref in doc.children(value_list, "ItemRef"):
        value_item = doc.item_def(doc.attr(ref, "ItemOID"))
        if value_item is not None and not doc.children(value_item, "def:Origin"):
            yield Violation(item, f"has no def:Origin, and neither has value-level ItemDef "
                                  f"{value_item.get('OID')} in its value list {value_list.get('OID')}")


@rule("168", "Description", None, f"{ITEM}[not(odm:Description)]", context=SUBMISSION)
def dataset_variable_has_a_description(doc, item):
    if _referenced_from_a_dataset(doc, item):
        yield Violation(item, "has no Description, but it is referenced from an ItemGroupDef and the document "
                              "is a submission")


@rule("242", "ItemDef", "def:CommentOID", f"{ITEM}[not(@def:CommentOID)]")
def comment_required_when_no_data(doc, item):
    refs = [ref for ref in doc.item_refs_for(item.get("OID")) if doc.attr(ref, "def:HasNoData") == "Yes"]
    if refs:
        parent = doc.display_name(refs[0].getparent())
        yield Violation(item, f'@def:CommentOID is missing, but the ItemRef under {parent} '
                              f'{refs[0].getparent().get("OID")} has @def:HasNoData="Yes"')


# -- def:Origin --------------------------------------------------------------------------------

rule("158", "def:Origin", "Type", ORIGIN, required_attr("Type"))
rule("160", "def:Origin", "Type", ORIGIN, allowed_values("Type", V.ORIGIN_TYPES))
rule("161", "def:Origin", "Source", ORIGIN, allowed_values("Source", V.ORIGIN_SOURCES))
rule("243", "Description", None, ORIGIN, max_one_child("Description"))


@rule("159", "def:Origin", "Type", COLLECTED_ORIGIN)
def collected_origin_references_the_annotated_crf(doc, origin):
    crf = doc.annotated_crf_leaf_ids
    refs = doc.children(origin, "def:DocumentRef")
    if any(doc.attr(ref, "leafID") in crf for ref in refs):
        return
    source = doc.attr(origin, "Source")
    if not crf:
        yield Violation(origin, f'is @Type="Collected" with @Source="{source}", but the document has no '
                                f"def:AnnotatedCRF to reference")
    else:
        yield Violation(origin, f'is @Type="Collected" with @Source="{source}", but no def:DocumentRef names an '
                                f"annotated CRF leaf ({', '.join(sorted(crf))})")


# -- def:ValueListDef --------------------------------------------------------------------------

rule("235", "Description", None, VALUE_LIST, max_one_child("Description"))
rule("236", "def:ValueListDef", "OID", VALUE_LIST, required_attr("OID"))
rule("237", "ItemRef", None, VALUE_LIST, required_child("ItemRef"))

# -- def:WhereClauseDef and RangeCheck ---------------------------------------------------------

rule("80", "def:WhereClauseRef", "WhereClauseOID", WHERE_CLAUSE_REF, required_attr("WhereClauseOID"))
rule("81", "def:WhereClauseRef", "WhereClauseOID", WHERE_CLAUSE_REF,
     ref_to("WhereClauseOID", "def:WhereClauseDef"))
rule("82", "def:WhereClauseDef", "OID", WHERE_CLAUSE, required_attr("OID"))
rule("83", "def:WhereClauseDef", "def:CommentOID", WHERE_CLAUSE, ref_to("def:CommentOID", "def:CommentDef"))


@rule("84", "def:WhereClauseDef", "def:CommentOID", f"{WHERE_CLAUSE}[not(@def:CommentOID)]")
def comment_required_across_datasets(doc, where_clause):
    datasets = []
    for check in doc.children(where_clause, "RangeCheck"):
        item = doc.item_def(doc.attr(check, "def:ItemOID") or "")
        if item is not None:
            datasets.append({g.get("OID") for g in doc.owning_item_groups(item)})
    if len(datasets) > 1 and not set.intersection(*datasets):
        names = sorted(oid for group in datasets for oid in group)
        yield Violation(where_clause, f"@def:CommentOID is missing, but its RangeChecks reference items from "
                                      f"different datasets ({', '.join(names)})")


rule("85", "RangeCheck", None, WHERE_CLAUSE, required_child("RangeCheck"))
rule("86", "RangeCheck", "Comparator", RANGE_CHECK, allowed_values("Comparator", V.COMPARATORS))
rule("87", "RangeCheck", "Comparator", RANGE_CHECK, required_attr("Comparator"))
rule("88", "RangeCheck", "SoftHard", RANGE_CHECK, allowed_values("SoftHard", V.SOFT_OR_HARD))
rule("89", "RangeCheck", "SoftHard", RANGE_CHECK, required_attr("SoftHard"))
rule("90", "RangeCheck", "def:ItemOID", RANGE_CHECK, required_attr("def:ItemOID"))
rule("91", "RangeCheck", "def:ItemOID", RANGE_CHECK, ref_to("def:ItemOID", "ItemDef"))
rule("92", "CheckValue", None, RANGE_CHECK, required_child("CheckValue"))
