"""Report rendering for the definerefs OID reference/definition checker.

Everything that turns a check result into words lives here so definerefs.py stays about
loading, traversal and evaluation. This module imports nothing from definerefs.py -- it
duck-types the RefCheckResult it is handed and reads severities through that object's errors
and warnings properties -- which keeps the dependency one-way and free of an import cycle.
"""
import json
from dataclasses import asdict
from textwrap import wrap

MODEL_LABELS = {"define_2_1": "Define-XML v2.1", "define_2_0": "Define-XML v2.0"}
# element class names that read better with their Define-XML namespace prefix
DISPLAY_ELEMENT = {"leaf": "def:leaf"}


def model_label(model_package: str) -> str:
    return MODEL_LABELS.get(model_package, model_package)


def display_element(element: str) -> str:
    return DISPLAY_ELEMENT.get(element, element)


def display_path(path: str) -> str:
    """
    trims the constant ODM/Study[...] prefix from a collected path, since a Define-XML file
    has exactly one of each; displayed paths therefore start at the MetaDataVersion
    :param path: the collected path, e.g. "/ODM/Study[SDTM]/MetaDataVersion[MDV.1]"
    :return: string
    """
    segments = [s for s in path.split("/") if s]
    while segments and (segments[0] == "ODM" or segments[0].split("[")[0] == "Study"):
        segments.pop(0)
    return "/".join(segments) or "(document root)"


def article(word: str) -> str:
    return "an" if word[:1].lower() in "aeiou" else "a"


def undefined_text(attribute: str, oid: str, expected: str, document: bool) -> tuple:
    """
    phrasing for a reference to an OID (or, when document is True, a def:leaf ID) that nothing
    defines
    :return: tuple of (detail for the text listing, self-contained message for the JSON report)
    """
    expected_display = display_element(expected)
    defines = "no leaf defines this ID" if document else "no element defines this OID"
    detail = f"expects {article(expected_display)} {expected_display}; {defines}"
    return detail, f"{attribute} '{oid}' {detail}"


def mismatch_text(attribute: str, oid: str, expected: str, actual: str) -> tuple:
    """
    phrasing for a reference that resolves to the wrong kind of element
    :return: tuple of (detail for the text listing, self-contained message for the JSON report)
    """
    expected_display, actual_display = display_element(expected), display_element(actual)
    detail = (f"expects {article(expected_display)} {expected_display}, but {oid} is "
              f"defined by {article(actual_display)} {actual_display}")
    return detail, f"{attribute} '{oid}' {detail}"


def duplicate_text(oid: str, definitions: list) -> tuple:
    """
    phrasing for an OID defined more than once. Two ItemDefs under the same MetaDataVersion
    share a path, so each definition is named by element type and position among its siblings
    :param definitions: list of (element class name, ordinal) tuples in document order
    :return: tuple of (detail for the text listing, self-contained message for the JSON report)
    """
    first, rest = definitions[0], definitions[1:]
    detail = (f"defined by {first[0]} (#{first[1]}) and redefined by "
              + ", ".join(f"{element} (#{ordinal})" for element, ordinal in rest))
    return detail, f"OID '{oid}' is {detail}"


def orphan_text(element: str, oid: str, via: list) -> tuple:
    """
    phrasing for a definition nothing references
    :param via: the reference attributes that could have referenced it
    :return: tuple of (detail for the text listing, self-contained message for the JSON report)
    """
    expected = f" (expected via {' or '.join(via)})" if via else ""
    display = display_element(element)
    return (f"{display} defined but never referenced{expected}",
            f"{display} '{oid}' is defined but never referenced{expected}")


def render_text(result, errors_only: bool, max_locations: int) -> str:
    """
    builds the formatted text listing: header, permissive banner, errors, warnings, summary
    :param result: the RefCheckResult to render
    :param errors_only: when True, orphan definition warnings are suppressed
    :param max_locations: max example locations shown per finding (0 shows all)
    :return: string
    """
    model = model_label(result.model_package)
    lines = ["Define-XML OID reference/definition check",
             f"  File:  {result.define_file}",
             f"  Model: {model} (odmlib {result.model_package}, odmlib {result.odmlib_version})",
             f"  Scope: {result.definition_count} definitions, {result.reference_count} "
             f"references across {len(result.checked_attributes)} checked attributes"]
    if result.permissive:
        lines += ["",
                  f"NOTE: loaded in permissive mode - this file is not conformant {model}.",
                  "      Results may be incomplete; run the validate utility."]
    sections = [("ERRORS", result.errors), ("WARNINGS", [] if errors_only else result.warnings)]
    if not any(findings for _, findings in sections):
        lines += ["", "No OID reference/definition errors found." if errors_only
                  else "No OID reference/definition problems found."]
    for heading, findings in sections:
        if not findings:
            continue
        lines += ["", f"{heading} ({len(findings)})"]
        for finding in findings:
            lines += _render_finding(finding, max_locations)
    lines += [""] + _render_summary(result, errors_only)
    return "\n".join(lines)


def render_json(result, errors_only: bool, indent: int) -> str:
    """
    builds the JSON report; unlike the text listing it never truncates the locations
    :param result: the RefCheckResult to render
    :param errors_only: when True, orphan definition warnings are suppressed
    :param indent: JSON indent
    :return: string
    """
    warnings = [] if errors_only else result.warnings
    report = {
        "define_file": result.define_file,
        "model_package": result.model_package,
        "odmlib_version": result.odmlib_version,
        "permissive": result.permissive,
        "errors_only": errors_only,
        "counts": {
            "definitions": result.definition_count,
            "references": result.reference_count,
            "errors": len(result.errors),
            "warnings": len(warnings),
        },
        "findings": [asdict(f) for f in result.errors + warnings],
        "coverage": {
            "checked_attributes": result.checked_attributes,
            "skipped_attributes": result.skipped_attributes,
            "unmapped_attributes": result.unmapped_attributes,
        },
    }
    return json.dumps(report, indent=indent)


def _render_finding(finding, max_locations: int) -> list:
    """renders one finding: heading with the OID and occurrence count, detail, locations"""
    if finding.attribute:
        occurrences = len(finding.locations)
        count = f"   ({occurrences} occurrence{'s' if occurrences != 1 else ''})"
        heading = f"  {finding.check}  {finding.attribute} = \"{finding.oid}\"{count}"
    else:
        heading = f"  {finding.check}  {finding.oid}"
    lines = ["", heading, f"      {finding.detail}"]
    shown = finding.locations if max_locations <= 0 else finding.locations[:max_locations]
    for location in shown:
        lines.append(f"      - {location.element} in {location.path}")
    if len(finding.locations) > len(shown):
        lines.append(f"      ... and {len(finding.locations) - len(shown)} more")
    return lines


def _render_summary(result, errors_only: bool) -> list:
    """renders the closing tally and the coverage note that says what was and was not checked"""
    errors, warnings = len(result.errors), len(result.warnings)
    tally = f"  {errors} error{'s' if errors != 1 else ''}"
    if errors_only:
        tally += f" in {result.define_file} (warnings suppressed)"
    else:
        tally += f", {warnings} warning{'s' if warnings != 1 else ''} in {result.define_file}"
    lines = ["SUMMARY", tally]
    lines += _wrap_attributes("  Checked attributes: ", result.checked_attributes)
    lines += _wrap_attributes("  Skipped attributes: ", result.skipped_attributes)
    if result.skipped_attributes:
        lines.append(" " * 22 + "(file-level or structurally guaranteed - not checked)")
    if result.unmapped_attributes:
        lines += _wrap_attributes("  Unmapped attributes: ", result.unmapped_attributes)
        lines.append(" " * 23 + "(no definition class in the model - not checked)")
    return lines


def _wrap_attributes(label: str, attributes: list) -> list:
    text = label + (", ".join(attributes) if attributes else "none")
    return wrap(text, width=90, subsequent_indent=" " * len(label)) or [text]
