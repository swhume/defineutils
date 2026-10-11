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

defineutils is a Python package for working with CDISC Define-XML v2.1 files. It provides five modules:
- **definehtml**: Transforms define.xml files to HTML using an embedded XSL stylesheet
- **validate**: Schema validates define.xml files using embedded XSD schemas
- **definepp**: Pretty-prints (re-indents) define.xml files
- **definerefs**: Checks OID reference/definition integrity in define.xml files
- **metrics**: Reports element counts and file/study metrics for define.xml files

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
# Transform define.xml to HTML (omit -o to write <define name>.html beside the input; add --comments-table,
# --no-methods-table, --prefixes, --length-format, --codelist-items N as needed)
python -m defineutils.definehtml -d tests/define.xml -o tests/define.html

# Schema validate a define.xml (add -s for a schema other than the bundled v2.1; -o, --json, -L as needed)
python -m defineutils.validate -d tests/define.xml
python -m defineutils.validate -d tests/define.xml -s cdisc-define-2.0/define2-0-0.xsd
python -m defineutils.validate -d tests/define.xml --json -o report.json

# Pretty-print a define.xml to a file (omit -o to print to the console; -H limits console lines)
python -m defineutils.definepp -d tests/define.xml -o tests/define.pretty.xml

# Check OID references/definitions (add --json, --errors-only, -L, --permissive as needed)
python -m defineutils.definerefs -d tests/define.xml

# Report define.xml metrics (add -o, --json, --no-datasets, --permissive as needed)
python -m defineutils.metrics -d tests/define.xml
```

## Architecture

The package is structured as `defineutils` with five submodules:
- `defineutils/definehtml/` - HTML generation from Define-XML
- `defineutils/validate/` - Schema validation
- `defineutils/definepp/` - Pretty-printing
- `defineutils/definerefs/` - OID reference/definition checking
- `defineutils/metrics/` - Element counts and file/study metrics

Each submodule follows the same pattern:
- Main class in `<submodule>.py` with a custom exception class
- `__init__.py` exports the main class and exception
- `__main__.py` enables CLI usage via `python -m defineutils.<submodule>`

**definehtml module**: Uses lxml for XSLT transformation. `DefineHtml` compiles the bundled `define2-1.xsl` (the
module-level `STYLESHEET`) once in `__init__` and renders via `transform_to_html_string()`, which returns `str`, or
`transform_to_html_file()`; the result tree is cached on `self._result`. Serialize an XSLT result only with
`str(result)` / `bytes(result)`, **never `etree.tostring()`**. `tostring()` writes XML and ignores the stylesheet's
`xsl:output method="html"`, self-closing empty `<span/>` / `<a/>` / `<ul/>`, which browsers read as unclosed start tags
that swallow the rest of the page. That was the real cause of the a0022b8 "text shown as hyperlinks" workaround in the
stylesheet.

Every failure raises `DefineHtmlGenerationError`; nothing returns an empty result or writes nothing silently.
- XSLT errors carry the distinct `error_log` messages, because `str(XSLTApplyError)` can be one word (`'first'`).
- Input must have an ODM v1.3 root and a MetaDataVersion with the v2.1 `def:DefineVersion`. The stylesheet binds `def:`
  to the v2.1 namespace, so other input would otherwise render without error but with most of its content missing.
- `transform_to_html_file()` checks the destination before transforming, and refuses one that is the input
  (`samefile`).

Before serializing, `_neutralize_unsafe_links()` turns each `<a href>` into a `<span>` unless its scheme is relative,
`http`, `https`, `file` or a one-letter Windows drive, since hrefs are copied verbatim from `def:leaf/@xlink:href` and
`ExternalCodeList/@href`.

The stylesheet's five `xsl:param`s are constructor options:

| Option | Default | CLI flag |
|---|---|---|
| `codelist_items` | 5 | `--codelist-items N` |
| `methods_table` | True | `--no-methods-table` |
| `comments_table` | False | `--comments-table` |
| `prefixes` | False | `--prefixes` |
| `length_format` | False | `--length-format` |

lxml evaluates parameter values as XPath expressions, so only validated integers are passed.

CLI: `-d` is required and `-o` defaults to `<define stem>.html` beside the input. Exit codes: 0 HTML written; 2 not
written (`DefineHtmlGenerationError`); 1 an unexpected exception, with the traceback on stderr; 130 Ctrl-C.

`define2-1.xsl` is a modified copy of Lex Jansen's stylesheet: **log every stylesheet edit in
`stylesheet_changes.md`**.
- Its OID lookups use `xsl:key`s whose match patterns are anchored at `/odm:ODM/odm:Study[1]/odm:MetaDataVersion[1]`,
  the same node set as the `$g_seq…` globals they replaced. Use `key()` for new lookups and keep that anchoring;
  filtering a `$g_seq…` sequence by OID makes rendering quadratic again.
- `key()` searches the context node's document, so it must not be called with the context inside the `str:tokenize`
  loops of `linkPages2Hyperlinks` / `linkNamedDestinations2Hyperlinks`.

Rendering tests:
- The `edited_define` fixture in `tests/conftest.py` builds synthetic define.xml files from an lxml edit of a test file.
- `tests/define-adam.xml`, the CDISC ADaM sample, is the only test file with ARM content.

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

**metrics module**: Uses odmlib to load the define.xml into the `define_2_1` model and report file/study identity,
a count for every element type, and a per-dataset table. `DefineMetrics.collect()` returns a `MetricsResult` cached on
`self._result`; `collect_to_string()` / `_to_file()` / `_to_console()` / `_to_json()` all reuse it. Raises
`DefineMetricsError`, reusing definerefs' load-failure wording (recommends the validate module, and suggests
`--permissive` only when a permissive load of that file actually succeeds). Bundles no resources.

The counted element list is **derived from the model, never hand-coded**: `_element_inventory()` walks the closure of
child elements reachable from `<model>.ODM` breadth-first over each class's `_elems`, so an element absent from a
document is reported as `0` rather than omitted -- the whole point of the report. Two invariants make that walk
correct and must not be "simplified":

- Child classes are resolved **by name against the model module** (`getattr(model, name, descriptor.element_class)`),
  mirroring `odmlib/define_loader.py` (`elem_class = getattr(self.DEF, elem_name)`). `define_2_1.MetaDataVersion`
  inherits its `ItemGroupDef` / `ItemDef` / `CodeList` / `MethodDef` descriptors from `odm_1_3_2.MetaDataVersion`, so
  following `descriptor.element_class` walks the **ODM 1.3.2** shape: `ItemDef` gains `Question`, `ExternalQuestion`,
  `MeasurementUnitRef` and `ErrorMessage` and loses `def:Origin` / `def:ValueListRef`, and `ItemGroupDef` loses
  `def:Class` / `def:leaf`. Nothing raises when this goes wrong; `tests/test_metrics.py` pins the inventory to the
  model's own class set (39 element types for `define_2_1`).
- The walk is breadth-first because a section is assigned from where an element is *first* reached: `MetaDataVersion`'s
  own children are the `definitions` section, everything deeper is `nested`. `def:leaf` is reachable both ways, and BFS
  puts it with the definitions.

Counting is a separate `element.__dict__` traversal (the definerefs technique, for the same reason), and every
attribute read happens inside the same permissive context as the load, since reading an unset required attribute
outside it raises. Element counts are per element type across the whole document, so `ItemRef` (199 in
`tests/define.xml`) covers both dataset variables and the value-level ItemRefs under `def:ValueListDef`; the dataset
table's `Variables` column and `total_variable_refs` count only `len(ItemGroupDef.ItemRef)` (155) -- the two numbers
differ by design. Exit codes are 0 (report produced), 2 (could not be produced) and 1 (an unexpected exception, with
the traceback on stderr). 1 never judges the file, because a metrics report describes a file rather than judging it.
`main()` re-raises `BrokenPipeError` ahead of its `except Exception`, so quitting a pager still exits 0 at the entry
point.

The definehtml and validate modules bundle their required resources (XSL stylesheet, XSD schemas) to simplify usage.
