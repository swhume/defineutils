"""Rules on the shared definitions: MethodDef and FormalExpression, def:CommentDef, def:leaf and
def:title."""
from . import rule
from . import values as V
from .checks import (allowed_values, attr_matches, max_one_child, required_attr, required_child,
                     unique_in_document)

METHOD = "//odm:MethodDef"
COMMENT = "//def:CommentDef"
LEAF = "//def:leaf"

# -- MethodDef ---------------------------------------------------------------------------------

rule("56", "Description", None, METHOD, required_child("Description"))
rule("205", "Description", None, METHOD, max_one_child("Description"))
rule("206", "MethodDef", "OID", METHOD, required_attr("OID"))
rule("207", "MethodDef", "Name", METHOD, required_attr("Name"))
rule("208", "MethodDef", "Type", METHOD, required_attr("Type"))
rule("209", "MethodDef", "Type", METHOD, allowed_values("Type", V.METHOD_TYPES))
rule("210", "Description", None, METHOD, required_child("Description"))
rule("221", "FormalExpression", "Context", "//odm:FormalExpression", required_attr("Context"))

# -- def:CommentDef ----------------------------------------------------------------------------

rule("212", "def:CommentDef", "OID", COMMENT, required_attr("OID"))
rule("213", "def:CommentDef", "OID", "/*", unique_in_document(COMMENT, "OID"))
rule("214", "Description", None, COMMENT, required_child("Description"))
rule("215", "Description", None, COMMENT, max_one_child("Description"))

# -- def:leaf ----------------------------------------------------------------------------------

rule("216", "def:leaf", "ID", "/*", unique_in_document(LEAF, "ID"))
rule("218", "def:title", None, LEAF, required_child("def:title"))
rule("219", "def:title", None, LEAF, max_one_child("def:title"))
rule("248", "def:leaf", "xlink:href", LEAF, required_attr("xlink:href"))
rule("259", "def:leaf", "ID", LEAF,
     attr_matches("ID", V.LEAF_ID, "a letter or underscore followed by letters, digits, underscores, hyphens "
                                   "and periods"))
