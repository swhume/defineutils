"""
Converts the CDISC Define-XML v2.1 conformance rules spreadsheet into the JSON that
defineutils/conformance/rules/define21_rules.json bundles. Run by hand when CDISC publishes a new
version of the spreadsheet; the JSON it writes is what gets committed, the .xlsx is not.

    python scripts/export_conformance_rules.py Define-XML_v2.1_Conformance_Rules.xlsx \
           defineutils/conformance/rules/define21_rules.json

The workbook is read with the standard library's zipfile and lxml rather than openpyxl, which
is not a defineutils dependency. Three artefacts of the spreadsheet are normalised here so the
rule modules never see them: the "_x000D_" carriage returns Excel writes into multi-line cells,
the HTML entities encoded twice in a few messages (&amp;lt;), and the one rule (121) whose
message cell is empty, for which the rule text is used as the message.
"""
import html
import json
import re
import sys
import zipfile
from pathlib import Path

from lxml import etree

SHEET = "DefineRules"
SOURCE = "CDISC Define-XML v2.1 Conformance Rules"
MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
RELATIONSHIPS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PACKAGE_RELATIONSHIPS = "http://schemas.openxmlformats.org/package/2006/relationships"

# spreadsheet column heading -> JSON field
COLUMNS = {"Rule Identifier": "id",
           "Plain Text Rule": "plain_text",
           "Rule": "rule",
           "Rule Message": "message",
           "Applicable Versions": "versions",
           "Source Type": "source_type",
           "XPaths": "paths",
           "Element": "element",
           "Attribute": "attribute"}

CARRIAGE_RETURN = "_x000D_"


def main(argv: list) -> int:
    if len(argv) != 3:
        print(f"usage: {Path(argv[0]).name} <rules.xlsx> <rules.json>", file=sys.stderr)
        return 2
    xlsx_file, json_file = Path(argv[1]), Path(argv[2])
    rules = export(xlsx_file)
    json_file.parent.mkdir(parents=True, exist_ok=True)
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump({"source": SOURCE, "source_file": xlsx_file.name, "rules": rules}, f, indent=1,
                  ensure_ascii=False)
        f.write("\n")
    print(f"{len(rules)} rules written to {json_file}")
    return 0


def export(xlsx_file: Path) -> list:
    """the rule records from the DefineRules sheet, in ascending rule id order"""
    with zipfile.ZipFile(xlsx_file) as workbook:
        strings = _shared_strings(workbook)
        rows = _rows(workbook, _sheet_path(workbook, SHEET), strings)
    headings = rows[0]
    fields = {column: COLUMNS[heading] for column, heading in headings.items() if heading in COLUMNS}
    missing = set(COLUMNS) - set(headings.values())
    if missing:
        raise SystemExit(f"{xlsx_file}: the {SHEET} sheet has no column(s) {sorted(missing)}")
    rules = []
    for cells in rows[1:]:
        record = {field: _clean(cells.get(column, "")) for column, field in fields.items()}
        if not record["id"]:
            continue
        record["id"] = str(int(float(record["id"])))
        record["paths"] = [path for path in (p.strip() for p in record["paths"].splitlines()) if path]
        record["attribute"] = record["attribute"] or None
        # rule 121 has no message in the spreadsheet; its rule text says the same thing
        record["message"] = record["message"] or record["rule"]
        rules.append(record)
    ids = [rule["id"] for rule in rules]
    if len(ids) != len(set(ids)):
        raise SystemExit(f"{xlsx_file}: duplicate rule ids")
    return sorted(rules, key=lambda rule: int(rule["id"]))


def _clean(text: str) -> str:
    """drops Excel's carriage-return markers and decodes doubly encoded entities"""
    text = text.replace(CARRIAGE_RETURN, "").replace("\r", "")
    while True:
        decoded = html.unescape(text)
        if decoded == text:
            break
        text = decoded
    return "\n".join(line.rstrip() for line in text.splitlines()).strip()


def _sheet_path(workbook: zipfile.ZipFile, name: str) -> str:
    """the part path of the worksheet with the given name, resolved through the workbook rels"""
    book = etree.fromstring(workbook.read("xl/workbook.xml"))
    rels = etree.fromstring(workbook.read("xl/_rels/workbook.xml.rels"))
    targets = {rel.get("Id"): rel.get("Target") for rel in rels.iter(f"{{{PACKAGE_RELATIONSHIPS}}}Relationship")}
    for sheet in book.iter(f"{{{MAIN}}}sheet"):
        if sheet.get("name") == name:
            target = targets[sheet.get(f"{{{RELATIONSHIPS}}}id")]
            return target if target.startswith("xl/") else f"xl/{target}"
    raise SystemExit(f"{workbook.filename}: no sheet named {name}")


def _shared_strings(workbook: zipfile.ZipFile) -> list:
    root = etree.fromstring(workbook.read("xl/sharedStrings.xml"))
    return ["".join(t.text or "" for t in si.iter(f"{{{MAIN}}}t")) for si in root.iter(f"{{{MAIN}}}si")]


def _rows(workbook: zipfile.ZipFile, sheet_path: str, strings: list) -> list:
    """every row as a dict of column letter -> cell text, in sheet order"""
    root = etree.fromstring(workbook.read(sheet_path))
    rows = []
    for row in root.find(f"{{{MAIN}}}sheetData"):
        cells = {}
        for cell in row:
            value = cell.find(f"{{{MAIN}}}v")
            if value is None:
                continue
            column = re.match(r"[A-Z]+", cell.get("r")).group()
            cells[column] = strings[int(value.text)] if cell.get("t") == "s" else value.text
        rows.append(cells)
    return rows


if __name__ == "__main__":
    sys.exit(main(sys.argv))
