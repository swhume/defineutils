"""Conformance rule checking for CDISC Define-XML v2.1.

DefineConformanceChecker loads a define.xml with lxml and evaluates every registered rule
against it: each rule's XPath selects its context nodes and its check yields a Violation per
offence, which becomes a Location (OID-decorated path, source line, detail) under one Finding
per failed rule. Rules that need published CDISC content or the datasets are reported as not
evaluated, and the 13 Submission rules as not applicable when ODM/@def:Context is not
"Submission", so the result accounts for all 225 rules.
"""
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Union

from lxml import etree

from . import report
from .document import Document
from .rules import all_rules, REGISTRY, RULES_SOURCE

ERROR = "error"


class DefineConformanceError(Exception):
    pass


class DefineConformanceLoadError(DefineConformanceError):
    """raised when the check could not be run at all -- the define.xml is missing, not
    well-formed or a Define-XML 2.0 document, or the report could not be written -- as opposed
    to the define.xml failing rules. A subclass of DefineConformanceError so callers that catch
    the parent keep working unchanged"""
    pass


@dataclass(frozen=True)
class Location:
    path: str                   # OID-decorated, e.g. "ItemGroupDef[IG.EC]/ItemRef[IT.EC.EXDOSE]"
    line: Union[int, None]      # source line of the offending element
    detail: str                 # per-occurrence sentence from the check


@dataclass
class Finding:
    rule: str                   # the CDISC rule id, e.g. "73"
    severity: str               # always "error"; kept so the reports share a finding shape
    element: str                # e.g. "ItemRef"
    attribute: Union[str, None]     # e.g. "MethodOID"
    source_type: str            # "Schema" | "Specification", from the spreadsheet
    message: str                # the CDISC rule text
    cdisc_message: str          # the CDISC message template, as published
    locations: list = field(default_factory=list)


@dataclass
class ConformanceResult:
    define_file: str
    define_version: Union[str, None]    # MetaDataVersion/@def:DefineVersion as written, e.g. "2.1.9"
    context: Union[str, None]           # ODM/@def:Context as written
    rules_source: str
    rule_count: int                     # every registered rule, 225
    findings: list                      # Finding per failed rule, ascending rule id
    passed: list                        # rule ids evaluated with no violation
    not_applicable: list                # rule ids skipped because of ODM/@def:Context
    not_evaluated: list                 # (rule id, requirement) pairs
    skipped: list = field(default_factory=list)     # rule ids left out by a rules / skip_rules selection

    @property
    def errors(self) -> list:
        return [f for f in self.findings if f.severity == ERROR]

    @property
    def has_errors(self) -> bool:
        return any(f.severity == ERROR for f in self.findings)

    @property
    def failed_count(self) -> int:
        return len(self.findings)

    @property
    def occurrence_count(self) -> int:
        return sum(len(f.locations) for f in self.findings)

    @property
    def evaluated_count(self) -> int:
        return len(self.findings) + len(self.passed)


class DefineConformanceChecker:
    def __init__(self, define_file: Path, rules: Iterable[str] = None, skip_rules: Iterable[str] = None):
        """
        :param define_file: the define.xml to check
        :param rules: rule ids to run; every other rule is reported as skipped
        :param skip_rules: rule ids to leave out
        """
        self.define_file = Path(define_file)
        self._result = None
        self.rules = self._rule_ids(rules)
        self.skip_rules = self._rule_ids(skip_rules) or set()
        if not self.define_file.is_file():
            raise DefineConformanceLoadError(f"File {self.define_file} not found.")

    @classmethod
    def all_rules(cls) -> list:
        """the registry: every rule with its CDISC metadata, in ascending id order"""
        return all_rules()

    def check(self) -> ConformanceResult:
        """
        loads the define.xml and evaluates every rule; the result is cached so the report
        methods and the CLI exit code do not re-parse the file
        :return: ConformanceResult
        """
        if self._result is not None:
            return self._result
        doc = self._load()
        findings, passed, not_applicable, not_evaluated, skipped = [], [], [], [], []
        for rule in all_rules():
            if (self.rules is not None and rule.id not in self.rules) or rule.id in self.skip_rules:
                skipped.append(rule.id)
            elif rule.requires:
                not_evaluated.append((rule.id, rule.requires))
            elif rule.context and doc.context != rule.context:
                not_applicable.append(rule.id)
            else:
                locations = [Location(path=doc.path(v.node), line=doc.line(v.node), detail=v.detail)
                             for node in doc.xpath(doc.root, rule.select) for v in rule.check(doc, node)]
                if locations:
                    findings.append(Finding(rule=rule.id, severity=ERROR, element=rule.element,
                                            attribute=rule.attribute, source_type=rule.source_type,
                                            message=rule.text, cdisc_message=rule.cdisc_message,
                                            locations=locations))
                else:
                    passed.append(rule.id)
        self._result = ConformanceResult(
            define_file=str(self.define_file), define_version=doc.define_version, context=doc.context,
            rules_source=RULES_SOURCE, rule_count=len(REGISTRY), findings=findings, passed=passed,
            not_applicable=not_applicable, not_evaluated=not_evaluated, skipped=skipped)
        return self._result

    def check_to_string(self, max_locations: int = 5) -> str:
        """
        checks and returns the formatted text listing
        :param max_locations: max example locations shown per finding (0 shows all)
        :return: string
        """
        return report.render_text(self.check(), max_locations)

    def check_to_file(self, out_file: Path, max_locations: int = 5, as_json: bool = False) -> None:
        """
        checks and writes the listing (text or JSON) to out_file
        :param out_file: Path to the file to save the report
        :param max_locations: max example locations shown per finding (0 shows all)
        :param as_json: when True, writes the JSON report instead of the text listing
        :return: None
        """
        if as_json:
            listing = self.check_to_json()
        else:
            listing = self.check_to_string(max_locations=max_locations)
        try:
            with open(out_file, "w", encoding="utf-8") as f:
                f.write(listing + "\n")
        except FileNotFoundError as e:
            raise DefineConformanceLoadError(f"File {out_file} not found.\n{e}")
        except PermissionError as e:
            # Windows raises PermissionError, not IsADirectoryError, for a folder; os.path.isdir never raises,
            # where Path.is_dir() can when a parent folder is unreadable
            if os.path.isdir(out_file):
                raise DefineConformanceLoadError(f"Error attempting to write to a directory {out_file}.")
            raise DefineConformanceLoadError(f"Permission error attempting to write to {out_file}.\n{e}")
        except IsADirectoryError as e:
            raise DefineConformanceLoadError(f"Error attempting to write to a directory {out_file}.\n{e}")

    def check_to_console(self, max_locations: int = 5) -> None:
        """
        checks and prints the formatted text listing to stdout
        :param max_locations: max example locations shown per finding (0 shows all)
        :return: None
        """
        print(self.check_to_string(max_locations=max_locations))

    def check_to_json(self, indent: int = 2) -> str:
        """
        checks and returns the results as a JSON string; every location is included even when
        the text listing truncates them
        :param indent: JSON indent
        :return: string
        """
        return report.render_json(self.check(), indent)

    @staticmethod
    def _rule_ids(ids: Iterable[str]):
        """the ids as a set of strings, or None; an id the registry does not know is an error"""
        if ids is None:
            return None
        ids = {str(i).strip() for i in ids if str(i).strip()}
        unknown = ids - set(REGISTRY)
        if unknown:
            raise DefineConformanceError(f"Unknown rule id(s): {', '.join(sorted(unknown))}. "
                                         f"Run defineconform --list-rules to see the rule ids.")
        return ids

    def _load(self) -> Document:
        """
        parses the define.xml with lxml, comments stripped, exactly as validate does, so the two
        tools agree on line numbers and child positions
        :return: Document
        """
        try:
            tree = etree.parse(str(self.define_file), etree.XMLParser(remove_comments=True))
        except etree.XMLSyntaxError as e:
            raise DefineConformanceLoadError(f"Define-XML file is not well-formed XML: {self.define_file}.\n{e}")
        except OSError as e:
            raise DefineConformanceLoadError(f"Define-XML file not found: {self.define_file}.\n{e}")
        doc = Document(tree, self.define_file)
        if doc.uses_define_20():
            raise DefineConformanceLoadError(f"{self.define_file} is a Define-XML 2.0 document; only Define-XML "
                                             f"2.1 is supported.")
        return doc
