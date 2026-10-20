"""Rules on datasets: ItemGroupDef, its ItemRefs, Alias, def:Class and def:SubClass."""
import re

from . import Violation, rule, not_evaluated, SUBMISSION, NEEDS_IG, NEEDS_DATASETS
from . import values as V
from .checks import (absent_when, all_or_none, allowed_values, attr_matches, attrs_equal, child_present_when,
                     forbidden_child, max_one_child, present_when, ref_to, required_attr, required_child,
                     unique_among_siblings, value_when)

MDV = "//odm:MetaDataVersion"
GROUP = "//odm:ItemGroupDef"
ITEM_REF = "//odm:ItemRef"
ALIAS = "//odm:Alias"
CLASS = "//def:Class"
SUB_CLASS = "//def:SubClass"

INTEGER = "an integer"
SDTM_OR_SEND = ("SDTM", "SEND")
ADAM = ("ADaM",)
SUPPLEMENTAL = ("SUPP", "SQ")
TRIAL_DESIGN = "TRIAL DESIGN"

FILENAME = re.compile(r"[^/\\]+$")


def standard_name(doc, group):
    """the @Name of the def:Standard the ItemGroupDef's def:StandardOID names, or None"""
    standard = doc.standard(doc.attr(group, "def:StandardOID") or "")
    return doc.attr(standard, "Name") if standard is not None else None


def _follows(prefixes):
    def predicate(doc, group):
        name = standard_name(doc, group)
        return name is not None and name.startswith(prefixes)
    return predicate


def _has(attribute):
    return lambda doc, e: doc.attr(e, attribute) is not None


def _lacks(attribute):
    return lambda doc, e: doc.attr(e, attribute) is None


def _equals(attribute, value):
    return lambda doc, e: doc.attr(e, attribute) == value


# -- ItemGroupDef ------------------------------------------------------------------------------

rule("93", "ItemGroupDef", None, MDV, required_child("ItemGroupDef"), context=SUBMISSION)
rule("94", "ItemGroupDef", "OID", GROUP, required_attr("OID"))
rule("104", "ItemGroupDef", "Name", GROUP, required_attr("Name"))
rule("105", "ItemGroupDef", "Domain", GROUP,
     present_when("Domain", _follows(SDTM_OR_SEND), because="the dataset follows an SDTM or SEND standard"))
rule("106", "ItemGroupDef", "Domain", GROUP,
     absent_when("Domain", _follows(ADAM), because="the dataset follows an ADaM standard"))
rule("108", "ItemGroupDef", "SASDatasetName", GROUP, required_attr("SASDatasetName"), context=SUBMISSION)
rule("109", "ItemGroupDef", "SASDatasetName", GROUP,
     attr_matches("SASDatasetName", V.SAS_NAME, "a SAS dataset name (a letter or underscore, then letters, "
                                                 "digits or underscores, 8 characters at most)"))
rule("110", "ItemGroupDef", "SASDatasetName", GROUP, attrs_equal("SASDatasetName", "Name"))


@rule("112", "ItemGroupDef", "SASDatasetName", f"{GROUP}[@SASDatasetName]")
def sas_dataset_name_matches_the_archive_file(doc, group):
    href = doc.archive_href(group)
    filename = FILENAME.search(href) if href else None
    if filename is None:
        return
    stem = filename.group().split(".")[0]
    name = doc.attr(group, "SASDatasetName")
    if stem.upper() != name.upper():
        yield Violation(group, f'@SASDatasetName="{name}" does not match the file name in the archive '
                               f'location "{href}"')


rule("113", "ItemGroupDef", "Repeating", GROUP, required_attr("Repeating"))
rule("114", "ItemGroupDef", "Repeating", GROUP, allowed_values("Repeating", V.YES_OR_NO))
rule("115", "ItemGroupDef", "IsReferenceData", GROUP, allowed_values("IsReferenceData", V.YES_OR_NO))
rule("116", "ItemGroupDef", "Purpose", GROUP, allowed_values("Purpose", V.PURPOSES))
rule("117", "ItemGroupDef", "Purpose", GROUP, required_attr("Purpose"))
rule("118", "ItemGroupDef", "def:Structure", GROUP, required_attr("def:Structure"))
rule("119", "ItemGroupDef", "def:ArchiveLocationID", GROUP,
     present_when("def:ArchiveLocationID", lambda doc, e: doc.attr(e, "def:HasNoData") != "Yes",
                  because='@def:HasNoData is not "Yes" and the document is a submission'),
     context=SUBMISSION)
rule("120", "ItemGroupDef", "def:ArchiveLocationID", GROUP,
     ref_to("def:ArchiveLocationID", "def:leaf", scope="self"))
rule("121", "ItemGroupDef", "def:IsNonStandard", GROUP,
     absent_when("def:IsNonStandard", _has("def:StandardOID"), because="@def:StandardOID is present"))
rule("122", "ItemGroupDef", "def:IsNonStandard", GROUP,
     present_when("def:IsNonStandard", _lacks("def:StandardOID"), because="@def:StandardOID is absent"))
rule("123", "ItemGroupDef", "def:IsNonStandard", GROUP, allowed_values("def:IsNonStandard", V.YES_ONLY))
rule("124", "ItemGroupDef", "def:StandardOID", GROUP,
     ref_to("def:StandardOID", "def:Standard", where=lambda doc, standard: doc.attr(standard, "Type") == "IG",
            because='the def:Standard must have @Type="IG"'))
rule("125", "ItemGroupDef", "def:HasNoData", GROUP,
     present_when("def:HasNoData", _lacks("def:ArchiveLocationID"),
                  because="@def:ArchiveLocationID is absent and the document is a submission"),
     context=SUBMISSION)
rule("126", "ItemGroupDef", "def:HasNoData", GROUP, allowed_values("def:HasNoData", V.YES_ONLY))
rule("127", "ItemGroupDef", "def:CommentOID", GROUP, ref_to("def:CommentOID", "def:CommentDef"))
rule("128", "Description", None, GROUP, required_child("Description"), context=SUBMISSION)
rule("129", "Description", None, GROUP, max_one_child("Description"))
rule("131", "def:Class", None, GROUP, required_child("def:Class"), context=SUBMISSION)
rule("265", "Description", None, f"{GROUP}/odm:Description/odm:TranslatedText", not_evaluated, requires=NEEDS_IG)
rule("239", "ItemGroupDef", "IsReferenceData", GROUP,
     value_when("IsReferenceData", "Yes",
                lambda doc, e: any(doc.attr(c, "Name") == TRIAL_DESIGN for c in doc.children(e, "def:Class")),
                because=f'def:Class/@Name is "{TRIAL_DESIGN}"'))
rule("240", "ItemGroupDef", "def:CommentOID", GROUP,
     present_when("def:CommentOID", _equals("def:HasNoData", "Yes"), because='@def:HasNoData is "Yes"'))
rule("241", "ItemRef", None, GROUP, required_child("ItemRef"))
rule("251", "ItemGroupDef", "Purpose", GROUP,
     value_when("Purpose", "Tabulation", _follows(SDTM_OR_SEND),
                because="the dataset follows an SDTM or SEND standard"))
rule("252", "ItemGroupDef", "Purpose", GROUP,
     value_when("Purpose", "Analysis", _follows(ADAM), because="the dataset follows an ADaM standard"))
rule("260", "ItemGroupDef", "Repeating", GROUP,
     value_when("Repeating", "No", _equals("IsReferenceData", "Yes"), because='@IsReferenceData is "Yes"'))

# -- Description on datasets (57) and Alias ----------------------------------------------------

rule("57", "Description", None, GROUP,
     child_present_when("Description", _equals("def:IsNonStandard", "Yes"),
                        because='@def:IsNonStandard is "Yes"'))
rule("95", "Alias", None, GROUP,
     child_present_when("Alias", lambda doc, e: doc.attr(e, "Domain") is not None
                        and doc.attr(e, "Domain") != doc.attr(e, "Name"),
                        because="@Domain differs from @Name"))


@rule("96", "Alias", None, f"{GROUP}[not(odm:Alias)]", context=SUBMISSION)
def supplemental_qualifier_dataset_has_an_alias(doc, group):
    name, domain = doc.attr(group, "Name") or "", doc.attr(group, "Domain")
    if not name.startswith("SUPP") or domain is None:
        return
    sharing = [g for g in doc.xpath(doc.root, GROUP) if doc.attr(g, "Domain") == domain]
    if len(sharing) > 1:
        yield Violation(group, f'has no Alias child element, but it is a supplemental qualifier dataset '
                               f'sharing @Domain="{domain}" with {len(sharing) - 1} other dataset(s)')


rule("97", "Alias", None, ALIAS, not_evaluated, requires=NEEDS_IG)
rule("98", "Alias", None, ALIAS, not_evaluated, requires=NEEDS_IG)
rule("99", "Alias", None, ALIAS, not_evaluated, requires=NEEDS_IG)
rule("100", "Alias", "Context", ALIAS, required_attr("Context"))
rule("101", "Alias", "Name", ALIAS, required_attr("Name"))

# -- def:Class and def:SubClass ----------------------------------------------------------------

rule("132", "def:Class", "Name", CLASS, allowed_values("Name", V.ITEM_GROUP_CLASSES))
rule("134", "def:SubClass", "Name", SUB_CLASS, required_attr("Name"))
rule("261", "def:SubClass", "Name", SUB_CLASS, allowed_values("Name", V.ITEM_GROUP_SUB_CLASSES))
rule("262", "def:SubClass", "ParentClass", SUB_CLASS, allowed_values("ParentClass", V.PARENT_CLASSES))

# -- ItemRef -----------------------------------------------------------------------------------

rule("65", "ItemRef", "ItemOID", ITEM_REF, ref_to("ItemOID", "ItemDef"))
rule("66", "ItemRef", "OrderNumber", ITEM_REF, attr_matches("OrderNumber", V.INTEGER, INTEGER))
rule("67", "ItemRef", "Mandatory", ITEM_REF, not_evaluated, requires=NEEDS_IG)
rule("68", "ItemRef", "Mandatory", ITEM_REF, allowed_values("Mandatory", V.YES_OR_NO))
rule("69", "ItemRef", "Mandatory", ITEM_REF, required_attr("Mandatory"))


@rule("70", "ItemRef", "KeySequence", GROUP, context=SUBMISSION)
def dataset_has_a_key(doc, group):
    if not any(doc.attr(ref, "KeySequence") for ref in doc.children(group, "ItemRef")):
        yield Violation(group, "no ItemRef has a @KeySequence, and a submission dataset needs at least one key")


rule("71", "ItemRef", "KeySequence", GROUP, unique_among_siblings("ItemRef", "KeySequence"))
rule("72", "ItemRef", "KeySequence", ITEM_REF, attr_matches("KeySequence", V.INTEGER, INTEGER))


@rule("73", "ItemRef", "MethodOID", f"{ITEM_REF}[not(@MethodOID)]")
def method_required_for_derived(doc, ref):
    item = doc.item_def(doc.attr(ref, "ItemOID"))
    if item is not None and doc.xpath(item, "def:Origin[@Type='Derived']"):
        yield Violation(ref, f'ItemDef {item.get("OID")} has def:Origin/@Type="Derived" but the ItemRef has '
                             f"no @MethodOID")


rule("74", "ItemRef", "MethodOID", ITEM_REF, ref_to("MethodOID", "MethodDef"))
rule("75", "ItemRef", "def:IsNonStandard", ITEM_REF, allowed_values("def:IsNonStandard", V.YES_ONLY))
rule("76", "ItemRef", "def:HasNoData", ITEM_REF, not_evaluated, requires=NEEDS_DATASETS)
rule("77", "ItemRef", "def:HasNoData", ITEM_REF, allowed_values("def:HasNoData", V.YES_ONLY))
rule("79", "ItemRef", None, f"{GROUP}/odm:ItemRef",
     forbidden_child("def:WhereClauseRef", "it is permitted only under def:ValueListDef/ItemRef"))
rule("238", "ItemRef", "OrderNumber", f"{GROUP} | //def:ValueListDef", all_or_none("ItemRef", "OrderNumber"))
