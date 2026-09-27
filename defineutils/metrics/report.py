"""Report rendering for the metrics module.

Everything that turns a metrics result into words lives here so metrics.py stays about
loading, walking the model and counting. This module imports nothing from metrics.py -- it
duck-types the MetricsResult it is handed -- which keeps the dependency one-way and free of
an import cycle, exactly as definerefs/report.py and validate/report.py do.
"""
import json
from dataclasses import asdict
from textwrap import wrap

MODEL_LABELS = {"define_2_1": "Define-XML v2.1", "define_2_0": "Define-XML v2.0"}
SECTION_LABELS = [("document", "Document"),
                  ("definitions", "MetaDataVersion definitions"),
                  ("nested", "Nested elements")]
# the study header labels are padded to this width so their values line up
LABEL_WIDTH = 18
# a study or metadata description longer than this is truncated in the text report only
MAX_TEXT_WIDTH = 88
ABSENT = "-"


def model_label(model_package: str) -> str:
    return MODEL_LABELS.get(model_package, model_package)


def display_element(element: str, namespace: str) -> str:
    """
    the name an element is reported under: prefixed when it is not in the default ODM
    namespace, so def:leaf and def:Origin are not confused with ODM elements
    :param element: the model class name
    :param namespace: the model class namespace, "odm" for the default
    :return: string
    """
    return element if namespace == "odm" else f"{namespace}:{element}"


def human_size(size_bytes: int) -> str:
    """
    the file size as bytes plus a rounded binary unit, e.g. "174,322 bytes (170.2 KiB)".
    Bytes are always shown because they are what a reader compares between two files
    :param size_bytes: file size in bytes
    :return: string
    """
    size, unit = float(size_bytes), None
    for candidate in ("KiB", "MiB", "GiB"):
        if size < 1024:
            break
        size, unit = size / 1024, candidate
    if unit is None:
        return f"{size_bytes:,} bytes"
    return f"{size_bytes:,} bytes ({size:.1f} {unit})"


def truncate(text: str, width: int = MAX_TEXT_WIDTH) -> str:
    """shortens a long free-text value for the text report; the JSON report keeps it whole"""
    return text if len(text) <= width else text[:width - 1].rstrip() + "…"


def standard_text(standard) -> str:
    """one def:Standard rendered as 'SDTMIG 3.1.2 IG (Final)', omitting what is not set"""
    parts = [p for p in (standard.name, standard.publishing_set, standard.version,
                         standard.type) if p]
    text = " ".join(parts) or standard.oid
    return f"{text} ({standard.status})" if standard.status else text


def render_text(result, show_datasets: bool = True) -> str:
    """
    builds the formatted text report: header, permissive banner, study, element counts,
    datasets and summary
    :param result: the MetricsResult to render
    :param show_datasets: when False, the per-dataset table is omitted
    :return: string
    """
    lines = _render_header(result)
    lines += [""] + _render_study(result)
    lines += [""] + _render_elements(result)
    if show_datasets:
        lines += [""] + _render_datasets(result)
    lines += [""] + _render_summary(result)
    return "\n".join(lines)


def render_json(result, indent: int = 2) -> str:
    """
    builds the JSON report; unlike the text report it always includes the datasets and never
    truncates a description
    :param result: the MetricsResult to render
    :param indent: JSON indent
    :return: string
    """
    report = {
        "define_file": result.define_file,
        "model_package": result.model_package,
        "odmlib_version": result.odmlib_version,
        "permissive": result.permissive,
        "file": {
            "size_bytes": result.size_bytes,
            "modified": result.file_modified,
        },
        "document": {
            "file_oid": result.file_oid,
            "creation_datetime": result.creation_datetime,
            "context": result.context,
            "originator": result.originator,
            "source_system": result.source_system,
            "source_system_version": result.source_system_version,
            "odm_version": result.odm_version,
            "define_version": result.define_version,
        },
        "study": {
            "oid": result.study_oid,
            "study_name": result.study_name,
            "protocol_name": result.protocol_name,
            "study_description": result.study_description,
            "metadata_version": {
                "oid": result.mdv_oid,
                "name": result.mdv_name,
                "description": result.mdv_description,
            },
        },
        "standards": [asdict(s) for s in result.standards],
        "element_counts": [asdict(e) for e in result.elements],
        "datasets": [asdict(d) for d in result.datasets],
        "totals": {
            "elements": result.total_elements,
            "element_types": result.element_types,
            "element_types_present": result.element_types_present,
            "element_types_absent": result.element_types_absent,
            "datasets": len(result.datasets),
            "variable_references": result.total_variable_refs,
        },
    }
    return json.dumps(report, indent=indent)


def _render_header(result) -> list:
    """renders the file identity block and, on a permissive run, the non-conformance banner"""
    model = model_label(result.model_package)
    lines = ["Define-XML metrics",
             f"  File:     {result.define_file}",
             f"  Size:     {human_size(result.size_bytes)}"]
    if result.creation_datetime:
        lines.append(f"  Created:  {result.creation_datetime}  (ODM/@CreationDateTime)")
    lines += [f"  Modified: {result.file_modified}  (file system)",
              f"  Model:    {model} (odmlib {result.model_package}, "
              f"odmlib {result.odmlib_version})"]
    if result.permissive:
        lines += ["",
                  f"NOTE: loaded in permissive mode - this file is not conformant {model}.",
                  "      Counts may be incomplete; run the validate utility."]
    return lines


def _render_study(result) -> list:
    """renders the study identity block; absent values are omitted rather than shown empty"""
    lines = ["STUDY"]
    for label, value in (("Study name", result.study_name),
                         ("Protocol name", result.protocol_name),
                         ("Description", result.study_description)):
        if value:
            lines.append(_labelled(label, truncate(value)))
    if result.study_oid:
        lines.append(_labelled("Study OID", result.study_oid))
    if result.mdv_oid or result.mdv_name:
        lines.append(_labelled("MetaDataVersion", result.mdv_oid or ""))
        if result.mdv_name:
            lines.append(" " * (LABEL_WIDTH + 3) + truncate(result.mdv_name))
    for label, value in (("Define version", result.define_version),
                         ("File OID", result.file_oid),
                         ("Context", result.context),
                         ("Originator", result.originator),
                         ("Source system", _source_system(result))):
        if value:
            lines.append(_labelled(label, value))
    if result.standards:
        label = f"Standards ({len(result.standards)})"
        text = ", ".join(standard_text(s) for s in result.standards)
        lines += _wrap_value(label, text)
    return lines


def _source_system(result):
    """the source system with its version appended, when the document names one"""
    if result.source_system and result.source_system_version:
        return f"{result.source_system} {result.source_system_version}"
    return result.source_system or result.source_system_version


def _labelled(label: str, value: str) -> str:
    return f"  {label + ':':{LABEL_WIDTH}} {value}"


def _wrap_value(label: str, value: str) -> list:
    """a labelled value wrapped onto continuation lines aligned under the first one"""
    indent = " " * (LABEL_WIDTH + 3)
    lines = wrap(_labelled(label, value), width=98, subsequent_indent=indent)
    return lines or [_labelled(label, value)]


def _render_elements(result) -> list:
    """renders the element counts grouped into sections, one row per element type the model
    can hold -- an element absent from the document is reported as 0, never omitted"""
    lines = ["ELEMENT COUNTS"]
    if not result.elements:
        return lines + ["  (the model defines no elements)"]
    name_width = max(len(e.display) for e in result.elements)
    count_width = max(len(f"{e.count:,}") for e in result.elements)
    for section, heading in SECTION_LABELS:
        elements = [e for e in result.elements if e.section == section]
        if not elements:
            continue
        lines.append(f"  {heading}")
        for element in elements:
            lines.append(f"    {element.display:{name_width}}  "
                         f"{element.count:>{count_width},}")
    return lines


def _render_datasets(result) -> list:
    """renders one row per ItemGroupDef with its variable count, plus the column total"""
    lines = [f"DATASETS ({len(result.datasets)})"]
    if not result.datasets:
        return lines + ["  No ItemGroupDef elements are defined."]
    rows = [(d.oid or "", d.name or "", d.dataset_class or ABSENT,
             d.repeating or ABSENT, d.has_no_data or ABSENT, f"{d.variable_count:,}")
            for d in result.datasets]
    headings = ("OID", "Name", "Class", "Repeating", "No data", "Variables")
    widths = [max(len(headings[i]), max(len(row[i]) for row in rows))
              for i in range(len(headings))]
    lines.append("  " + _row(headings, widths))
    for row in rows:
        lines.append("  " + _row(row, widths))
    total = ("", "", "", "", "Total", f"{result.total_variable_refs:,}")
    lines.append("  " + _row(total, widths))
    return lines


def _row(values, widths) -> str:
    """one dataset table row: text columns left-aligned, the variable count right-aligned"""
    cells = [f"{value:{width}}" for value, width in zip(values[:-1], widths[:-1])]
    cells.append(f"{values[-1]:>{widths[-1]}}")
    return "  ".join(cells).rstrip()


def _render_summary(result) -> list:
    """renders the closing tallies: the element totals and the headline definition counts"""
    lines = ["SUMMARY",
             f"  {result.total_elements:,} elements across {result.element_types:,} element "
             f"types ({result.element_types_present:,} present, "
             f"{result.element_types_absent:,} absent)"]
    headline = [f"{len(result.datasets):,} dataset{_s(len(result.datasets))}",
                f"{result.total_variable_refs:,} variable reference"
                f"{_s(result.total_variable_refs)}",
                f"{result.count('ItemDef'):,} item definition{_s(result.count('ItemDef'))}",
                f"{result.count('CodeList'):,} code list{_s(result.count('CodeList'))}",
                f"{result.count('MethodDef'):,} method{_s(result.count('MethodDef'))}"]
    lines += wrap("  " + ", ".join(headline), width=98, subsequent_indent="  ")
    return lines


def _s(count: int) -> str:
    return "" if count == 1 else "s"
