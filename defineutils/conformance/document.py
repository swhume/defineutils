"""The parsed define.xml and the indexes the conformance checks share.

Document owns the lxml tree and builds each index once, lazily: elements by OID, def:leaf by
ID, ItemRefs by ItemOID, and the ItemGroupDefs that own an ItemDef directly or through a value
list. It is also the one place prefixes are resolved -- attr(), children() and xpath() take
names as they appear in the document ("def:IsNonStandard", "xml:lang") -- and the one place a
finding's path is built.
"""
from functools import cached_property

from lxml import etree

ODM_NS = "http://www.cdisc.org/ns/odm/v1.3"
DEFINE_NS = "http://www.cdisc.org/ns/def/v2.1"
DEFINE_20_NS = "http://www.cdisc.org/ns/def/v2.0"
XLINK_NS = "http://www.w3.org/1999/xlink"
XML_NS = "http://www.w3.org/XML/1998/namespace"

NAMESPACES = {"odm": ODM_NS, "def": DEFINE_NS, "xlink": XLINK_NS, "xml": XML_NS}
# lxml predefines the xml prefix and rejects it in an XPath namespace map
XPATH_NAMESPACES = {prefix: uri for prefix, uri in NAMESPACES.items() if prefix != "xml"}
PREFIXES = {uri: prefix for prefix, uri in NAMESPACES.items()}

# the attribute that identifies an element in a path, when it is not OID
IDENTIFIERS = {"def:leaf": "ID", "ItemRef": "ItemOID", "def:DocumentRef": "leafID",
               "CodeListItem": "CodedValue", "EnumeratedItem": "CodedValue", "Alias": "Name",
               "def:Class": "Name", "def:SubClass": "Name", "TranslatedText": "xml:lang",
               "CodeListRef": "CodeListOID", "def:ValueListRef": "ValueListOID",
               "def:WhereClauseRef": "WhereClauseOID", "RangeCheck": "def:ItemOID"}

NCI_EXT_CODE_ID = "nci:ExtCodeID"


def qualified(name: str) -> str:
    """the Clark-notation name for a prefixed element or attribute name"""
    if ":" in name:
        prefix, local = name.split(":", 1)
        return f"{{{NAMESPACES[prefix]}}}{local}"
    return name


class Document:
    def __init__(self, tree, define_file):
        self.tree = tree
        self.define_file = define_file
        self.root = tree.getroot()
        self._xpaths = {}

    # -- names and namespaces --------------------------------------------------------------

    def display_name(self, elem) -> str:
        """the element's name as written in the document: ItemDef, def:leaf, arm:ResultDisplay"""
        qname = etree.QName(elem)
        if qname.namespace in (None, ODM_NS):
            return qname.localname
        prefix = PREFIXES.get(qname.namespace)
        if prefix is None:
            prefix = next((p for p, uri in elem.nsmap.items() if uri == qname.namespace and p), None)
        return f"{prefix}:{qname.localname}" if prefix else f"{{{qname.namespace}}}{qname.localname}"

    def attr(self, elem, name: str):
        """the attribute's value, or None; name as written: "OID", "def:StandardOID", "xml:lang" """
        return elem.get(qualified(name))

    def children(self, elem, name: str = None) -> list:
        """the element's child elements, all of them or those with the given display name"""
        if name is None:
            return [child for child in elem if isinstance(child.tag, str)]
        tag = qualified(name) if ":" in name else f"{{{ODM_NS}}}{name}"
        return [child for child in elem if child.tag == tag]

    def xpath(self, node, expression: str) -> list:
        """evaluates the XPath, compiled once, with the odm, def and xlink prefixes bound"""
        compiled = self._xpaths.get(expression)
        if compiled is None:
            compiled = self._xpaths[expression] = etree.XPath(expression, namespaces=XPATH_NAMESPACES)
        return compiled(node)

    # -- document-level facts --------------------------------------------------------------

    @property
    def context(self):
        return self.attr(self.root, "def:Context")

    @cached_property
    def metadata_version(self):
        found = self.xpath(self.root, "/odm:ODM/odm:Study/odm:MetaDataVersion")
        return found[0] if found else None

    @property
    def define_version(self):
        mdv = self.metadata_version
        return self.attr(mdv, "def:DefineVersion") if mdv is not None else None

    def uses_define_20(self) -> bool:
        """whether any element or attribute is in the Define-XML 2.0 namespace"""
        return bool(self.root.xpath("boolean(//*[namespace-uri()=$ns] | //@*[namespace-uri()=$ns])",
                                    ns=DEFINE_20_NS))

    # -- indexes ---------------------------------------------------------------------------

    @cached_property
    def by_oid(self) -> dict:
        """every element carrying an OID, by OID"""
        index = {}
        for elem in self.root.iter():
            if isinstance(elem.tag, str) and elem.get("OID") is not None:
                index.setdefault(elem.get("OID"), []).append(elem)
        return index

    @cached_property
    def leaf_by_id(self) -> dict:
        index = {}
        for leaf in self.xpath(self.root, "//def:leaf[@ID]"):
            index.setdefault(leaf.get("ID"), []).append(leaf)
        return index

    def definition(self, oid, name: str):
        """the element of the given display name defining the OID, or None"""
        return next((e for e in self.by_oid.get(oid, []) if self.display_name(e) == name), None)

    def item_def(self, oid):
        return self.definition(oid, "ItemDef")

    def standard(self, oid):
        return self.definition(oid, "def:Standard")

    def value_list(self, oid):
        return self.definition(oid, "def:ValueListDef")

    def leaf(self, leaf_id):
        leaves = self.leaf_by_id.get(leaf_id, [])
        return leaves[0] if leaves else None

    @cached_property
    def _item_refs(self) -> dict:
        index = {}
        for ref in self.xpath(self.root, "//odm:ItemRef[@ItemOID]"):
            index.setdefault(ref.get("ItemOID"), []).append(ref)
        return index

    def item_refs_for(self, item_oid) -> list:
        """every ItemRef naming the ItemDef, under ItemGroupDefs and def:ValueListDefs alike"""
        return self._item_refs.get(item_oid, [])

    @cached_property
    def _items_by_value_list(self) -> dict:
        """ValueListOID -> the ItemDefs whose def:ValueListRef names it"""
        index = {}
        for ref in self.xpath(self.root, "//odm:ItemDef/def:ValueListRef[@ValueListOID]"):
            index.setdefault(ref.get("ValueListOID"), []).append(ref.getparent())
        return index

    def variables_for_value_list(self, value_list_oid) -> list:
        """the ItemDefs whose def:ValueListRef names the def:ValueListDef"""
        return self._items_by_value_list.get(value_list_oid, [])

    def owning_item_groups(self, item_def) -> list:
        """
        the ItemGroupDefs that reference the ItemDef: directly through an ItemRef, or -- for a
        value-level ItemDef -- through the def:ValueListDef that references it and the variable
        ItemDef that references the value list
        """
        groups, pending, seen = [], [item_def], set()
        while pending:
            item = pending.pop()
            if item.get("OID") in seen:
                continue
            seen.add(item.get("OID"))
            for ref in self.item_refs_for(item.get("OID")):
                parent = ref.getparent()
                if parent is None:
                    continue
                if self.display_name(parent) == "ItemGroupDef":
                    if parent not in groups:
                        groups.append(parent)
                elif self.display_name(parent) == "def:ValueListDef":
                    pending.extend(self.variables_for_value_list(parent.get("OID")))
        return groups

    @cached_property
    def annotated_crf_leaf_ids(self) -> set:
        refs = self.xpath(self.root, "//odm:MetaDataVersion/def:AnnotatedCRF/def:DocumentRef[@leafID]")
        return {ref.get("leafID") for ref in refs}

    def archive_href(self, item_group):
        """the xlink:href of the def:leaf the ItemGroupDef's def:ArchiveLocationID names, or None"""
        leaf_id = self.attr(item_group, "def:ArchiveLocationID")
        leaf = self.leaf(leaf_id) if leaf_id else None
        return self.attr(leaf, "xlink:href") if leaf is not None else None

    # -- locations -------------------------------------------------------------------------

    def path(self, elem) -> str:
        """
        the OID-decorated path to the element, MetaDataVersion[MDV.1]/ItemDef[IT.DM.AGE], built the
        way validate builds its locations and extended with one identifier per element kind. The
        constant ODM/Study[...] prefix is dropped here, segment by segment, rather than by
        splitting the finished path on "/", which a Study OID may contain
        """
        segments, node = [], elem
        while node is not None and isinstance(node.tag, str):
            name = self.display_name(node)
            if name not in ("ODM", "Study"):
                identifier = self.attr(node, IDENTIFIERS.get(name, "OID"))
                segments.append(f"{name}[{identifier}]" if identifier else name)
            node = node.getparent()
        return "/".join(reversed(segments)) or "(document root)"

    def line(self, elem):
        return getattr(elem, "sourceline", None)
