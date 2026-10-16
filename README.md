# defineutils

## CDISC Define-XML v2.1 utilities

The defineutils package currently includes 7 modules:
1. `definehtml.py`: transforms a define.xml into a define.html using the stylesheet
2. `validate.py`: schema validates a define.xml file
3. `definepp.py`: pretty-prints (re-indents) a define.xml file
4. `definerefs.py`: checks the OID reference/definition integrity of a define.xml file
5. `metrics.py`: reports metrics for a define.xml file
6. `defineview.py`: renders a define.xml with definehtml and opens it in the default browser
7. `conformance.py`: checks a define.xml against the CDISC Define-XML v2.1 conformance rules

The `definehtml.py` module includes the Define-XML v2.1 style sheet to simplify usage. It generates a define.html file,
or alternatively returns the HTML as a string. It renders Define-XML v2.1 only: a file in another Define-XML version,
or one that is not well-formed, is refused with an error that recommends running definevalidate, rather than rendered
with content silently missing. Links in the define.xml that use a scheme other than http, https or file (such as
`javascript:`) are shown as text rather than as links. The stylesheet's display options are available as arguments:
the Comments table, the Methods table, `[Comment]`/`[Method]`/`[Origin]` prefixes, the Length / Significant Digits /
Display Format column, and how many codelist terms are listed in the Controlled Terms column.

The `validate.py` module includes the Define-XML v2.1 schema to simplify usage. It schema validates a define.xml file
and reports every schema validation error it finds, not just the first one. Errors that say the same thing about the
same kind of element are grouped into one finding that lists each place it occurs, with a line number, so a file with
hundreds of errors reads as a manageable list of distinct problems. The report can be printed to the console, written
to a text file, or emitted as JSON. The bundled schema is the default, but any schema file can be used instead -- the
`-s` command-line parameter, or the `xsd_file` argument in code -- to validate against a different Define-XML version.

The `definepp.py` module pretty-prints a define.xml file. The reformat is byte-preserving apart from whitespace:
comments, processing instructions, element/attribute order and namespaces are all retained. It writes the formatted
define.xml to a file, or, if no output file is given, to the console where it can be paged with a tool like `more`.

The `definerefs.py` module checks the OID reference/definition integrity of a define.xml file and prints a formatted
listing of everything it finds: references to OIDs nothing defines, references that resolve to the wrong kind of
element, duplicate OIDs, and definitions nothing references. It also checks the Define-XML document leaves
(`def:leaf`) and the `def:ArchiveLocationID` / `leafID` references to them. Errors and warnings are listed together
with the location of each occurrence; the report can be written to the console, to a file, or as JSON.

The `metrics.py` module reports what is in a define.xml: its size and creation date, the study and metadata version it
describes, the CDISC standards it references, a count of every element, and a per-dataset table with the number of
variables in each. The element list is derived from the Define-XML v2.1 model rather than hand-maintained, so an
element the file does not use is reported as 0 instead of being left out -- a define.xml with no `MethodDef` at all
says so. The report can be printed to the console, written to a text file, or emitted as JSON.

The `defineview.py` module shows a define.xml in the browser: it writes the HTML beside the define.xml and opens it in
the default browser, or opens a page saying why the file could not be shown. On Windows, choosing defineview once to
open define.xml files lets a double-click on a define.xml show it in the browser; see
[Opening a define.xml with a double-click](#opening-a-definexml-with-a-double-click-windows).

The `conformance.py` module checks a define.xml against the 225 published CDISC Define-XML v2.1 conformance rules and
reports each failure under its CDISC rule id, with the rule text and the line and path of every occurrence. It
answers the question a reviewer asks -- which rules does this define.xml break, and where? -- in one report: the 210
rules that can be decided from the document itself are evaluated, the 13 that apply only in the context of a
submission are evaluated when the document declares `def:Context="Submission"`, and the 15 that need published CDISC
controlled terminology, implementation-guide metadata or the datasets are listed as not evaluated, so the report
accounts for every rule. The rules are evaluated on the XML directly, so a non-conformant file does not need a
permissive mode to be checked. The report can be printed to the console, written to a text file, or emitted as JSON.

## Installing defineutils

There are three ways to get defineutils:
- pip, for Python users and for the Python code described in [Using defineutils](#using-defineutils);
- uv, for the commands only, without installing Python yourself;
- a download of the commands for Windows or macOS, ready to run, with nothing to install.

defineutils needs Python 3.10 or later. Install it with pip:

```commandline
pip install defineutils
```

Installing adds seven commands -- definehtml, definevalidate, definepp, definerefs, definemetrics, defineconform and
defineview -- described in
[Running defineutils from the Command-line](#running-defineutils-from-the-command-line).

If you only need the commands and do not have Python, [uv](https://docs.astral.sh/uv/getting-started/installation/)
installs them in one step, downloading a suitable Python for them if none is found. Install uv, then run:

```commandline
uv tool install defineutils
```

If the commands are not found afterwards, `uv tool update-shell` adds their folder to your PATH; open a new terminal
to pick it up. `uv tool upgrade defineutils` installs a newer release later.

### Downloading the commands for Windows or macOS

The seven commands are also built as programs that run without Python. Download the zip for your computer from the
[latest release](https://github.com/swhume/defineutils/releases/latest):

| Computer | Download |
|---|---|
| Windows, 64-bit (x64) | `defineutils-<version>-windows-x64.zip` |
| Mac with Apple silicon (M1 or later) | `defineutils-<version>-macos-arm64.zip` |

On Linux or an Intel Mac, install with uv or pip instead.

The zip holds a defineutils folder with the seven commands, the _internal folder they need to run, a README.txt and a
LICENSES folder. Keep _internal beside the commands. The commands are not code-signed, so Windows and macOS warn about
them:
- **Windows**: before unzipping, right-click the downloaded zip, choose Properties, tick Unblock and click OK. If
  "Windows protected your PC" still appears, choose More info, then Run anyway.
- **macOS**: after unzipping, remove the download quarantine from the folder once, in Terminal. Type the command below
  without its path, drag the defineutils folder onto the Terminal window to add the path, and press Return:
  ```commandline
  xattr -dr com.apple.quarantine /path/to/defineutils
  ```

To run a command, open a terminal in the defineutils folder (on Windows, PowerShell or Command Prompt; on macOS,
Terminal) and type its name with `.\` in front on Windows or `./` on macOS:

```commandline
# Windows
.\definehtml -d C:\studies\define.xml

# macOS
./definehtml -d ~/studies/define.xml
```

To run the commands from any folder without the `.\` or `./`, add the defineutils folder to your PATH; README.txt in the
folder explains how. The commands work as described in
[Running defineutils from the Command-line](#running-defineutils-from-the-command-line). To update, download the zip
from the newer release and replace the folder. The download holds only the commands; the Python code needs pip.

### Opening a define.xml with a double-click (Windows)

defineview renders a define.xml and opens it in your default browser. Choose it once to open define.xml files, and a
double-click on a define.xml shows it in the browser, with no terminal and no console window:

1. Keep the defineutils folder where it will stay, for example `%LOCALAPPDATA%\Programs\defineutils`, unblocking the
   zip first as above. Windows remembers where defineview.exe is, so to update, replace the folder's contents rather
   than unzipping the new release somewhere else.
2. Right-click a define.xml, choose Open with, then Choose another app. Choose "Choose an app on your PC" (on Windows
   10, More apps, then "Look for another app on this PC") and select defineview.exe in the defineutils folder.
3. Windows asks whether to use defineview just once or always (on Windows 10, with the "Always use this app to open
   .xml files" box):
   - **Just once** leaves .xml files opening as they do now, and keeps defineview in the Open with menu for next time.
   - **Always** makes a double-click open every .xml file with defineview. An XML file that is not a Define-XML v2.1
     file gets a page saying so, with a link that shows it as plain XML in the browser.

defineview writes the HTML beside the define.xml, as define.html for define.xml, replacing any file of that name, so
the page's links to the datasets and documents in that folder work. When it can't write there, such as on a read-only
share, it writes the HTML to your temp folder instead, with links that still point to the define.xml's folder. When a
define.xml can't be shown, because it is not well-formed or not Define-XML v2.1, a page in the browser says why.

To use the temp folder every time, so that nothing is written beside the define.xml:
- make a shortcut to defineview.exe, add ` --temp` to the end of the Target in the shortcut's Properties, and drop
  define.xml files onto the shortcut;
- to have it in the right-click Send to menu as well, move the shortcut to the Send to folder: type `shell:sendto` in
  File Explorer's address bar to open it.

To stop .xml files opening with defineview, open Settings > Apps > Default apps, find .xml, and choose another app.

If you installed defineutils with pip or uv rather than downloading it, choose the defineview.exe they installed
in step 2; in PowerShell, `(Get-Command defineview).Source` shows where it is. On a Mac, run defineview in Terminal for
now (`./defineview ~/studies/define.xml`); opening a define.xml with a double-click is not available there yet.

## Using defineutils

Currently, defineutils contains 7 modules: one for generating an HTML rendition, one for schema validation, one
for pretty-printing, one for OID reference/definition checking, one for reporting metrics, one that opens a
define.xml in the browser, and one that checks the CDISC conformance rules.

Example code used to generate a define.html from a define.xml:
```python
from pathlib import Path
from defineutils.definehtml import DefineHtml, DefineHtmlGenerationError

out_file = Path(__file__).parent.joinpath("define.html")
try:
    dh = DefineHtml(Path(__file__).parent.joinpath("define.xml"))
    dh.transform_to_html_file(out_file)
except DefineHtmlGenerationError as e:
    print(e)

# or get the HTML as a string, here with the Comments table added
html = DefineHtml(Path(__file__).parent.joinpath("define.xml"), comments_table=True).transform_to_html_string()
```

The above code applies the Define-XML v2.1 stylesheet to the define.xml to generate the define.html file. The
stylesheet is embedded in the module. Every failure raises the custom DefineHtmlGenerationError exception: a missing,
unreadable or malformed define.xml, a file that is not Define-XML v2.1, a stylesheet error, or an output file that
cannot be written or that is the input define.xml itself; the last two raise its subclass DefineHtmlWriteError.
`transform_to_html_string()` returns a `str`. The display options are keyword arguments to `DefineHtml`:
`codelist_items` (default 5), `methods_table` (default True), `comments_table`, `prefixes` and `length_format` (default
False). For HTML saved in a different folder from the define.xml, `absolute_links=True` rewrites the links to datasets
and documents as `file:` URLs pointing to the define.xml's folder, so they still work.

Example code used to schema validate a define.xml:
```python
from pathlib import Path
from defineutils.validate import DefineSchemaValidator, DefineSchemaValidationError

validator = DefineSchemaValidator(Path(__file__).parent.joinpath("define.xml"))
try:
    result = validator.validate_define_file()
except DefineSchemaValidationError as e:
    print(e)
```

The above code schema validates the specified define.xml file. The Define-XML v2.1 schema is embedded into the module.
`validate_define_file()` is the quick check: it returns a message when the file is valid and otherwise raises
DefineSchemaValidationError describing the **first** error found.

To collect every error instead, use `validate()` and the report methods:
```python
from defineutils.validate import DefineSchemaValidator

validator = DefineSchemaValidator("define.xml")
result = validator.validate()
print(f"{result.error_count} errors in {len(result.findings)} distinct problems")
for finding in result.findings:
    print(finding.check, finding.element, finding.reason)
    for location in finding.locations:
        print("   line", location.line, location.path)

validator.validate_to_console()                       # the formatted listing
validator.validate_to_file("report.txt")              # the same listing, saved
validator.validate_to_file("report.json", as_json=True)
report = validator.validate_to_json()                 # JSON string
```

`validate()` returns a ValidationResult carrying `error_count` (raw errors), `findings` (after grouping), and the
`is_valid` / `has_errors` flags. Each Finding has a `check` id (`unexpected_child`, `incomplete_content`,
`invalid_value`, `attribute_error` or `schema_validation`), the `element` it was found on, the `reason` as the schema
validator phrased it, and a `locations` list of path/line pairs. The result is cached, so the report methods do not
re-parse the file. The text listing shows the first 5 locations per finding by default; JSON always includes all of
them.

To validate against a different version of the schema, pass its file path as the `xsd_file` argument:
```python
validator = DefineSchemaValidator(Path(__file__).parent.joinpath("define.xml"),
                                  xsd_file=Path("cdisc-define-2.0").joinpath("define2-0-0.xsd"))
```

A schema that cannot be loaded, and a define.xml that cannot be read or parsed, raise DefineSchemaLoadError. It is a
subclass of DefineSchemaValidationError, so code that catches the latter catches both; catch it separately to tell a
check that could not be run from a define.xml that is genuinely invalid.

Example code used to pretty-print a define.xml:
```python
from pathlib import Path
from defineutils.definepp import DefinePrettyPrinter, DefinePrettyPrintError

pp = DefinePrettyPrinter(Path(__file__).parent.joinpath("define.xml"))
try:
    pp.pretty_print_to_file(Path(__file__).parent.joinpath("define.pretty.xml"))
except DefinePrettyPrintError as e:
    print(e)
```

The above code re-indents the define.xml and writes the formatted result to define.pretty.xml. Use
`pretty_print_to_string()` to get the formatted XML as a string, or `pretty_print_to_console()` to write it to
stdout. Errors, including malformed XML, are reported via the DefinePrettyPrintError exception.

Example code used to check the OID references and definitions in a define.xml:
```python
from pathlib import Path
from defineutils.definerefs import DefineRefChecker, DefineRefCheckError

checker = DefineRefChecker(Path(__file__).parent.joinpath("define.xml"))
try:
    result = checker.check()
    print(f"{len(result.errors)} errors, {len(result.warnings)} warnings")
    checker.check_to_console()
except DefineRefCheckError as e:
    print(e)
```

The above code loads the define.xml with odmlib and reports every OID problem it finds. `check()` returns a
RefCheckResult with the `findings`, `errors`, `warnings` and `has_errors` properties, plus the definition and
reference counts and a record of which reference attributes were checked and which were skipped. Each finding names
the check, the OID, the reference attribute, the expected and actual element types, and every location the problem
occurs at. Use `check_to_string()` for the formatted listing, `check_to_file()` to write it to a file,
`check_to_console()` to print it, and `check_to_json()` for machine-readable results. A define.xml that will not load
into the Define-XML v2.1 model cannot be checked at all, so that failure is reported via the DefineRefCheckError
exception with a recommendation to run definevalidate first. Pass `permissive=True` to attempt a best-effort
check of a non-conformant file anyway.

Example code used to report the metrics for a define.xml:
```python
from pathlib import Path
from defineutils.metrics import DefineMetrics, DefineMetricsError

metrics = DefineMetrics(Path(__file__).parent.joinpath("define.xml"))
try:
    result = metrics.collect()
    print(f"{result.total_elements} elements, {len(result.datasets)} datasets")
    print(f"{result.count('ItemDef')} item definitions, {result.count('MethodDef')} methods")
    metrics.collect_to_console()
except DefineMetricsError as e:
    print(e)
```

The above code loads the define.xml with odmlib and collects its metrics. `collect()` returns a MetricsResult carrying
the file size and modified time, the `creation_datetime` the document declares, the study and metadata version
identifiers, the `standards` it references, an `elements` list holding a count for every element type the Define-XML
v2.1 model defines, and a `datasets` list holding one entry per ItemGroupDef with its variable count. The
`total_elements`, `element_types`, `element_types_present`, `element_types_absent` and `total_variable_refs`
properties give the totals, and `count("ItemDef")` looks up a single element count by name. The result is cached, so
the report methods do not re-parse the file. Use `collect_to_string()` for the formatted report,
`collect_to_file()` to write it to a file, `collect_to_console()` to print it, and `collect_to_json()` for
machine-readable results; pass `show_datasets=False` to leave the per-dataset table out of the text report. A
define.xml that will not load into the Define-XML v2.1 model is reported via the DefineMetricsError exception with a
recommendation to run definevalidate first; pass `permissive=True` to collect best-effort metrics from a
non-conformant file anyway.

Note that the element counts are per element type across the whole document, so the ItemRef count includes both the
dataset variables and the value-level ItemRefs under each def:ValueListDef. The `Variables` column in the dataset
table, and the `total_variable_refs` property, count only the ItemRefs belonging to an ItemGroupDef.

Example code used to check a define.xml against the Define-XML v2.1 conformance rules:
```python
from pathlib import Path
from defineutils.conformance import DefineConformanceChecker, DefineConformanceError

try:
    checker = DefineConformanceChecker(Path(__file__).parent.joinpath("define.xml"))
    checker.check_to_console()
    for finding in checker.check().findings:
        print(finding.rule, finding.element, len(finding.locations))
except DefineConformanceError as e:
    print(e)
```

The above code loads the define.xml with lxml and evaluates every conformance rule against it. `check()` returns a
ConformanceResult: `findings` holds one Finding per failed rule, in ascending rule id order, each carrying the CDISC
`rule` id, the `element` and `attribute` it is about, the rule text as its `message`, the published CDISC
`cdisc_message`, and a Location per occurrence with the OID-decorated `path`, the source `line` and a one-sentence
`detail` saying what is wrong there; `passed`, `not_applicable` (the Submission-only rules, when the document is not a
submission) and `not_evaluated` (the rules that need CDISC controlled terminology, implementation-guide metadata or the
datasets, with the reason) account for the rest of the 225. The `has_errors`, `occurrence_count` and
`evaluated_count` properties summarise it. The result is cached, so the report methods do not re-parse the file. Use
`check_to_string()` for the formatted listing, `check_to_file()` to write it to a file, `check_to_console()` to print
it, and `check_to_json()` for machine-readable results; pass `rules=["73", "110"]` to evaluate a subset, or
`skip_rules=[...]` to leave rules out, and `DefineConformanceChecker.all_rules()` lists the registry with each
rule's text. A file that is missing, not well-formed or a Define-XML 2.0 document is reported via the
DefineConformanceLoadError exception, a subclass of DefineConformanceError.

## Running defineutils from the Command-line

Installing defineutils, or downloading the commands, gives a command for each module:

| Command | Module | What it does |
|---|---|---|
| `definehtml` | `defineutils.definehtml` | transforms a define.xml into a define.html |
| `definevalidate` | `defineutils.validate` | schema validates a define.xml |
| `definepp` | `defineutils.definepp` | pretty-prints a define.xml |
| `definerefs` | `defineutils.definerefs` | checks the OID references and definitions in a define.xml |
| `definemetrics` | `defineutils.metrics` | reports the metrics for a define.xml |
| `defineconform` | `defineutils.conformance` | checks a define.xml against the Define-XML v2.1 conformance rules |
| `defineview` | `defineutils.defineview` | shows a define.xml in the default browser |

Each command does the same as running its module with Python's -m switch, so `definehtml -d tests/define.xml` and
`python3 -m defineutils.definehtml -d tests/define.xml` are equivalent; the downloaded commands behave the same, with
no Python needed. Every command takes --help to list its parameters and --version to show the defineutils version.

The definehtml command transforms a define.xml file into HTML using the stylesheet. It uses the required -d parameter
to specify the define.xml file path and the optional -o to specify the define.html file path; without -o the HTML is
written beside the define.xml with an .html extension (tests/define.html below). The display options are
--comments-table, --no-methods-table, --prefixes, --length-format and --codelist-items N. The exit code is 0 when the
HTML was written, 2 when it was not (the message is printed to stderr), and 1 for an unexpected error.

```commandline
definehtml -d tests/define.xml -o tests/define.html

# write tests/define.html, including the Comments table
definehtml -d tests/define.xml --comments-table
```

The defineview command renders a define.xml with the stylesheet's default options and opens it in the default
browser. The define.xml is given without -d, since that is how Windows passes a file to the program that opens it. The
HTML is written beside the define.xml, as definehtml does without -o, or to the temp folder when that fails; --temp
always uses the temp folder, and -o writes to the given file. HTML written outside the define.xml's folder has its links
to datasets and documents pointed back to that folder. --no-open writes the HTML without opening the browser. The exit
code is 0 when the page was opened, 2 when the define.xml could not be shown (a page saying why is opened instead), and
1 for an unexpected error. On Windows defineview has no console window: it shows a problem that has no page to go on,
and its --help and --version, in a message box.

```commandline
defineview tests/define.xml

# write the HTML to the temp folder rather than beside the define.xml
defineview --temp tests/define.xml
```

The definevalidate command schema validates a define.xml. Only the -d parameter is required, to indicate the file
path of the define.xml to validate. The -s parameter is optional and gives the file path
of the schema to validate against; without it the bundled Define-XML v2.1 schema is used. Without -o the formatted
listing goes to the console; with -o it is written to the given file. The --json switch emits machine-readable results
instead of the listing, and -L sets how many example locations are shown per finding (0 shows all).

```commandline
# validate against the bundled Define-XML v2.1 schema
definevalidate -d tests/define.xml

# validate against a different version of the schema
definevalidate -d tests/define.xml -s cdisc-define-2.0/define2-0-0.xsd

# save the listing to a file
definevalidate -d tests/define.xml -o validation_report.txt

# machine-readable results for CI or other tooling
definevalidate -d tests/define.xml --json

# show every location of every error, rather than the first 5 per finding
definevalidate -d tests/define.xml -L 0
```

The listing names the file and the schema, then each distinct problem with the places it occurs:

```
Define-XML schema validation
  File:   tests/define.xml
  Schema: defineutils/validate/schema/cdisc-odm-1.3.2/ODM1-3-2.xsd
  Scope:  401 errors in 110 distinct problems

ERRORS (110)

  unexpected_child  ItemDef   (108 occurrences)
      Unexpected child with tag 'def:Origin' at position 2.
      - line 782  MetaDataVersion[MDV.CDISC01_1]/ItemDef[IT.DM.AGE]
      - line 789  MetaDataVersion[MDV.CDISC01_1]/ItemDef[IT.DM.AGEU]
      ... and 106 more

SUMMARY
  401 errors in tests/define.xml
  Schema: defineutils/validate/schema/cdisc-odm-1.3.2/ODM1-3-2.xsd
```

definevalidate sets an exit code so it can gate a CI job: 0 when the define.xml is valid, 1 when it is invalid, and 2 when
the validation could not be run at all -- the schema would not load, the define.xml could not be read or parsed, or the
report could not be written. The report is written to stdout and the failure messages to stderr, so a redirected report
stays clean.

The definepp command pretty-prints a define.xml. Use the -d parameter to specify the define.xml file path and the -o
parameter to specify the formatted output file path. If no -o is given, the formatted define.xml is written to the
console, which can be paged with a tool like `more`. When printing to the console, the -H parameter limits the number
of lines shown.

```commandline
# write the formatted define.xml to a file
definepp -d tests/define.xml -o tests/define.pretty.xml

# print the formatted define.xml to the console, one screen at a time
definepp -d tests/define.xml | more

# print only the first 40 lines to the console
definepp -d tests/define.xml -H 40
```

The definerefs command checks the OID references and definitions in a define.xml. Use the -d parameter to specify
the define.xml file path. Without -o the formatted listing goes to the console; with -o it is written to the given
file. The --json switch emits machine-readable results instead of the listing, --errors-only suppresses the orphan
definition warnings, -L sets how many example locations are shown per finding (0 shows all), and --permissive
attempts a best-effort check of a define.xml that is not conformant enough to load normally.

```commandline
# print the listing to the console
definerefs -d tests/define.xml

# save the listing to a file
definerefs -d tests/define.xml -o refdef_report.txt

# machine-readable results for CI or other tooling
definerefs -d tests/define.xml --json

# errors only, with every location listed
definerefs -d tests/define.xml --errors-only -L 0

# best-effort check of a non-conformant define.xml
definerefs -d broken_define.xml --permissive
```

definerefs sets an exit code, like definevalidate, so it can gate a CI job: 0 when there are no errors (a clean
define.xml, or one that only has orphan definition warnings), 1 when there are errors (dangling references,
duplicate OIDs or type mismatches), and 2 when the check could not be run at all -- the define.xml would not load,
or the report could not be written. A file that will not load is reported with a recommendation to run definevalidate
to find out why.

The definemetrics command reports what is in a define.xml. Use the -d parameter to specify the define.xml file path.
Without -o the report goes to the console; with -o it is written to the given file. The --json switch emits
machine-readable results instead of the report, --no-datasets leaves the per-dataset table out, and --permissive
collects best-effort metrics from a define.xml that is not conformant enough to load normally.

```commandline
# print the report to the console
definemetrics -d tests/define.xml

# save the report to a file
definemetrics -d tests/define.xml -o metrics_report.txt

# machine-readable results for CI or other tooling
definemetrics -d tests/define.xml --json

# the counts and totals without the per-dataset table
definemetrics -d tests/define.xml --no-datasets

# best-effort metrics for a non-conformant define.xml
definemetrics -d broken_define.xml --permissive
```

The report names the file and the study, then the element counts and the datasets:

```
Define-XML metrics
  File:     tests/define.xml
  Size:     174,322 bytes (170.2 KiB)
  Created:  2024-11-21T16:27:00  (ODM/@CreationDateTime)
  Modified: 2025-03-28T14:05:08  (file system)
  Model:    Define-XML v2.1 (odmlib define_2_1, odmlib 0.2.0)

STUDY
  Study name:        CDISC01_1
  Protocol name:     CDISC01-1
  Description:       CDISC Test Study Modified to illustrate Define-XML 2.1 features
  Study OID:         STDY.www.cdisc.org.CDISC01_1
  MetaDataVersion:   MDV.CDISC01_1.1.SDTMIG.3.1.2.SDTM.1.2_X
                     Study CDISC01_1, Data Definitions V-1
  Define version:    2.1.9
  Standards (6):     SDTMIG 3.1.2 IG (Final), SDTMIG 3.2 IG (Final), SDTMIG-MD 1.0 IG (Final),
                     CDISC/NCI SDTM 2011-12-09 CT (Final), CDISC/NCI SDTM 2015-12-18 CT (Final),
                     CDISC/NCI DEFINE-XML 2025-03-28 CT (Final)

ELEMENT COUNTS
  MetaDataVersion definitions
    def:Standards          1
    def:AnnotatedCRF       0
    def:ValueListDef       8
    ItemGroupDef          11
    ItemDef              179
    CodeList              40
    MethodDef             33
    def:leaf              12

DATASETS (11)
  OID        Name    Class            Repeating  No data  Variables
  IG.TS      TS      TRIAL DESIGN     No         -                6
  IG.DM      DM      SPECIAL PURPOSE  No         -               16
  IG.XX      XX      FINDINGS         Yes        Yes             17
                                                 Total          155

SUMMARY
  2,090 elements across 39 element types (37 present, 2 absent)
  11 datasets, 155 variable references, 179 item definitions, 40 code lists, 33 methods
```

`def:AnnotatedCRF 0` above is the point of the model-derived element list: this define.xml has no annotated CRF, and
the report says so rather than staying silent about it.

definemetrics sets an exit code: 0 when the report was produced, and 2 when it could not be -- the define.xml is
missing or would not load, or the report could not be written. 1 means only that an unexpected error occurred, and its
traceback is printed to stderr. Unlike definevalidate and definerefs, definemetrics never exits 1 to judge the
define.xml, because a metrics report describes a define.xml rather than judging it.

The defineconform command checks a define.xml against the CDISC Define-XML v2.1 conformance rules. Use the -d
parameter to specify the define.xml file path. Without -o the listing goes to the console; with -o it is written to
the given file. The --json switch emits machine-readable results instead of the listing, -L sets how many example
locations are shown per finding (0 shows all), --rules evaluates only the given rule ids and --skip-rules leaves
rule ids out, and --list-rules prints the 225 rules, one per line, without checking a file.

```commandline
# print the listing to the console
defineconform -d tests/define.xml

# save the listing to a file
defineconform -d tests/define.xml -o conformance_report.txt

# machine-readable results for CI or other tooling
defineconform -d tests/define.xml --json

# two rules only, with every location listed
defineconform -d tests/define.xml --rules 73,159 -L 0

# every rule but these
defineconform -d tests/define.xml --skip-rules 153,249

# the rules themselves: id, how each is evaluated, element/attribute, source, versions and text
defineconform --list-rules
```

The listing names the file, its Define-XML version and context, then each failed rule with its CDISC id, the rule text
and the line and path of each occurrence, and accounts for the rules that were not evaluated:

```
Define-XML conformance check
  File:     tests/define.xml
  Version:  Define-XML 2.1.9    Context: Other
  Rules:    CDISC Define-XML v2.1 Conformance Rules (225)

ERRORS (5 rules, 55 occurrences)

  [73]   ItemRef/@MethodOID   (2 occurrences)
         The MethodOID attribute must be provided on the  ItemRef element when the Origin Type attribute on the corresponding ItemDef element is "Derived".
         - line 556  MetaDataVersion[MDV.CDISC01_1.1.SDTMIG.3.1.2.SDTM.1.2_X]/ItemGroupDef[IG.EC]/ItemRef[IT.EC.EXDOSE]: ItemDef IT.EC.EXDOSE has def:Origin/@Type="Derived" but the ItemRef has no @MethodOID
         - line 557  MetaDataVersion[MDV.CDISC01_1.1.SDTMIG.3.1.2.SDTM.1.2_X]/ItemGroupDef[IG.EC]/ItemRef[IT.EC.EXDOSU]: ItemDef IT.EC.EXDOSU has def:Origin/@Type="Derived" but the ItemRef has no @MethodOID

  [153]  CodeList/@def:IsNonStandard   (11 occurrences)
         Attribute def:IsNonStandard must be provided for a CodeList element where CDISC Controlled Terminology is required and there is no Alias provided.
         - line 2133  MetaDataVersion[MDV.CDISC01_1.1.SDTMIG.3.1.2.SDTM.1.2_X]/CodeList[CL.ARM]: @def:IsNonStandard is missing, but the CodeList has no Alias[@Context="nci:ExtCodeID"]
         - line 2139  MetaDataVersion[MDV.CDISC01_1.1.SDTMIG.3.1.2.SDTM.1.2_X]/CodeList[CL.ARMCD]: @def:IsNonStandard is missing, but the CodeList has no Alias[@Context="nci:ExtCodeID"]
         ... and 9 more

  [159]  def:Origin/@Type   (30 occurrences)
         ItemDef which has a def:Origin element with Type = 'Collected' must have a reference to a document which corresponds to AnnotatedCRF
         - line 815  MetaDataVersion[MDV.CDISC01_1.1.SDTMIG.3.1.2.SDTM.1.2_X]/ItemDef[IT.DM.BRTHDTC]/def:Origin: is @Type="Collected" with @Source="Investigator", but the document has no def:AnnotatedCRF to reference
         - line 840  MetaDataVersion[MDV.CDISC01_1.1.SDTMIG.3.1.2.SDTM.1.2_X]/ItemDef[IT.DM.ETHNIC]/def:Origin: is @Type="Collected" with @Source="Investigator", but the document has no def:AnnotatedCRF to reference
         ... and 28 more

  [240]  ItemGroupDef/@def:CommentOID   (1 occurrence)
         The def:CommentOID attribute must be provided when the value of the ItemGroupDef def:HasNoData attribute is "Yes".
         - line 759  MetaDataVersion[MDV.CDISC01_1.1.SDTMIG.3.1.2.SDTM.1.2_X]/ItemGroupDef[IG.SUPPVS]: @def:CommentOID is missing, but @def:HasNoData is "Yes"

  [249]  Alias/@Context   (11 occurrences)
         There must be an Alias element with the Context Attribute nci:ExtCodeID when the Codelist includes a reference to a CDISC Controlled Terminology Standard.
         - line 2133  MetaDataVersion[MDV.CDISC01_1.1.SDTMIG.3.1.2.SDTM.1.2_X]/CodeList[CL.ARM]: has no Alias[@Context="nci:ExtCodeID"], but @def:StandardOID is present
         - line 2139  MetaDataVersion[MDV.CDISC01_1.1.SDTMIG.3.1.2.SDTM.1.2_X]/CodeList[CL.ARMCD]: has no Alias[@Context="nci:ExtCodeID"], but @def:StandardOID is present
         ... and 9 more

NOT APPLICABLE (13 rules)
  Require ODM/@def:Context="Submission"; this document declares "Other":
  31, 70, 93, 96, 108, 119, 125, 128, 131, 147, 154, 168, 176

NOT EVALUATED (15 rules)
  Need CDISC controlled terminology:      179, 186, 187, 192, 201, 202
  Need implementation-guide metadata:     67, 97, 98, 99, 149, 263, 265, 266
  Need the datasets:                      76

SUMMARY
  225 rules: 197 evaluated, 192 passed, 5 failed (55 occurrences), 13 not applicable, 15 not evaluated
  File: tests/define.xml
```

The listing above was produced with `-L 2`. The CDISC sample above declares `def:Context="Other"`, so the 13
submission-only rules are not applicable to it; a define.xml that declares `Submission` has them evaluated too, as
tests/define-adam.xml does.

defineconform sets an exit code, like definevalidate and definerefs, so it can gate a CI job: 0 when no rule failed,
1 when at least one rule failed, 2 when the check could not be run at all -- the define.xml is missing, not
well-formed or a Define-XML 2.0 document, a rule id is unknown, or the report could not be written -- and 3 when an
unexpected error occurred, with its traceback printed to stderr, so a crash is never mistaken for a failed check.

If you are running defineutils from the source code, install it into a virtual environment in editable mode to create
the commands, and activate that environment before running them. Re-run the install after the version or the commands
change. Without installing, the `python3 -m` form works from the root of the source tree.

```commandline
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
definevalidate -d tests/define.xml
```
