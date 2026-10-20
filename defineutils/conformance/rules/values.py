"""The enumerations and lexical patterns the conformance rules test values against.

They are hand-coded from the CDISC rule text rather than read from the XSD at runtime, because
four of them deliberately differ from the schema: DATA_TYPES (rule 140) is the 12 Define-XML
values, not the 22 ODM ones; CODELIST_DATA_TYPES (174) leaves out "string"; METHOD_TYPES (209)
is Computation and Imputation only; and ORIGIN_TYPES (160) is the six C170449 values without
"Other". XSD_TYPES names the schema type each of the others corresponds to, and
tests/test_conformance.py keeps them equal to the schema's enumeration facets.
"""
import re

CONTEXTS = {"Submission", "Other"}
ODM_VERSIONS = {"1.3.2"}
FILE_TYPES = {"Snapshot"}
YES_OR_NO = {"Yes", "No"}
YES_ONLY = {"Yes"}
PDF_PAGE_TYPES = {"PhysicalRef", "NamedDestination"}
COMPARATORS = {"LT", "LE", "GT", "GE", "EQ", "NE", "IN", "NOTIN"}
SOFT_OR_HARD = {"Soft", "Hard"}
PURPOSES = {"Tabulation", "Analysis"}
STANDARD_TYPES = {"IG", "CT"}
STANDARD_STATUSES = {"Draft", "Final", "Provisional"}
ORIGIN_SOURCES = {"Investigator", "Sponsor", "Subject", "Vendor"}
ITEM_GROUP_CLASSES = {"ADAM OTHER", "BASIC DATA STRUCTURE", "DEVICE LEVEL ANALYSIS DATASET", "EVENTS",
                      "FINDINGS", "FINDINGS ABOUT", "INTERVENTIONS", "MEDICAL DEVICE BASIC DATA STRUCTURE",
                      "MEDICAL DEVICE OCCURRENCE DATA STRUCTURE", "OCCURRENCE DATA STRUCTURE",
                      "REFERENCE DATA STRUCTURE", "RELATIONSHIP", "SPECIAL PURPOSE", "STUDY REFERENCE",
                      "SUBJECT LEVEL ANALYSIS DATASET", "TRIAL DESIGN"}
ITEM_GROUP_SUB_CLASSES = {"ADVERSE EVENT", "MEDICAL DEVICE TIME-TO-EVENT", "NON-COMPARTMENTAL ANALYSIS",
                          "POPULATION PHARMACOKINETIC ANALYSIS", "TIME-TO-EVENT"}
PARENT_CLASSES = ITEM_GROUP_CLASSES | ITEM_GROUP_SUB_CLASSES

# the four that deliberately differ from the XSD
DATA_TYPES = {"text", "integer", "float", "date", "datetime", "time", "partialDate", "partialTime",
              "partialDatetime", "incompleteDatetime", "durationDatetime", "intervalDatetime"}
CODELIST_DATA_TYPES = {"text", "float", "integer"}
METHOD_TYPES = {"Computation", "Imputation"}
ORIGIN_TYPES = {"Assigned", "Collected", "Derived", "Not Available", "Predecessor", "Protocol"}

# enumeration -> the simple type in the bundled schemas with the same values
XSD_TYPES = {"ODMContext": CONTEXTS, "FileType": None, "YesOrNo": YES_OR_NO, "YesOnly": YES_ONLY,
             "PDFPageType": PDF_PAGE_TYPES, "Comparator": COMPARATORS, "SoftOrHard": SOFT_OR_HARD,
             "StandardType": STANDARD_TYPES, "StandardStatus": STANDARD_STATUSES,
             "OriginSource": ORIGIN_SOURCES, "ItemGroupClass": ITEM_GROUP_CLASSES,
             "ItemGroupSubClass": ITEM_GROUP_SUB_CLASSES}
XSD_DIVERGENCES = {"DataType": DATA_TYPES, "OriginType": ORIGIN_TYPES, "MethodType": METHOD_TYPES}

# lexical patterns, matched in full
INTEGER = re.compile(r"[+-]?\d+")
POSITIVE_INTEGER = re.compile(r"\+?0*[1-9]\d*")
NON_NEGATIVE_INTEGER = re.compile(r"\+?\d+")
# ISO 8601 date-time as the ODM datetime type spells it, with an optional fraction and zone
DATETIME = re.compile(r"\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])"
                      r"T([01]\d|2[0-3]):[0-5]\d:[0-5]\d(\.\d+)?(Z|[+-]([01]\d|2[0-3]):[0-5]\d)?")
DEFINE_VERSION = re.compile(r"2\.0\.0|2\.1\.(0|[1-9]\d*)")
# odm:sasName -- a SAS name: a letter or underscore, then letters, digits or underscores, 8 at most
SAS_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,7}")
# odm:sasFormat -- a SAS format name, which may start with $ and contain periods, 8 at most
SAS_FORMAT = re.compile(r"(?=.{1,8}$)[A-Za-z_$][A-Za-z0-9_.]*")
# def:leaf/@ID: a letter or underscore, then letters, digits, underscores, hyphens and periods
LEAF_ID = re.compile(r"[A-Za-z_][A-Za-z0-9_.\-]*")

# pattern -> the simple type in the bundled ODM schema with the same pattern facet
XSD_PATTERNS = {"sasName": SAS_NAME, "sasFormat": SAS_FORMAT}
