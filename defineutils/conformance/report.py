"""Report rendering for the conformance rule checker.

Everything that turns a conformance result into words lives here so conformance.py stays about
loading and evaluating. This module imports nothing from conformance.py -- it duck-types the
ConformanceResult it is handed -- which keeps the dependency one-way, as the other report
modules do.
"""
import json
from dataclasses import asdict

from .rules import REQUIREMENT_LABELS, SUBMISSION


def render_text(result, max_locations: int) -> str:
    """
    builds the formatted text listing: header, errors, not applicable, not evaluated, summary
    :param result: the ConformanceResult to render
    :param max_locations: max example locations shown per finding (0 shows all)
    :return: string
    """
    version = f"Define-XML {result.define_version}" if result.define_version else "Define-XML version not given"
    context = result.context if result.context else "not given"
    lines = ["Define-XML conformance check",
             f"  File:     {result.define_file}",
             f"  Version:  {version}    Context: {context}",
             f"  Rules:    {result.rules_source} ({result.rule_count})"]
    if result.findings:
        failed, occurrences = len(result.findings), result.occurrence_count
        lines += ["", f"ERRORS ({failed} rule{'s' if failed != 1 else ''}, "
                      f"{occurrences} occurrence{'s' if occurrences != 1 else ''})"]
        for finding in result.findings:
            lines += _render_finding(finding, max_locations)
    else:
        lines += ["", "No conformance rule violations found."]
    if result.not_applicable:
        lines += ["", f"NOT APPLICABLE ({_rules(len(result.not_applicable))})",
                  f'  Require ODM/@def:Context="{SUBMISSION}"; this document declares '
                  f'{_quoted(result.context)}:',
                  f"  {', '.join(result.not_applicable)}"]
    if result.not_evaluated:
        lines += ["", f"NOT EVALUATED ({_rules(len(result.not_evaluated))})"]
        for requirement, label in REQUIREMENT_LABELS.items():
            ids = [rule_id for rule_id, needs in result.not_evaluated if needs == requirement]
            if ids:
                lines.append(f"  {('Need ' + label + ':'):<40}{', '.join(ids)}")
    if result.skipped:
        lines += ["", f"SKIPPED ({_rules(len(result.skipped))})",
                  "  Left out by the rule selection:", f"  {', '.join(result.skipped)}"]
    lines += [""] + _render_summary(result)
    return "\n".join(lines)


def render_json(result, indent: int) -> str:
    """
    builds the JSON report; unlike the text listing it never truncates the locations
    :param result: the ConformanceResult to render
    :param indent: JSON indent
    :return: string
    """
    report = {
        "define_file": result.define_file,
        "define_version": result.define_version,
        "context": result.context,
        "rules_source": result.rules_source,
        "counts": {
            "rules": result.rule_count,
            "evaluated": result.evaluated_count,
            "passed": len(result.passed),
            "failed": len(result.findings),
            "occurrences": result.occurrence_count,
            "not_applicable": len(result.not_applicable),
            "not_evaluated": len(result.not_evaluated),
            "skipped": len(result.skipped),
        },
        "findings": [asdict(f) for f in result.findings],
        "passed": list(result.passed),
        "not_applicable": list(result.not_applicable),
        "not_evaluated": [{"rule": rule_id, "requires": needs} for rule_id, needs in result.not_evaluated],
        "skipped": list(result.skipped),
    }
    return json.dumps(report, indent=indent)


def render_rule_list(rules) -> str:
    """
    one line per rule -- id, how it is evaluated, element/attribute, source type, versions and
    the rule text -- so the registry can be read without a define.xml
    :param rules: the Rule list
    :return: string
    """
    return "\n".join(f"{rule.id:>3}  {rule.status:<15} {rule.subject:<38} {rule.source_type:<14} "
                     f"{rule.versions:<17} {rule.text}" for rule in rules)


def _render_finding(finding, max_locations: int) -> list:
    """renders one finding: heading with the rule id, element/@attribute and occurrence count,
    the rule text, then the locations"""
    occurrences = len(finding.locations)
    subject = f"{finding.element}/@{finding.attribute}" if finding.attribute else finding.element
    lines = ["", f"  {('[' + finding.rule + ']'):<7}{subject}   ({occurrences} "
                 f"occurrence{'s' if occurrences != 1 else ''})",
             f"         {finding.message}"]
    shown = finding.locations if max_locations <= 0 else finding.locations[:max_locations]
    for location in shown:
        where = f"line {location.line}  " if location.line else ""
        lines.append(f"         - {where}{location.path}: {location.detail}")
    if occurrences > len(shown):
        lines.append(f"         ... and {occurrences - len(shown)} more")
    return lines


def _render_summary(result) -> list:
    failed = len(result.findings)
    tally = (f"  {result.rule_count} rules: {result.evaluated_count} evaluated, {len(result.passed)} passed, "
             f"{failed} failed ({result.occurrence_count} occurrence{'s' if result.occurrence_count != 1 else ''}), "
             f"{len(result.not_applicable)} not applicable, {len(result.not_evaluated)} not evaluated")
    if result.skipped:
        tally += f", {len(result.skipped)} skipped"
    return ["SUMMARY", tally, f"  File: {result.define_file}"]


def _rules(count: int) -> str:
    return f"{count} rule{'s' if count != 1 else ''}"


def _quoted(value) -> str:
    return f'"{value}"' if value else "no context"
