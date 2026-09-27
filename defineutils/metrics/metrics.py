"""Metrics reporting for CDISC Define-XML v2.1.

The list of elements to count is derived from the odmlib model rather than hand-maintained:
the closure of child elements reachable from the model root supplies every element type the
document *can* hold, so one that is absent from a file is reported as 0 instead of missing
from the report. Child classes are resolved by name against the model module -- the way
odmlib's own loader does it (define_loader.py: elem_class = getattr(self.DEF, elem_name)) --
because the Define-XML MetaDataVersion inherits its ItemGroupDef, ItemDef, CodeList and
MethodDef descriptors from ODM 1.3.2, so following descriptor.element_class would walk the
ODM shape rather than the Define-XML one.
"""
import importlib
from collections import Counter, deque
from contextlib import nullcontext
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Union

import odmlib
import odmlib.define_loader as DL
import odmlib.loader as LD
from odmlib import permissive as permissive_mode
from odmlib.odm_element import ODMElement

from . import report

# instance attributes odmlib uses for its own bookkeeping; not document content
SKIP_KEYS = {"_fields", "_attr_ns", "_elems", "_attrs"}
# the element the section rule pivots on: its children are the document's definitions
DEFINITION_PARENT = "MetaDataVersion"
# the model root class; every model package in the ODM family names it ODM
ROOT_ELEMENT = "ODM"

DOCUMENT = "document"
DEFINITIONS = "definitions"
NESTED = "nested"


class DefineMetricsError(Exception):
    pass


@dataclass(frozen=True)
class ElementCount:
    element: str            # model class name, e.g. "leaf"
    display: str            # namespace-prefixed name for display, e.g. "def:leaf"
    namespace: str          # "odm" | "def"
    section: str            # "document" | "definitions" | "nested"
    count: int


@dataclass(frozen=True)
class StandardInfo:
    oid: str
    name: Union[str, None]
    type: Union[str, None]
    publishing_set: Union[str, None]
    version: Union[str, None]
    status: Union[str, None]


@dataclass(frozen=True)
class DatasetMetrics:
    oid: str
    name: Union[str, None]
    domain: Union[str, None]
    dataset_class: Union[str, None]
    sub_classes: list
    repeating: Union[str, None]
    is_reference_data: Union[str, None]
    has_no_data: Union[str, None]
    is_non_standard: Union[str, None]
    purpose: Union[str, None]
    structure: Union[str, None]
    archive_location_id: Union[str, None]
    variable_count: int     # len(ItemGroupDef.ItemRef)


@dataclass
class MetricsResult:
    define_file: str
    model_package: str
    odmlib_version: str
    permissive: bool
    size_bytes: int
    file_modified: str                          # ISO 8601, from st_mtime
    creation_datetime: Union[str, None]         # ODM/@CreationDateTime, verbatim
    file_oid: Union[str, None]
    context: Union[str, None]
    originator: Union[str, None]
    source_system: Union[str, None]
    source_system_version: Union[str, None]
    odm_version: Union[str, None]
    define_version: Union[str, None]            # MetaDataVersion/@def:DefineVersion
    study_oid: Union[str, None]
    study_name: Union[str, None]
    protocol_name: Union[str, None]
    study_description: Union[str, None]
    mdv_oid: Union[str, None]
    mdv_name: Union[str, None]
    mdv_description: Union[str, None]
    standards: list = field(default_factory=list)    # StandardInfo
    elements: list = field(default_factory=list)     # ElementCount, in model order
    datasets: list = field(default_factory=list)     # DatasetMetrics, in document order

    @property
    def total_elements(self) -> int:
        return sum(e.count for e in self.elements)

    @property
    def element_types(self) -> int:
        return len(self.elements)

    @property
    def element_types_present(self) -> int:
        return sum(1 for e in self.elements if e.count)

    @property
    def element_types_absent(self) -> int:
        return sum(1 for e in self.elements if not e.count)

    @property
    def total_variable_refs(self) -> int:
        return sum(d.variable_count for d in self.datasets)

    def count(self, element: str) -> int:
        """
        the count for one element type by model class name, 0 when the model has no such
        element; lets a report name a headline count without indexing the list
        :param element: model class name, e.g. "ItemDef"
        :return: int
        """
        return next((e.count for e in self.elements if e.element == element), 0)


class DefineMetrics:
    def __init__(self, define_xml_file: Path, model_package: str = "define_2_1",
                 permissive: bool = False) -> None:
        self.define = Path(define_xml_file)
        self.model_package = model_package
        self.permissive = permissive
        self._result = None
        self._does_define_file_exist()

    def collect(self) -> MetricsResult:
        """
        loads the define.xml and collects every metric; the result is cached so the report
        methods and the CLI do not re-parse the file
        :return: MetricsResult
        """
        if self._result is not None:
            return self._result
        model = self._model_module()
        inventory = self._element_inventory(model)
        # the load, the traversal and every attribute read share the permissive context:
        # reading an unset required attribute outside it raises
        with permissive_mode() if self.permissive else nullcontext():
            root = self._load_define()
            counts = self._count_elements(root)
            self._result = self._build_result(root, inventory, counts)
        return self._result

    def collect_to_string(self, show_datasets: bool = True) -> str:
        """
        collects the metrics and returns the formatted text report
        :param show_datasets: when False, the per-dataset table is omitted
        :return: string
        """
        return report.render_text(self.collect(), show_datasets)

    def collect_to_file(self, out_file: Path, show_datasets: bool = True,
                        as_json: bool = False) -> None:
        """
        collects the metrics and writes the report (text or JSON) to out_file
        :param out_file: Path to the file to save the report
        :param show_datasets: when False, the per-dataset table is omitted from the text report
        :param as_json: when True, writes the JSON report instead of the text report
        :return: None
        """
        if as_json:
            listing = self.collect_to_json()
        else:
            listing = self.collect_to_string(show_datasets=show_datasets)
        try:
            with open(out_file, "w", encoding="utf-8") as f:
                f.write(listing + "\n")
        except FileNotFoundError as e:
            raise DefineMetricsError(f"File {out_file} not found.\n{e}")
        except PermissionError as e:
            raise DefineMetricsError(f"Permission error attempting to write to {out_file}.\n{e}")
        except IsADirectoryError as e:
            raise DefineMetricsError(f"Error attempting to write to a directory {out_file}.\n{e}")

    def collect_to_console(self, show_datasets: bool = True) -> None:
        """
        collects the metrics and prints the formatted text report to stdout
        :param show_datasets: when False, the per-dataset table is omitted
        :return: None
        """
        print(self.collect_to_string(show_datasets=show_datasets))

    def collect_to_json(self, indent: int = 2) -> str:
        """
        collects the metrics and returns them as a JSON string; the datasets are always
        included, even when the text report suppresses them
        :param indent: JSON indent
        :return: string
        """
        return report.render_json(self.collect(), indent)

    def _model_module(self):
        """
        imports the odmlib model module the metrics are derived from and loaded into
        :return: the model module
        """
        try:
            return importlib.import_module(f"odmlib.{self.model_package}.model")
        except ImportError as e:
            raise DefineMetricsError(f"Unable to import the odmlib model package "
                                     f"{self.model_package}.\n{e}")

    def _element_inventory(self, model) -> list:
        """
        walks the model breadth-first from the root element and returns every element type
        the model can hold, in discovery order, each with the report section it belongs to.
        Breadth-first matters: def:leaf is reachable both as an ItemGroupDef child and as a
        MetaDataVersion child, and the shallower reading is the one a reader expects
        :param model: the odmlib model module
        :return: list of (class, section) tuples
        """
        root = getattr(model, ROOT_ELEMENT, None)
        if root is None:
            raise DefineMetricsError(f"The odmlib model package {self.model_package} has no "
                                     f"{ROOT_ELEMENT} root element.")
        inventory, seen = [], {ROOT_ELEMENT}
        queue = deque([(root, None, False)])
        while queue:
            cls, parent, under_definitions = queue.popleft()
            inventory.append((cls, self._section(cls.__name__, parent, under_definitions)))
            defines = cls.__name__ == DEFINITION_PARENT
            for name, descriptor in cls._elems.items():
                if name in seen:
                    continue
                seen.add(name)
                # resolve by name against the model module, the way odmlib's loader does:
                # the inherited ODM 1.3.2 descriptors would otherwise walk the ODM shape
                child = getattr(model, name, descriptor.element_class)
                queue.append((child, cls.__name__, under_definitions or defines))
        return inventory

    @staticmethod
    def _section(element: str, parent: Union[str, None], under_definitions: bool) -> str:
        """
        the report section an element type belongs to, derived from where the walk first
        reached it rather than from a curated list
        :param element: the element class name
        :param parent: the class name the walk reached it from (None for the root)
        :param under_definitions: True when the walk passed through the definition parent
        :return: "document" | "definitions" | "nested"
        """
        if element == DEFINITION_PARENT or not under_definitions:
            return DOCUMENT
        return DEFINITIONS if parent == DEFINITION_PARENT else NESTED

    def _count_elements(self, root) -> Counter:
        """
        counts every element in the loaded document by model class name in a single pass
        :param root: the root ODM object
        :return: Counter keyed by class name
        """
        counts = Counter()
        self._count(root, counts)
        return counts

    def _count(self, elem, counts: Counter) -> None:
        """
        recursive worker for _count_elements. Reads element.__dict__ rather than accessing
        attributes through the odmlib descriptors -- the technique definerefs uses -- so an
        unset attribute on a permissively loaded file is simply absent
        :param elem: the odmlib element to count
        :param counts: the Counter being accumulated
        :return: None
        """
        counts[type(elem).__name__] += 1
        for attr, obj in elem.__dict__.items():
            if attr in SKIP_KEYS:
                continue
            if isinstance(obj, ODMElement):
                self._count(obj, counts)
            elif isinstance(obj, list):
                for child in obj:
                    if isinstance(child, ODMElement):
                        self._count(child, counts)

    def _build_result(self, root, inventory: list, counts: Counter) -> MetricsResult:
        """
        assembles the MetricsResult from the loaded document, the model inventory and the
        counts. Called inside the permissive context so unset attributes cannot raise
        :param root: the root ODM object
        :param inventory: list of (class, section) tuples from _element_inventory
        :param counts: element counts keyed by class name
        :return: MetricsResult
        """
        study = self._attr(root, "Study")
        globals_ = self._attr(study, "GlobalVariables")
        mdv = self._attr(study, DEFINITION_PARENT)
        stat = self.define.stat()
        return MetricsResult(
            define_file=str(self.define),
            model_package=self.model_package,
            odmlib_version=getattr(odmlib, "__version__", "unknown"),
            permissive=self.permissive,
            size_bytes=stat.st_size,
            # st_birthtime is not available on every platform, so this is the modified time
            file_modified=datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
            creation_datetime=self._attr(root, "CreationDateTime"),
            file_oid=self._attr(root, "FileOID"),
            context=self._attr(root, "Context"),
            originator=self._attr(root, "Originator"),
            source_system=self._attr(root, "SourceSystem"),
            source_system_version=self._attr(root, "SourceSystemVersion"),
            odm_version=self._attr(root, "ODMVersion"),
            define_version=self._attr(mdv, "DefineVersion"),
            study_oid=self._attr(study, "OID"),
            study_name=self._text(self._attr(globals_, "StudyName")),
            protocol_name=self._text(self._attr(globals_, "ProtocolName")),
            study_description=self._text(self._attr(globals_, "StudyDescription")),
            mdv_oid=self._attr(mdv, "OID"),
            mdv_name=self._attr(mdv, "Name"),
            mdv_description=self._attr(mdv, "Description"),
            standards=self._standards(mdv),
            elements=[ElementCount(element=cls.__name__,
                                   display=report.display_element(cls.__name__,
                                                                  getattr(cls, "namespace", "odm")),
                                   namespace=getattr(cls, "namespace", "odm"),
                                   section=section,
                                   count=counts.get(cls.__name__, 0))
                      for cls, section in inventory],
            datasets=self._datasets(mdv),
        )

    def _standards(self, mdv) -> list:
        """
        the def:Standard elements the MetaDataVersion references, in document order
        :param mdv: the MetaDataVersion object, or None
        :return: list of StandardInfo
        """
        container = self._attr(mdv, "Standards")
        return [StandardInfo(oid=self._attr(std, "OID"),
                             name=self._attr(std, "Name"),
                             type=self._attr(std, "Type"),
                             publishing_set=self._attr(std, "PublishingSet"),
                             version=self._attr(std, "Version"),
                             status=self._attr(std, "Status"))
                for std in self._attr(container, "Standard") or []]

    def _datasets(self, mdv) -> list:
        """
        one row per ItemGroupDef in document order, with its variable count. The count is
        len(ItemRef), which is deliberately not the ItemDef count: ItemDefs are shared, and
        value-level ItemDefs are referenced from a def:ValueListDef rather than a dataset
        :param mdv: the MetaDataVersion object, or None
        :return: list of DatasetMetrics
        """
        datasets = []
        for group in self._attr(mdv, "ItemGroupDef") or []:
            group_class = self._attr(group, "Class")
            datasets.append(DatasetMetrics(
                oid=self._attr(group, "OID"),
                name=self._attr(group, "Name"),
                domain=self._attr(group, "Domain"),
                dataset_class=self._attr(group_class, "Name"),
                sub_classes=[self._attr(sub, "Name")
                             for sub in self._attr(group_class, "SubClass") or []],
                repeating=self._attr(group, "Repeating"),
                is_reference_data=self._attr(group, "IsReferenceData"),
                has_no_data=self._attr(group, "HasNoData"),
                is_non_standard=self._attr(group, "IsNonStandard"),
                purpose=self._attr(group, "Purpose"),
                structure=self._attr(group, "Structure"),
                archive_location_id=self._attr(group, "ArchiveLocationID"),
                variable_count=len(self._attr(group, "ItemRef") or []),
            ))
        return datasets

    @staticmethod
    def _attr(elem, name: str):
        """
        reads one attribute or child out of the instance __dict__ rather than through the
        odmlib descriptor, so an unset attribute on a permissively loaded file returns None
        instead of raising, and an absent optional child needs no separate guard
        :param elem: the odmlib element, or None
        :param name: the attribute or child element name
        :return: the value, or None
        """
        return None if elem is None else elem.__dict__.get(name)

    @staticmethod
    def _text(elem) -> Union[str, None]:
        """the body text of an element such as StudyName, which odmlib holds in _content"""
        return None if elem is None else elem.__dict__.get("_content")

    def _load_define(self):
        """
        loads the define.xml into the odmlib model and returns the root ODM object. odmlib
        raises a mix of exception types here -- ParseError on malformed XML, AttributeError on
        an unexpected root element or an element the model does not define, OdmlibError
        subclasses on non-conformant content -- so the load boundary catches Exception and
        re-raises DefineMetricsError with guidance
        :return: the root ODM object
        """
        try:
            return self._open_define()
        except Exception as e:
            raise DefineMetricsError(self._load_error_message(e))

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
        exception type keeps the guidance correct across odmlib releases
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
                   f"No metrics were collected. This file must parse as conformant\n"
                   f"{model} before its metrics can be collected. Run the validate\n"
                   f"utility to identify the problems:\n\n"
                   f"    python -m defineutils.validate -d {self.define}\n\n"
                   f"Then re-run these metrics.")
        if not self.permissive and self._permissive_would_load():
            message += (" To collect best-effort metrics from the file as-is,\n"
                        "add --permissive.")
        return message

    def _does_define_file_exist(self) -> None:
        """
        confirms that the define-xml file exists before attempting to read it and raises a
        DefineMetricsError if the file does not exist
        """
        if not self.define.is_file():
            raise DefineMetricsError(f"File {str(self.define)} not found.")
