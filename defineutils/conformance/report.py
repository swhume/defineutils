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
    builds the formatted text listing: header, errors, extra checks, not applicable, not
    evaluated, summary
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
    if result.extra_count:
        lines.append(f"  Extra:    {result.extras_source} ({result.extra_count})")
    if result.findings:
        lines += ["", f"ERRORS ({_rules(len(result.findings))}, {_occurrences(result.occurrence_count)})"]
        for finding in result.findings:
            lines += _render_finding(finding, max_locations)
    elif result.extra_findings:
        lines += ["", "No CDISC rule violations found."]
    else:
        lines += ["", "No conformance rule violations found."]
    if result.extra_findings:
        lines += ["", f"EXTRA CHECKS ({_checks(len(result.extra_findings))}, "
                      f"{_occurrences(result.extra_occurrence_count)})",
                  "  Extensions to the CDISC rules; each names its basis."]
        for finding in result.extra_findings:
            lines += _render_finding(finding, max_locations)
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
    if result.skipped or result.extra_skipped:
        counts = ([_rules(len(result.skipped))] if result.skipped else []) + \
                 ([_checks(len(result.extra_skipped))] if result.extra_skipped else [])
        lines += ["", f"SKIPPED ({', '.join(counts)})", "  Left out by the rule selection:"]
        lines += [f"  {', '.join(ids)}" for ids in (result.skipped, result.extra_skipped) if ids]
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
        "extra_checks": {
            "source": result.extras_source,
            "counts": {
                "checks": result.extra_count,
                "evaluated": result.extra_evaluated_count,
                "passed": len(result.extra_passed),
                "failed": len(result.extra_findings),
                "occurrences": result.extra_occurrence_count,
                "skipped": len(result.extra_skipped),
            },
            "findings": [asdict(f) for f in result.extra_findings],
            "passed": list(result.extra_passed),
            "skipped": list(result.extra_skipped),
        },
    }
    return json.dumps(report, indent=indent)


def render_rule_list(rules) -> str:
    """
    one line per rule -- id, how it is evaluated, element/attribute, source type, versions and
    the rule text, then an extra check's basis -- so the registry can be read without a define.xml
    :param rules: the Rule list
    :return: string
    """
    return "\n".join(f"{rule.id:>3}  {rule.status:<15} {rule.subject:<38} {rule.source_type:<14} "
                     f"{rule.versions:<17} {rule.text}" + (f" Basis: {rule.basis}." if rule.basis else "")
                     for rule in rules)


def _render_finding(finding, max_locations: int) -> list:
    """renders one finding: heading with the rule id, element/@attribute and occurrence count,
    the rule text and an extra check's basis, then the locations"""
    occurrences = len(finding.locations)
    subject = f"{finding.element}/@{finding.attribute}" if finding.attribute else finding.element
    lines = ["", f"  {('[' + finding.rule + ']'):<7}{subject}   ({_occurrences(occurrences)})",
             f"         {finding.message}"]
    if finding.basis:
        lines.append(f"         Basis: {finding.basis}")
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
             f"{failed} failed ({_occurrences(result.occurrence_count)}), "
             f"{len(result.not_applicable)} not applicable, {len(result.not_evaluated)} not evaluated")
    if result.skipped:
        tally += f", {len(result.skipped)} skipped"
    lines = ["SUMMARY", tally]
    if result.extra_count:
        extra = (f"  {_checks(result.extra_count)}: {result.extra_evaluated_count} evaluated, "
                 f"{len(result.extra_passed)} passed, {len(result.extra_findings)} failed "
                 f"({_occurrences(result.extra_occurrence_count)})")
        if result.extra_skipped:
            extra += f", {len(result.extra_skipped)} skipped"
        lines.append(extra)
    return lines + [f"  File: {result.define_file}"]


def _rules(count: int) -> str:
    return f"{count} rule{'s' if count != 1 else ''}"


def _checks(count: int) -> str:
    return f"{count} extra check{'s' if count != 1 else ''}"


def _occurrences(count: int) -> str:
    return f"{count} occurrence{'s' if count != 1 else ''}"


def _quoted(value) -> str:
    return f'"{value}"' if value else "no context"
