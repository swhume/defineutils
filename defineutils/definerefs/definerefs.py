"""OID reference/definition integrity checking for CDISC Define-XML v2.1.

odmlib is the authority on *what* to check: create_oid_checker("define_2_1") introspects the
model classes and supplies the ref/def mappings and skip lists, so this module never
hand-codes a reference table. The traversal, however, is done here rather than via
verify_oids(): odmlib raises on the first violation and collects references as sets of OID
values, so a report built on it could name neither every problem nor where each one lives.
"""
from contextlib import nullcontext
from dataclasses import dataclass, field
from pathlib import Path
from typing import Union

import odmlib
import odmlib.define_loader as DL
import odmlib.loader as LD
from odmlib import create_oid_checker
from odmlib import permissive as permissive_mode
from odmlib.odm_element import ODMElement

from . import report

# instance attributes odmlib uses for its own bookkeeping; not document content
SKIP_KEYS = {"_fields", "_attr_ns", "_elems", "_attrs"}
# Define-XML document-leaf ref/def pairs. odmlib 0.2.0 models leaf/@ID as a plain attribute,
# so these references are invisible to the introspected mappings; supplemented via setdefault
# so a later odmlib that maps them natively wins and nothing is reported twice.
ID_REF_DEF = {"leafID": "leaf", "ArchiveLocationID": "leaf"}

UNDEFINED_REFERENCE = "undefined_reference"
UNDEFINED_DOCUMENT_REFERENCE = "undefined_document_reference"
TYPE_MISMATCH = "type_mismatch"
DUPLICATE_OID = "duplicate_oid"
ORPHAN_DEFINITION = "orphan_definition"
ORPHAN_DOCUMENT_LEAF = "orphan_document_leaf"

ERROR = "error"
WARNING = "warning"


class DefineRefCheckError(Exception):
    pass


@dataclass(frozen=True)
class Location:
    element: str            # class name holding the reference/definition, e.g. "ItemRef"
    path: str               # "MetaDataVersion[MDV.x]/ItemGroupDef[IG.DM]"


@dataclass
class Finding:
    check: str              # "undefined_reference" | "type_mismatch" | "duplicate_oid" | ...
    severity: str           # "error" | "warning"
    oid: str
    attribute: Union[str, None]         # reference attribute, e.g. "ItemOID" (None for defs)
    expected_element: Union[str, None]
    actual_element: Union[str, None]
    message: str            # self-contained sentence, used in the JSON report
    detail: str             # short form for the text listing, whose heading names oid/attribute
    locations: list = field(default_factory=list)


@dataclass
class RefCheckResult:
    define_file: str
    model_package: str
    odmlib_version: str
    permissive: bool
    definition_count: int
    reference_count: int
    findings: list
    checked_attributes: list
    skipped_attributes: list
    unmapped_attributes: list

    @property
    def errors(self) -> list:
        return [f for f in self.findings if f.severity == ERROR]

    @property
    def warnings(self) -> list:
        return [f for f in self.findings if f.severity == WARNING]

    @property
    def has_errors(self) -> bool:
        return any(f.severity == ERROR for f in self.findings)


class DefineRefChecker:
    def __init__(self, define_xml_file: Path, model_package: str = "define_2_1",
                 permissive: bool = False) -> None:
        self.define = Path(define_xml_file)
        self.model_package = model_package
        self.permissive = permissive
        self._result = None
        self._does_define_file_exist()

    def check(self) -> RefCheckResult:
        """
        loads the define.xml and runs every ref/def check; the result is cached so the
        report methods and the CLI exit code do not re-parse the file
        :return: RefCheckResult
        """
        if self._result is not None:
            return self._result
        checker = create_oid_checker(self.model_package)
        ref_def = self._ref_def_map(checker)
        id_defs = self._id_def_classes(ref_def, checker)
        # the load and the traversal share the permissive context: reading an unset required
        # attribute outside it raises, even though the __dict__ traversal avoids descriptors
        with permissive_mode() if self.permissive else nullcontext():
            root = self._load_define()
            defs, refs = self._collect(root, ref_def, id_defs)
        findings = self._evaluate(defs, refs, checker, ref_def, id_defs)
        present = {r["attr"] for r in refs}
        self._result = RefCheckResult(
            define_file=str(self.define),
            model_package=self.model_package,
            odmlib_version=getattr(odmlib, "__version__", "unknown"),
            permissive=self.permissive,
            definition_count=len(defs),
            reference_count=len(refs),
            findings=findings,
            checked_attributes=sorted((a for a in present
                                       if a in ref_def and a not in checker.skip_attr),
                                      key=str.lower),
            skipped_attributes=list(checker.skip_attr),
            unmapped_attributes=sorted((a for a in present
                                        if a not in ref_def and a not in checker.skip_attr),
                                       key=str.lower),
        )
        return self._result

    def check_to_string(self, errors_only: bool = False, max_locations: int = 5) -> str:
        """
        runs the checks and returns the formatted text listing
        :param errors_only: when True, orphan definition warnings are suppressed
        :param max_locations: max example locations shown per finding (0 shows all)
        :return: string
        """
        return report.render_text(self.check(), errors_only, max_locations)

    def check_to_file(self, out_file: Path, errors_only: bool = False, max_locations: int = 5,
                      as_json: bool = False) -> None:
        """
        runs the checks and writes the listing (text or JSON) to out_file
        :param out_file: Path to the file to save the report
        :param errors_only: when True, orphan definition warnings are suppressed
        :param max_locations: max example locations shown per finding (0 shows all)
        :param as_json: when True, writes the JSON report instead of the text listing
        :return: None
        """
        if as_json:
            listing = self.check_to_json(errors_only=errors_only)
        else:
            listing = self.check_to_string(errors_only=errors_only, max_locations=max_locations)
        try:
            with open(out_file, "w", encoding="utf-8") as f:
                f.write(listing + "\n")
        except FileNotFoundError as e:
            raise DefineRefCheckError(f"File {out_file} not found.\n{e}")
        except PermissionError as e:
            raise DefineRefCheckError(f"Permission error attempting to write to {out_file}.\n{e}")
        except IsADirectoryError as e:
            raise DefineRefCheckError(f"Error attempting to write to a directory {out_file}.\n{e}")

    def check_to_console(self, errors_only: bool = False, max_locations: int = 5) -> None:
        """
        runs the checks and prints the formatted text listing to stdout
        :param errors_only: when True, orphan definition warnings are suppressed
        :param max_locations: max example locations shown per finding (0 shows all)
        :return: None
        """
        print(self.check_to_string(errors_only=errors_only, max_locations=max_locations))

    def check_to_json(self, errors_only: bool = False, indent: int = 2) -> str:
        """
        runs the checks and returns the results as a JSON string; every location is included
        even when the text listing truncates them
        :param errors_only: when True, orphan definition warnings are suppressed
        :param indent: JSON indent
        :return: string
        """
        return report.render_json(self.check(), errors_only, indent)

    def _load_define(self):
        """
        loads the define.xml into the odmlib model and returns the root ODM object. odmlib
        raises a mix of exception types here -- ParseError on malformed XML, AttributeError on
        an unexpected root element, OdmlibError subclasses on non-conformant content -- so the
        load boundary catches Exception and re-raises DefineRefCheckError with guidance
        :return: the root ODM object
        """
        try:
            return self._open_define()
        except Exception as e:
            raise DefineRefCheckError(self._load_error_message(e))

    def _open_define(self):
        """
        opens the define.xml with the odmlib Define-XML loader and builds the model objects
        :return: the root ODM object
        """
        loader = LD.ODMLoader(DL.XMLDefineLoader(model_package=self.model_package))
        loader.open_odm_document(str(self.define))
        return loader.root()

    def _permissive_would_load(self) -> bool:
        """
        re-attempts a failed load inside the permissive context to find out whether suggesting
        --permissive is worth the user's time. Asking the file rather than testing the
        exception type keeps the guidance correct across odmlib releases: 0.2.0 raises a
        ParseError on malformed XML where a later odmlib raises OdmlibParsingError, and neither
        is rescued by permissive mode
        :return: True when the file loads in permissive mode
        """
        try:
            with permissive_mode():
                self._open_define()
            return True
        except Exception:
            return False

    def _load_error_message(self, e: Exception) -> str:
        """
        builds the load failure message that recommends the validate utility; the --permissive
        hint is added only when a permissive load of this file actually succeeds
        :param e: the exception raised by the odmlib load
        :return: string
        """
        model = report.model_label(self.model_package)
        message = (f"Unable to load {self.define} into the {model} model.\n"
                   f"  {type(e).__name__}: {e}\n\n"
                   f"No reference/definition checks were run. This file must parse as conformant\n"
                   f"{model} before its OID references can be checked. Run the validate\n"
                   f"utility to identify the problems:\n\n"
                   f"    python -m defineutils.validate -d {self.define}\n\n"
                   f"Then re-run this check.")
        if not self.permissive and self._permissive_would_load():
            message += (" To attempt a best-effort check of the file as-is,\n"
                        "add --permissive.")
        return message

    def _ref_def_map(self, checker) -> dict:
        """
        returns odmlib's introspected reference attribute to definition class mapping,
        supplemented with the Define-XML document-leaf pairs odmlib 0.2.0 does not model
        :param checker: the odmlib DynamicOIDRef checker
        :return: dict of reference attribute name to definition class name
        """
        ref_def = dict(checker.ref_def)
        for attr, def_class in ID_REF_DEF.items():
            if def_class in checker.model_classes:
                ref_def.setdefault(attr, def_class)
        return ref_def

    @staticmethod
    def _id_def_classes(ref_def: dict, checker) -> set:
        """
        returns the definition classes that identify themselves with ID rather than OID (in
        Define-XML v2.1, def:leaf). Derived from the model classes so it stays correct if a
        later odmlib maps the leaf ref/def pairs itself
        :param ref_def: reference attribute to definition class mapping
        :param checker: the odmlib DynamicOIDRef checker
        :return: set of class names
        """
        id_defs = set()
        for def_class in set(ref_def.values()):
            attrs = getattr(checker.model_classes.get(def_class), "_attrs", {})
            if "OID" not in attrs and "ID" in attrs:
                id_defs.add(def_class)
        return id_defs

    def _collect(self, root, ref_def: dict, id_defs: set):
        """
        walks the loaded object tree once, collecting every OID definition and every
        reference occurrence with its element class name and path
        :param root: the root ODM object
        :param ref_def: reference attribute to definition class mapping
        :param id_defs: definition classes identified by ID rather than OID
        :return: tuple of (definitions, references), each a list of dicts
        """
        defs, refs = [], []
        self._walk(root, "", 1, defs, refs, ref_def, id_defs)
        return defs, refs

    def _walk(self, elem, parent_path: str, ordinal: int, defs: list, refs: list,
              ref_def: dict, id_defs: set) -> None:
        """
        recursive worker for _collect. Reads element.__dict__ rather than accessing attributes
        through the odmlib descriptors -- the same technique odmlib's own _init_oid_check uses
        -- so an unset attribute on a permissively loaded file is simply absent
        :param elem: the odmlib element to walk
        :param parent_path: path of the element that contains elem
        :param ordinal: 1-based position of elem among its same-class siblings
        :return: None
        """
        cls = type(elem).__name__
        content = {k: v for k, v in elem.__dict__.items() if k not in SKIP_KEYS}
        own = content.get("OID") or (content.get("ID") if cls in id_defs else None)
        path = f"{parent_path}/{cls}[{own}]" if own else f"{parent_path}/{cls}"
        counts = {}

        def visit(child):
            name = type(child).__name__
            counts[name] = counts.get(name, 0) + 1
            self._walk(child, path, counts[name], defs, refs, ref_def, id_defs)

        for attr, obj in content.items():
            if isinstance(obj, ODMElement):
                visit(obj)
            elif isinstance(obj, list):
                for child in obj:
                    if isinstance(child, ODMElement):
                        visit(child)
            elif not isinstance(obj, str):
                continue
            elif attr == "OID" or (attr == "ID" and cls in id_defs):
                defs.append({"oid": obj, "elem": cls, "path": parent_path, "ordinal": ordinal})
            elif "OID" in attr or attr in ref_def:
                # an element that carries its own OID names itself in the location, so the
                # reference is recorded against the path that identifies it
                refs.append({"oid": obj, "attr": attr, "elem": cls,
                             "path": path if own else parent_path})

    def _evaluate(self, defs: list, refs: list, checker, ref_def: dict, id_defs: set) -> list:
        """
        turns the collected definitions and references into findings: duplicate OIDs, dangling
        references, type mismatches and orphan definitions. Findings are grouped by
        (check, oid, attribute) with every occurrence appended as a Location
        :return: list of Finding ordered errors first, then by check id and OID
        """
        by_oid = {}
        for definition in defs:
            by_oid.setdefault(definition["oid"], []).append(definition)
        findings = self._duplicate_findings(by_oid)
        findings += self._reference_findings(refs, by_oid, checker, ref_def, id_defs)
        findings += self._orphan_findings(refs, by_oid, checker, ref_def, id_defs)
        findings.sort(key=lambda f: (f.severity != ERROR, f.check, f.oid, f.attribute or ""))
        return findings

    def _duplicate_findings(self, by_oid: dict) -> list:
        """uniqueness is checked for every definition, including the element types odmlib
        exempts from its orphan and target checks -- a duplicate ItemGroupDef OID is a real
        error even though an ItemGroupDef is legitimately never referenced"""
        findings = []
        for oid, group in by_oid.items():
            if len(group) < 2:
                continue
            detail, message = report.duplicate_text(oid, [(d["elem"], d["ordinal"])
                                                          for d in group])
            findings.append(Finding(
                check=DUPLICATE_OID, severity=ERROR, oid=oid, attribute=None,
                expected_element=None, actual_element=group[0]["elem"],
                message=message, detail=detail,
                locations=[Location(d["elem"], report.display_path(d["path"])) for d in group]))
        return findings

    def _reference_findings(self, refs: list, by_oid: dict, checker, ref_def: dict,
                            id_defs: set) -> list:
        """dangling references and type mismatches. Resolution consults every definition,
        including the skipped element types, so a reference aimed at the wrong kind of element
        is reported as a precise type_mismatch rather than a vague not-found"""
        grouped = {}
        for ref in refs:
            attr, oid = ref["attr"], ref["oid"]
            if attr in checker.skip_attr or attr not in ref_def:
                continue
            expected = ref_def[attr]
            target = by_oid.get(oid)
            if target is None:
                document = expected in id_defs
                check, actual = (UNDEFINED_DOCUMENT_REFERENCE if document
                                 else UNDEFINED_REFERENCE), None
                detail, message = report.undefined_text(attr, oid, expected, document)
            elif target[0]["elem"] == expected:
                continue
            else:
                check, actual = TYPE_MISMATCH, target[0]["elem"]
                detail, message = report.mismatch_text(attr, oid, expected, actual)
            key = (check, oid, attr)
            if key not in grouped:
                grouped[key] = Finding(
                    check=check, severity=ERROR, oid=oid, attribute=attr,
                    expected_element=expected, actual_element=actual,
                    message=message, detail=detail, locations=[])
            grouped[key].locations.append(Location(ref["elem"], report.display_path(ref["path"])))
        return list(grouped.values())

    def _orphan_findings(self, refs: list, by_oid: dict, checker, ref_def: dict,
                         id_defs: set) -> list:
        """definitions nothing references. Any reference occurrence counts, including one made
        through an attribute odmlib skips, so the warning cannot fire on an OID that is used"""
        referenced = {ref["oid"] for ref in refs}
        findings = []
        for oid, group in by_oid.items():
            elem = group[0]["elem"]
            if oid in referenced or elem in checker.skip_elem:
                continue
            via = sorted((a for a, target in ref_def.items()
                          if target == elem and a not in checker.skip_attr), key=str.lower)
            detail, message = report.orphan_text(elem, oid, via)
            findings.append(Finding(
                check=ORPHAN_DOCUMENT_LEAF if elem in id_defs else ORPHAN_DEFINITION,
                severity=WARNING, oid=oid, attribute=None, expected_element=elem,
                actual_element=elem, message=message, detail=detail,
                locations=[Location(d["elem"], report.display_path(d["path"])) for d in group]))
        return findings

    def _does_define_file_exist(self) -> None:
        """
        confirms that the define-xml file exists before attempting to check it and raises a
        DefineRefCheckError if the file does not exist
        """
        if not self.define.is_file():
            raise DefineRefCheckError(f"File {str(self.define)} not found.")
