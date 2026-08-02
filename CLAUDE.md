# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Maintaining this file
- When a change alters a documented invariant, a default, a public API signature, or introduces a 
non-obvious gotcha, update the relevant section here as part of
the same phase — before reporting the phase complete. Do not log what changed;
record only what a future session needs to know to avoid getting it wrong.

## Instructions
- Read a file in this session before any Edit or Write to it. Never attempt an
  edit on a file you have not read.
- Do not fill gaps from adjacent knowledge. If you don't know whether tool X
  does Y, say so — don't reason from what similar tools do.
- Before naming any API, method, default, or cardinality, read it from the
  installed package or the repo. If you can't, label it unverified.

## Project Overview

defineutils is a Python package for working with CDISC Define-XML v2.1 files. It provides four modules:
- **definehtml**: Transforms define.xml files to HTML using an embedded XSL stylesheet
- **validate**: Schema validates define.xml files using embedded XSD schemas
- **definepp**: Pretty-prints (re-indents) define.xml files
- **definerefs**: Checks OID reference/definition integrity in define.xml files

## Commands

### Install dependencies
```bash
pip install -e .
```

### Run tests
```bash
pytest
```

### Run a single test
```bash
pytest tests/test_definehtml.py::test_transform_to_html_string_basic
```

### Run modules from command line
```bash
# Transform define.xml to HTML
python -m defineutils.definehtml -d tests/define.xml -o tests/define.html

# Schema validate a define.xml (add -s for a schema other than the bundled v2.1; -o, --json, -L as needed)
python -m defineutils.validate -d tests/define.xml
python -m defineutils.validate -d tests/define.xml -s cdisc-define-2.0/define2-0-0.xsd
python -m defineutils.validate -d tests/define.xml --json -o report.json

# Pretty-print a define.xml to a file (omit -o to print to the console; -H limits console lines)
python -m defineutils.definepp -d tests/define.xml -o tests/define.pretty.xml

# Check OID references/definitions (add --json, --errors-only, -L, --permissive as needed)
python -m defineutils.definerefs -d tests/define.xml
```

## Architecture

The package is structured as `defineutils` with four submodules:
- `defineutils/definehtml/` - HTML generation from Define-XML
- `defineutils/validate/` - Schema validation
- `defineutils/definepp/` - Pretty-printing
- `defineutils/definerefs/` - OID reference/definition checking

Each submodule follows the same pattern:
- Main class in `<submodule>.py` with a custom exception class
- `__init__.py` exports the main class and exception
- `__main__.py` enables CLI usage via `python -m defineutils.<submodule>`

**definehtml module**: Uses lxml for XSLT transformation. The `DefineHtml` class takes a define.xml path, applies the bundled `define2-1.xsl` stylesheet, and outputs HTML via `transform_to_html_string()` or `transform_to_html_file()`.

**validate module**: Uses xmlschema for validation. The `DefineSchemaValidator` class validates against the bundled
Define-XML v2.1 schemas in `defineutils/validate/schema/`; the entry point is the module-level `DEFAULT_SCHEMA`
(`schema/cdisc-define-2.1/define2-1-0.xsd`), used when the `xsd_file` argument (CLI `-s`/`--schema`) is not given. Any
schema file path is accepted, so a define.xml can be validated against another Define-XML version. The resolved path is
kept on `self.xsd_file`. Failures that mean the check could not be run at all -- a schema that will not load (the
`XMLSchema` object is built eagerly in `__init__`), a define.xml that is missing or not well-formed, or a report that
could not be written -- raise `DefineSchemaLoadError`, a subclass of `DefineSchemaValidationError`, so it must be
caught first where the two are distinguished. Sets exit codes: 0 valid, 1 invalid, 2 could not validate; the report
goes to stdout and failure messages to stderr.

There are two validation paths, deliberately. `validate_define_file()` calls `xsd.validate()` on the file *path*, which
raises on the **first** error; it is left that way as the quick check and its message wording is depended on by callers.
`validate()` calls `xsd.iter_errors()` and collects **every** error, returning a `ValidationResult` cached on
`self._result` that the `validate_to_string()` / `_to_file()` / `_to_console()` / `_to_json()` reports and the CLI exit
code all reuse. There is no `errors_only` parameter anywhere -- schema validation yields only errors, never warnings.

The collecting path parses with lxml (`etree.XMLParser(remove_comments=True)`) rather than handing xmlschema the path.
Two reasons, both load-bearing: handing over a path leaves `error.sourceline` unset, so there would be no line numbers;
and lxml keeps comments as child nodes, which shifts the child positions xmlschema reports in `at position N` messages,
so they must be stripped for the reasons to match what the path source produces. Because lxml does the parsing, a
missing file surfaces as `OSError` and a malformed one as `etree.XMLSyntaxError`; both are mapped onto
`DefineSchemaLoadError` with the same wording the path-based route uses.

Errors are grouped by `(check, element, reason)` into one `Finding` holding a `Location` (OID-decorated path plus line)
per occurrence, sorted by descending occurrence count -- 401 raw errors against a mismatched schema become 110
findings. The `check` id is derived **structurally**, never by matching on `reason` text, which xmlschema formats and is
free to reword: `XMLSchemaChildrenValidationError` with `invalid_tag` set is `unexpected_child` and without it
`incomplete_content`; `XMLSchemaDecodeError` (a subclass, so test it before the generic branches) is `invalid_value`;
an `XsdAttributeGroup` validator is `attribute_error` (covering both a missing required attribute and a disallowed one);
a validator whose class name contains `Facet` is `invalid_value`; anything else falls back to `schema_validation`.
Rendering lives in `defineutils/validate/report.py`, which imports nothing from `validate.py` -- it duck-types the
result -- keeping the dependency one-way, exactly as `definerefs/report.py` does.

**definepp module**: Uses lxml to re-indent a define.xml. The `DefinePrettyPrinter` class parses with `remove_blank_text=True` and serializes with `pretty_print=True`, a byte-preserving reformat (comments, processing instructions, order and namespaces are retained). It outputs via `pretty_print_to_file()`, `pretty_print_to_string()`, or `pretty_print_to_console()` (with an optional line limit for paging), and raises `DefinePrettyPrintError`. This module bundles no resources.

**definerefs module**: Uses odmlib (`>= 0.2.0`, a runtime dependency) to load the define.xml into the `define_2_1`
model and check OID reference/definition integrity. `create_oid_checker("define_2_1")` is the authority on *what* to
check -- its introspected `ref_def` mapping and `skip_attr` / `skip_elem` lists are used as-is, never hand-coded --
but `DefineRefChecker` does its own recursive traversal of `element.__dict__` rather than calling `verify_oids()`,
because odmlib raises on the first violation and stores references as sets of OID values, so it can report neither
every problem nor where each one lives. Two gaps in odmlib 0.2.0 are filled here: the Define-XML `def:leaf` / `leafID`
/ `def:ArchiveLocationID` ref/def pairs (supplemented with `setdefault`, so a later odmlib that maps them natively
wins and nothing is double-reported), and uniqueness for the `skip_elem` classes, which odmlib exempts before its
duplicate test. Reports come from `check_to_string()`, `check_to_file()`, `check_to_console()` and `check_to_json()`;
errors are dangling references, duplicate OIDs and type mismatches, while orphan definitions are warnings. Raises
`DefineRefCheckError`, whose load-failure message recommends the validate module. This module bundles no resources
and sets exit codes (0 clean, 1 errors, 2 could not check).

The definehtml and validate modules bundle their required resources (XSL stylesheet, XSD schemas) to simplify usage.
