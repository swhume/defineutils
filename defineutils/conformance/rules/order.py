"""The expected child order of every Define-XML v2.1 element, derived from the odmlib model.

This is the registry's only use of odmlib, and it is read-only: the model's declared child
order (each class's _elems, in declaration order) is the Define-XML global element ordering
that rule 1 checks. The walk resolves child classes by name against the model module, exactly
as metrics._element_inventory() does and for the same reason -- define_2_1.MetaDataVersion
inherits its ItemGroupDef, ItemDef, CodeList and MethodDef descriptors from ODM 1.3.2, so
following descriptor.element_class would yield the ODM shapes (ItemDef with Question and
MeasurementUnitRef, no def:Origin). odmlib's own loader resolves by name the same way.
"""
from collections import deque

import odmlib.define_2_1.model as define_model

ROOT_ELEMENT = "ODM"


def display_name(cls) -> str:
    """the element name as written in a document: the class name with its def: prefix"""
    namespace = getattr(cls, "namespace", "odm")
    return cls.__name__ if namespace == "odm" else f"{namespace}:{cls.__name__}"


def expected_child_order(model=define_model) -> dict:
    """
    walks the model breadth-first from ODM and returns, for every element the model can hold,
    the display names of its children in declared order
    :param model: the odmlib model module
    :return: dict of parent display name -> list of child display names
    """
    root = getattr(model, ROOT_ELEMENT)
    order, seen = {}, {ROOT_ELEMENT}
    queue = deque([root])
    while queue:
        cls = queue.popleft()
        children = []
        for name, descriptor in cls._elems.items():
            # by name against the model module, the way odmlib's loader does
            child = getattr(model, name, descriptor.element_class)
            children.append(display_name(child))
            if name not in seen:
                seen.add(name)
                queue.append(child)
        order[display_name(cls)] = children
    return order
