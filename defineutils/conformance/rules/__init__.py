"""The Define-XML v2.1 conformance rule registry.

A rule is registered with rule(): its id, the element and attribute it is about, an XPath
selecting the context nodes, and a check that yields a Violation per offence. The CDISC text,
message, source type and version applicability are joined by id from define21_rules.json, the
bundled export of the CDISC spreadsheet, so a rule id that is not in the JSON -- or is
registered twice -- fails at import, and the registry cannot drift from the published rules.

The rule modules are imported at the bottom of this file, statically: PyInstaller's analysis
finds them that way, with no hiddenimports, and the JSON is read through Path(__file__), which
the frozen build resolves inside its _internal folder.
"""
import json
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Union

METADATA_FILE = Path(__file__).parent / "define21_rules.json"

SUBMISSION = "Submission"

# what a rule that cannot be decided from the document needs
NEEDS_CT = "ct"
NEEDS_IG = "ig"
NEEDS_DATASETS = "datasets"
REQUIREMENT_LABELS = {NEEDS_CT: "CDISC controlled terminology",
                      NEEDS_IG: "implementation-guide metadata",
                      NEEDS_DATASETS: "the datasets"}


@dataclass(frozen=True)
class Violation:
    node: object                # the offending lxml element: the finding's path and line
    detail: str                 # one per-occurrence sentence from the check


Check = Callable[[object, object], Iterable[Violation]]


@dataclass(frozen=True)
class Rule:
    id: str                             # the spreadsheet's Rule Identifier, e.g. "110"
    element: str                        # display name, e.g. "ItemGroupDef", "def:PDFPageRef"
    attribute: Union[str, None]         # "SASDatasetName", "def:IsNonStandard", "xml:lang", None
    select: str                         # XPath 1.0 selecting the context nodes
    check: Check
    context: Union[str, None] = None    # "Submission": evaluated only when ODM/@def:Context matches
    requires: Union[str, None] = None   # NEEDS_CT | NEEDS_IG | NEEDS_DATASETS: registered, never run
    meta: dict = field(default_factory=dict, compare=False)   # the CDISC record from the JSON

    @property
    def text(self) -> str:
        """the CDISC plain-text rule, the finding's message"""
        return self.meta["plain_text"]

    @property
    def cdisc_rule(self) -> str:
        return self.meta["rule"]

    @property
    def cdisc_message(self) -> str:
        return self.meta["message"]

    @property
    def source_type(self) -> str:
        return self.meta["source_type"]

    @property
    def versions(self) -> str:
        return self.meta["versions"]

    @property
    def paths(self) -> list:
        return self.meta["paths"]

    @property
    def subject(self) -> str:
        """element/@attribute, as the listings show the rule"""
        return f"{self.element}/@{self.attribute}" if self.attribute else self.element

    @property
    def status(self) -> str:
        """document | submission | needs ct|ig|datasets: how the rule is evaluated"""
        if self.requires:
            return f"needs {self.requires}"
        return "submission" if self.context == SUBMISSION else "document"

    @property
    def sort_key(self) -> int:
        return int(self.id)


class RegistryError(Exception):
    """a registration that does not match the bundled rule metadata; raised at import"""


def load_metadata() -> dict:
    with open(METADATA_FILE, encoding="utf-8") as f:
        return json.load(f)


_metadata = load_metadata()
RULES_SOURCE = _metadata["source"]
METADATA = {record["id"]: record for record in _metadata["rules"]}

REGISTRY = {}


def rule(id: str, element: str, attribute: Union[str, None], select: str, check: Check = None, *,
         context: str = None, requires: str = None):
    """
    registers a rule; works as a plain call with the check, or as a decorator on a check function
    :param id: the CDISC rule identifier, as a string
    :param element: the element the rule is about, as displayed ("def:leaf")
    :param attribute: the attribute the rule is about, as written in the document, or None
    :param select: XPath 1.0 selecting the context nodes the check runs on
    :param check: callable(doc, node) yielding Violations
    :param context: SUBMISSION when the rule applies only to ODM/@def:Context="Submission"
    :param requires: NEEDS_CT | NEEDS_IG | NEEDS_DATASETS when the rule cannot be run
    :return: the Rule, or a decorator returning the check function
    """
    def register(check_function: Check):
        if id in REGISTRY:
            raise RegistryError(f"rule {id} is registered twice")
        if id not in METADATA:
            raise RegistryError(f"rule {id} is not in {METADATA_FILE.name}")
        if requires is not None and requires not in REQUIREMENT_LABELS:
            raise RegistryError(f"rule {id}: unknown requirement {requires!r}")
        REGISTRY[id] = Rule(id=id, element=element, attribute=attribute, select=select,
                            check=check_function, context=context, requires=requires, meta=METADATA[id])
        return check_function

    if check is None:
        return register
    register(check)
    return REGISTRY[id]


def not_evaluated(doc, node):
    """the check of a rule registered with requires=...; the evaluator never calls it"""
    raise RegistryError("a rule that needs external content was evaluated")


def all_rules() -> list:
    """every registered rule in ascending numeric id order"""
    return sorted(REGISTRY.values(), key=lambda r: r.sort_key)


def get_rule(id: str) -> Rule:
    return REGISTRY[id]


# the rule modules register themselves on import; keep these static for PyInstaller's analysis
from . import structure, datasets, variables, codelists, definitions  # noqa: E402,F401

__all__ = ["Rule", "Violation", "Check", "rule", "not_evaluated", "all_rules", "get_rule",
           "REGISTRY", "METADATA", "RULES_SOURCE", "SUBMISSION", "NEEDS_CT", "NEEDS_IG",
           "NEEDS_DATASETS", "REQUIREMENT_LABELS", "RegistryError", "load_metadata"]
