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

defineutils is a Python package for working with CDISC Define-XML v2.1 files. It provides six modules:
- **definehtml**: Transforms define.xml files to HTML using an embedded XSL stylesheet
- **validate**: Schema validates define.xml files using embedded XSD schemas
- **definepp**: Pretty-prints (re-indents) define.xml files
- **definerefs**: Checks OID reference/definition integrity in define.xml files
- **metrics**: Reports element counts and file/study metrics for define.xml files
- **defineview**: Renders a define.xml with definehtml and opens it in the default browser (double-click on Windows)

## Commands

### Install dependencies
```bash
pip install -e .   # also creates the six commands; re-run after the version, [project.scripts] or
                   # [project.gui-scripts] changes
```

### Run tests
```bash
pytest
# run the CLI tests against a folder of commands (installed console scripts, or an unzipped frozen build); this also
# runs tests/test_commands_match_modules.py, which compares each command's output with python -m
DEFINEUTILS_BIN=.venv/bin pytest
```

### Build the executables
```bash
# Python 3.12, with defineutils installed; writes packaging/dist/defineutils-<version>-<platform>.zip
pip install . -r packaging/requirements-build.txt
python packaging/build_executables.py
python packaging/build_executables.py --zip-only   # rezip packaging/dist/defineutils without rebuilding (after signing)
```

### Run a single test
```bash
pytest tests/test_definehtml.py::test_transform_to_html_string_basic
```

### Run the commands
Each command is equivalent to `python -m defineutils.<module>` (definevalidate is `defineutils.validate`,
definemetrics is `defineutils.metrics`); the `python -m` form also works uninstalled from the repo root. Every
command takes `--version`.
```bash
# Transform define.xml to HTML (omit -o to write <define name>.html beside the input; add --comments-table,
# --no-methods-table, --prefixes, --length-format, --codelist-items N as needed)
definehtml -d tests/define.xml -o tests/define.html

# Schema validate a define.xml (add -s for a schema other than the bundled v2.1; -o, --json, -L as needed)
definevalidate -d tests/define.xml
definevalidate -d tests/define.xml -s cdisc-define-2.0/define2-0-0.xsd
definevalidate -d tests/define.xml --json -o report.json

# Pretty-print a define.xml to a file (omit -o to print to the console; -H limits console lines)
definepp -d tests/define.xml -o tests/define.pretty.xml

# Check OID references/definitions (add --json, --errors-only, -L, --permissive as needed)
definerefs -d tests/define.xml

# Report define.xml metrics (add -o, --json, --no-datasets, --permissive as needed)
definemetrics -d tests/define.xml

# Show a define.xml in the browser: the path is positional (--temp, -o, --no-open as needed)
defineview tests/define.xml
```

## Architecture

The package is structured as `defineutils` with six submodules:
- `defineutils/definehtml/` - HTML generation from Define-XML
- `defineutils/validate/` - Schema validation
- `defineutils/definepp/` - Pretty-printing
- `defineutils/definerefs/` - OID reference/definition checking
- `defineutils/metrics/` - Element counts and file/study metrics
- `defineutils/defineview/` - Showing a define.xml in the browser

Each submodule follows the same pattern:
- Main class in `<submodule>.py` with a custom exception class
- `__init__.py` exports the main class and exception
- `__main__.py` holds the CLI: `main()` parses the arguments and returns the exit code, and `run()` is the entry
  point for both the console script (`[project.scripts]` in `pyproject.toml`; defineview is in
  `[project.gui-scripts]`) and `python -m`

CLI invariants:
- The console and GUI scripts call `run()` directly and never execute the `if __name__ == "__main__":` block, so the
  Ctrl-C / broken-pipe handling must stay in `run()`. Point a new command at `run`, not `main`.
- Each parser sets `prog=` to its command name (otherwise usage reads `__main__.py`, or `definehtml.exe` once frozen)
  and has `--version`.
- Messages that tell the user to run another tool name the command (`definevalidate -d <file>`), never
  `python -m ...`, which does not exist for users of a frozen build.
- CLI tests start processes only through the `run_cli` / `cli_command` fixtures in `tests/conftest.py`, so setting
  `DEFINEUTILS_BIN` re-runs them all against the installed or frozen commands. The one exception is `run_module`,
  the `python -m` reference that `tests/test_commands_match_modules.py` compares the commands with.
- Writing an output file to a folder must be reported as a folder. Windows raises `PermissionError`, not
  `IsADirectoryError`, there, so each `*_to_file()` checks `os.path.isdir()` in its `PermissionError` handler. Use
  `os.path.isdir()`, not `Path.is_dir()`: the latter raises when a parent folder can't be read. definehtml checks
  before writing instead. `tests/test_write_to_folder.py` simulates the Windows error for the other four modules.

**Executables** (`packaging/`, built by `.github/workflows/executables.yml` on Windows x64 and macOS arm64):
`packaging/defineutils.spec` builds six one-folder executables from `packaging/entry/<command>.py`, passed to one
shared `COLLECT` so they share one `_internal` folder; `build_executables.py` adds `README.txt` and `LICENSES/` (one
folder per bundled distribution, found from defineutils' requirements, plus Python and PyInstaller) and zips it.
- A new command needs an entry script and a `COMMANDS` entry in the spec, as well as `[project.scripts]` (or
  `[project.gui-scripts]`), the `COMMANDS` dict in `tests/conftest.py` and `ENTRY_MODULES` in
  `tests/test_entry_points.py`.
- A new data file or computed import, in defineutils or a dependency, must be collected in the spec, or the frozen
  build fails only when that code runs. CI's run of the tests against the unzipped executables is what catches it.
- Spec choices that were measured; don't revert them:
  - `noarchive=True`: an archive would put a ~4.5 MB copy of the Python code in each executable.
  - No `collect_all("xmlschema")`: the contrib hook is enough, and `collect_all` bundles xmlschema's test framework.
  - `excludes` setuptools: PyInstaller requires it, cerberus pulls it in, and its runtime hook slows start-up.
  - `X utf8`: the executables run in UTF-8 mode, so output redirected on Windows is UTF-8. That is why `run_module`
    also uses `-X utf8`; pip-installed commands on Windows don't, so they may not match it there.
- Build output goes to `packaging/build/` and `packaging/dist/`, never the top-level `dist/` holding the PyPI files.
- Never add `__init__.py` to `packaging/`: with the repo root on `sys.path` (`python -m pytest`), it would shadow the
  PyPI `packaging` library that pytest and PyInstaller import.
- A `v*` tag build attaches both zips to that tag's GitHub Release, creating a published release if none exists. The
  zip names carry the package version, so the release job fails when the tag doesn't match it.
- The version is in both `pyproject.toml` and `defineutils/__init__.py`. The zip name uses `__version__`, and
  `tests/test_entry_points.py` fails in CI when the two differ.
- README.md's "Downloading the commands" and "Opening a define.xml with a double-click" sections and
  `packaging/README.txt` name the zips and give the unblock and "Open with" steps; keep them in step with
  `platform_name()` and with each other.
- CI checks out with LF line endings, while a local working copy may have CRLF (`tests/define.xml` does), so tests
  must not pin a test file's byte size.
- Windows can't deliver SIGINT to a child process, so the subprocess Ctrl-C test is skipped there;
  `tests/test_entry_points.py` covers `run()`'s Ctrl-C handling on every platform.

**Windows signing** (setup and behaviour in `packaging/SIGNING.md`; macOS signing is deferred):
- **What runs it:** the `sign-windows` job signs with Azure Artifact Signing on a `v*` tag, or on a manual run with
  `sign`, once the `ARTIFACT_SIGNING_ACCOUNT` repository variable is set. That condition appears twice: in the
  workflow's `env.SIGN_WINDOWS` and in the job's `if`, which can't read env. Change both together.
- **Azure login:** the job uses OIDC through the `signing` GitHub environment. Entra federated credentials can't
  match a tag pattern, so the environment is what lets every tag sign; keep the job's `environment: signing`.
- **What is signed:** only files without a signature, listed by `packaging/windows_signing.ps1 -Action List`. Never
  sign the whole folder: it would replace the PSF's and Microsoft's signatures on Python and the runtime.
- **Timestamps:** every signature needs one, because Artifact Signing certificates last three days. `-Action Check`
  fails on any signature without one.
- **Artifact names:** on a signing run, the build job uploads the Windows zip as `windows-unsigned`. The sign job
  rezips it with `build_executables.py --zip-only`, so the only artifact named `defineutils-*-windows-x64.zip` is the
  signed one, which the release job's `defineutils-*` pattern picks up.
- **The throwaway-certificate check:** every Windows build signs a copy with a throwaway self-signed certificate
  (`-Action TrySelfSigned`) and runs the commands from it.
- **Running defineview in workflow PowerShell:** it is windowed, and `&` is not expected to wait for a windowed
  program or set `$LASTEXITCODE`, so use `Start-Process -Wait -PassThru` and check `.ExitCode`.
- **PowerShell version:** `windows_signing.ps1` runs under Windows PowerShell 5.1 (`shell: powershell`), where
  `New-SelfSignedCertificate` and the Authenticode cmdlets are built in. Keep it free of PowerShell 7-only syntax and
  of .NET Core-only APIs.

**definehtml module**: Uses lxml for XSLT transformation. `DefineHtml` compiles the bundled `define2-1.xsl` (the
module-level `STYLESHEET`) once in `__init__` and renders via `transform_to_html_string()`, which returns `str`, or
`transform_to_html_file()`; the result tree is cached on `self._result`. Serialize an XSLT result only with
`str(result)` / `bytes(result)`, **never `etree.tostring()`**. `tostring()` writes XML and ignores the stylesheet's
`xsl:output method="html"`, self-closing empty `<span/>` / `<a/>` / `<ul/>`, which browsers read as unclosed start tags
that swallow the rest of the page. That was the real cause of the a0022b8 "text shown as hyperlinks" workaround in the
stylesheet.

Every failure raises `DefineHtmlGenerationError`; nothing returns an empty result or writes nothing silently. A
destination that can't be written (the output check, or the write itself) raises its subclass `DefineHtmlWriteError`,
so a caller can tell "couldn't write there" from "couldn't render"; defineview falls back to the temp folder on it.
- XSLT errors carry the distinct `error_log` messages, because `str(XSLTApplyError)` can be one word (`'first'`).
- Input must have an ODM v1.3 root and a MetaDataVersion with the v2.1 `def:DefineVersion`. The stylesheet binds `def:`
  to the v2.1 namespace, so other input would otherwise render without error but with most of its content missing.
- `transform_to_html_file()` checks the destination before transforming, and refuses one that is the input
  (`samefile`).

Before serializing, `_neutralize_unsafe_links()` turns each `<a href>` into a `<span>` unless its scheme is relative,
`http`, `https`, `file` or a one-letter Windows drive, since hrefs are copied verbatim from `def:leaf/@xlink:href` and
`ExternalCodeList/@href`.

`absolute_links=True` (not a stylesheet option, and not a CLI flag) then has `_absolutize_links()` resolve each
relative `<a href>` against the define.xml's folder as a `file:` URL, for HTML saved elsewhere. Fragment-only links
(`#IG.AE`) and links with a scheme are left alone. Don't replace it with a `<base href>`: that would also redirect the
page's many `#fragment` links. The stylesheet emits links only as `<a href>`. The folder comes from `os.path.abspath`,
not `resolve()`, which turns a mapped network drive into its UNC path.

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
`DefineRefCheckError`, whose load-failure message recommends `definevalidate`. This module bundles no resources
and sets exit codes (0 clean, 1 errors, 2 could not check).

**metrics module**: Uses odmlib to load the define.xml into the `define_2_1` model and report file/study identity,
a count for every element type, and a per-dataset table. `DefineMetrics.collect()` returns a `MetricsResult` cached on
`self._result`; `collect_to_string()` / `_to_file()` / `_to_console()` / `_to_json()` all reuse it. Raises
`DefineMetricsError`, reusing definerefs' load-failure wording (recommends `definevalidate`, and suggests
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
`main()` re-raises `BrokenPipeError` ahead of its `except Exception`, so quitting a pager still exits 0 in `run()`.

**defineview module**: What double-clicking a define.xml runs on Windows, once the user has chosen defineview.exe
for it with "Open with" (README.md has the user's steps; there is no installer or registry code). `DefineViewer`
renders with `DefineHtml`, writes the HTML and `open_in_browser()` opens it with `webbrowser`.
- **Where the HTML goes:** beside the define.xml as `<stem>.html` by default (relative links, byte-identical to
  definehtml's), replacing any file there. On `DefineHtmlWriteError` it falls back to `temp_folder`,
  `<tempfile.gettempdir()>/defineutils/<12 hex of the define path's sha256>/`, rendering again with
  `absolute_links=True`. `--temp` always uses it; `-o` writes where it is told. HTML outside the define.xml's folder
  always gets absolute links.
- **Failures:** a `DefineHtmlGenerationError` writes `<stem>.error.html` to `temp_folder`, never beside the define.xml,
  and opens it (exit 2). An unexpected exception does the same with the traceback (exit 1). Both also go to stderr when
  there is one.
- **The path is positional:** "Open with" passes only `"%1"`, so the command can't need `-d` or any option.
- **No console on Windows:** the spec builds it windowed there, and pip installs it as a GUI script, so `sys.stdout`
  and `sys.stderr` can be `None`. Never report only to stderr: a problem goes on a page, or through `tell_user()`,
  which shows a `MessageBoxW` when there is no stderr. `parse_args()` captures argparse's output (help, `--version`,
  usage errors) for the same reason. A message box waits for a click, so `run_cli` has a timeout (`CLI_TIMEOUT`) and
  CLI tests of defineview check exit codes and files, not output. Starting defineview with no path shows the help.
- **Never open an `.xml` through the OS** (`webbrowser`, `os.startfile`): when defineview is the `.xml` default, that
  starts defineview again. The error page links to the file instead, and the browser follows that link itself.
- **Tests that patch `sys.stdout` / `sys.stderr`** must do it in the test body: pytest's capturing sets both again
  after the fixtures run.
- macOS double-click needs a `.app` bundle (PyInstaller `BUNDLE`, `argv_emulation`); deferred, see `SIMPLE_LOAD.md`.

The definehtml and validate modules bundle their required resources (XSL stylesheet, XSD schemas) to simplify usage.
