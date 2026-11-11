"""Extra checks: defineutils' extensions to the CDISC rules.

Each tests something no CDISC Define-XML v2.1 conformance rule does, but that a define.xml
should still meet, and names its basis: the Define-XML specification, a Pinnacle 21 rule, or
the Define-XML 2.0 or ODM 1.3 Schematron. They are reported apart from the CDISC rules.
"""
from . import extra_rule
from .checks import required_child, unique_among_siblings, unique_in_document

GROUP = "//odm:ItemGroupDef"
VALUE_LIST = "//def:ValueListDef"

# Name rather than SASDatasetName, which P21 checks: rule 110 makes the two equal, and Name is
# present outside a submission too
extra_rule("X1", "ItemGroupDef", "Name", "/*", unique_in_document(GROUP, "Name"),
           text="Name attribute value must be unique within the set of ItemGroupDef elements.",
           basis="P21 DD0051 (SASDatasetName); Define-XML 2.0 Schematron rule #26.1")
# the datasets only, as P21's OD0041 describes it: "unique within a single ItemGroupDef"
extra_rule("X2", "ItemRef", "ItemOID", GROUP, unique_among_siblings("ItemRef", "ItemOID"),
           text="An ItemGroupDef must not reference the same ItemDef more than once: the ItemOID attribute "
                "value must be unique within its ItemRef elements.",
           basis="P21 OD0041; ODM 1.3 Schematron")
extra_rule("X3", "ItemRef", "OrderNumber", f"{GROUP} | {VALUE_LIST}", unique_among_siblings("ItemRef", "OrderNumber"),
           text="OrderNumber attribute values must be unique within the ItemRef elements of an ItemGroupDef or "
                "def:ValueListDef.",
           basis="P21 OD0042; ODM 1.3 Schematron")
extra_rule("X4", "Description", None, "//def:Origin[@Type='Predecessor']", required_child("Description"),
           text='A def:Origin with Type="Predecessor" must have a Description child element identifying the '
                "dataset and variable that is copied.",
           basis="Define-XML 2.1 section 4.3.2; P21 DD0061; Define-XML 2.0 Schematron rule #40")
