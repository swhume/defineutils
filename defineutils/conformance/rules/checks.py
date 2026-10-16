"""The check factories the declarative rules are built from.

Every factory returns a check: callable(doc, node) yielding a Violation for each offence on the
context node. Attribute and element names are written as they appear in the document
("def:IsNonStandard", "xml:lang", "def:leaf"); Document.attr() and Document.children() resolve
the prefixes, so no factory sees a namespace URI.
"""
import re
from collections import Counter

from . import Violation
from .order import expected_child_order

ABSENT = "(absent)"


def _values(values) -> str:
    return ", ".join(f'"{v}"' for v in sorted(values))


def required_attr(attribute: str):
    """the attribute is present and not empty"""
    def check(doc, node):
        if not doc.attr(node, attribute):
            yield Violation(node, f"@{attribute} is missing")
    return check


def absent_attr(attribute: str):
    def check(doc, node):
        if doc.attr(node, attribute) is not None:
            yield Violation(node, f"@{attribute} is present")
    return check


def allowed_values(attribute: str, values):
    """when present, the attribute's value is one of the values; presence is another rule's job"""
    allowed = frozenset(values)

    def check(doc, node):
        value = doc.attr(node, attribute)
        if value is not None and value not in allowed:
            expected = f'"{next(iter(allowed))}"' if len(allowed) == 1 else f"one of {_values(allowed)}"
            yield Violation(node, f'@{attribute}="{value}" is not {expected}')
    return check


def attr_equals(attribute: str, value: str):
    return allowed_values(attribute, {value})


def attr_matches(attribute: str, pattern: re.Pattern, description: str):
    """when present, the attribute's whole value matches the pattern"""
    def check(doc, node):
        value = doc.attr(node, attribute)
        if value is not None and pattern.fullmatch(value) is None:
            yield Violation(node, f'@{attribute}="{value}" is not {description}')
    return check


def required_child(name: str, minimum: int = 1):
    def check(doc, node):
        count = len(doc.children(node, name))
        if count < minimum:
            if minimum == 1:
                yield Violation(node, f"has no {name} child element")
            else:
                yield Violation(node, f"has {count} {name} child elements; at least {minimum} are required")
    return check


def max_one_child(name: str):
    def check(doc, node):
        count = len(doc.children(node, name))
        if count > 1:
            yield Violation(node, f"has {count} {name} child elements; at most one is allowed")
    return check


def forbidden_child(name: str, because: str):
    def check(doc, node):
        if doc.children(node, name):
            yield Violation(node, f"has a {name} child element, but {because}")
    return check


def attrs_equal(attribute: str, other: str):
    """when both are present, the two attributes have the same value"""
    def check(doc, node):
        value, expected = doc.attr(node, attribute), doc.attr(node, other)
        if value is not None and expected is not None and value != expected:
            yield Violation(node, f'@{attribute}="{value}" differs from @{other}="{expected}"')
    return check


def present_when(attribute: str, predicate, because: str):
    """the attribute is required when predicate(doc, node) holds"""
    def check(doc, node):
        if predicate(doc, node) and not doc.attr(node, attribute):
            yield Violation(node, f"@{attribute} is missing, but {because}")
    return check


def absent_when(attribute: str, predicate, because: str):
    """the attribute must not be present when predicate(doc, node) holds"""
    def check(doc, node):
        if predicate(doc, node) and doc.attr(node, attribute) is not None:
            yield Violation(node, f"@{attribute} is present, but {because}")
    return check


def value_when(attribute: str, value: str, predicate, because: str):
    """the attribute must be present with the given value when predicate(doc, node) holds"""
    def check(doc, node):
        if predicate(doc, node):
            actual = doc.attr(node, attribute)
            if actual is None:
                yield Violation(node, f'@{attribute} is missing and must be "{value}", because {because}')
            elif actual != value:
                yield Violation(node, f'@{attribute}="{actual}" must be "{value}", because {because}')
    return check


def child_present_when(name: str, predicate, because: str):
    """the child element is required when predicate(doc, node) holds"""
    def check(doc, node):
        if predicate(doc, node) and not doc.children(node, name):
            yield Violation(node, f"has no {name} child element, but {because}")
    return check


def unique_among_siblings(child: str, attribute: str, absent_is_value: bool = False):
    """
    among the context node's children of the given name, the attribute's values are unique; one
    violation per child sharing a value. With absent_is_value, children without the attribute
    count as sharing one value -- two TranslatedText without xml:lang under one Description --
    while without it they are ignored, as ItemRefs without a KeySequence must be
    """
    def check(doc, node):
        children = doc.children(node, child)
        counts = Counter(doc.attr(c, attribute) for c in children)
        for c in children:
            value = doc.attr(c, attribute)
            if value is None and not absent_is_value:
                continue
            if counts[value] > 1:
                shared = f'@{attribute}="{value}"' if value is not None else f"no @{attribute}"
                yield Violation(c, f"{shared} is shared by {counts[value]} {child} elements under the same "
                                   f"{doc.display_name(node)}")
    return check


def all_or_none(child: str, attribute: str):
    """either every child of the given name carries the attribute, or none does"""
    def check(doc, node):
        children = doc.children(node, child)
        with_attribute = [c for c in children if doc.attr(c, attribute) is not None]
        if 0 < len(with_attribute) < len(children):
            for c in children:
                if doc.attr(c, attribute) is None:
                    yield Violation(c, f"@{attribute} is missing, but {len(with_attribute)} of the "
                                       f"{len(children)} {child} elements under this "
                                       f"{doc.display_name(node)} have one")
    return check


def unique_in_document(select: str, attribute: str):
    """across the elements the XPath selects, the attribute's values are unique; one violation per
    element sharing a value. Run from the document root"""
    def check(doc, node):
        elements = doc.xpath(doc.root, select)
        counts = Counter(doc.attr(e, attribute) for e in elements)
        for e in elements:
            value = doc.attr(e, attribute)
            if value is not None and counts[value] > 1:
                yield Violation(e, f'@{attribute}="{value}" is defined {counts[value]} times')
    return check


def at_most_in_document(select: str, maximum: int, description: str):
    """the XPath selects at most the given number of elements; run from the document root"""
    def check(doc, node):
        count = len(doc.xpath(doc.root, select))
        if count > maximum:
            yield Violation(node, f"the document has {count} {description}; at most {maximum} allowed")
    return check


def ref_to(attribute: str, target: str, where=None, because: str = None, scope: str = None):
    """
    when present, the attribute resolves to an element of the target kind. OID references go
    through the document OID index; leafID and def:ArchiveLocationID resolve through def:leaf/@ID.
    where(doc, target_element) adds a condition on the target, explained by because; scope="self"
    accepts only a target inside the context node
    """
    by_id = attribute in ("leafID", "def:ArchiveLocationID")

    def check(doc, node):
        value = doc.attr(node, attribute)
        if not value:
            return
        candidates = doc.leaf_by_id.get(value, []) if by_id else doc.by_oid.get(value, [])
        if scope == "self":
            candidates = [c for c in candidates if node in c.iterancestors()]
        if not candidates:
            inside = f" inside this {doc.display_name(node)}" if scope == "self" else ""
            yield Violation(node, f'@{attribute}="{value}" references no {target}{inside}')
            return
        matches = [c for c in candidates if doc.display_name(c) == target]
        if not matches:
            actual = doc.display_name(candidates[0])
            yield Violation(node, f'@{attribute}="{value}" is defined by {actual}, not {target}')
            return
        if where is not None and not any(where(doc, m) for m in matches):
            yield Violation(node, f'@{attribute}="{value}" resolves to a {target}, but {because}')
    return check


def root_is(name: str):
    def check(doc, node):
        actual = doc.display_name(node)
        if actual != name:
            yield Violation(node, f"the root element is {actual}, not {name}")
    return check


def element_order():
    """
    the context node's children follow the model's declared order: each child's position in the
    expected order is not lower than the highest already seen. Children the order table does not
    know (ARM, extensions) are ignored, and so are parents it does not know
    """
    order = expected_child_order()

    def check(doc, node):
        parent = doc.display_name(node)
        expected = order.get(parent)
        if not expected:
            return
        rank = {name: position for position, name in enumerate(expected)}
        highest, highest_name = -1, None
        for child in doc.children(node):
            name = doc.display_name(child)
            position = rank.get(name)
            if position is None:
                continue
            if position < highest:
                yield Violation(child, f"{name} comes after {highest_name}; the order under {parent} is "
                                       + ", ".join(expected))
            else:
                highest, highest_name = position, name
    return check


def any_of(*checks):
    """the violations of every check, so one rule can combine two"""
    def check(doc, node):
        for c in checks:
            yield from c(doc, node)
    return check
