# defineutils

## CDISC Define-XML v2.1 utilities

The defineutils package currently includes 5 modules:
1. `definehtml.py`: transforms a define.xml into a define.html using the stylesheet
2. `validate.py`: schema validates a define.xml file
3. `definepp.py`: pretty-prints (re-indents) a define.xml file
4. `definerefs.py`: checks the OID reference/definition integrity of a define.xml file
5. `metrics.py`: reports metrics for a define.xml file

The `definehtml.py` module includes the Define-XML v2.1 style sheet to simplify usage. It generates a define.html file,
or alternatively will generate an HTML string.

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

## Using defineutils

Currently, defineutils contains 5 modules: one for generating an HTML rendition, one for schema validation, one
for pretty-printing, one for OID reference/definition checking, and one for reporting metrics.

Example code used to generate a define.html from a define.xml:
```python
from pathlib import Path
from defineutils.definehtml import DefineHtml, DefineHtmlGenerationError

out_file = Path(__file__).parent.joinpath("define.html")
dh = DefineHtml(Path(__file__).parent.joinpath("define.xml"))
dh.transform_to_html_file(out_file)
```

The above code applies the Define-XML v2.1 stylesheet to the define.xml to generation the define.html file. The 
stylesheet is embedded in the module. For error handling, use the custom DefineHtmlGenerationError exception.

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
exception with a recommendation to run the validate module first. Pass `permissive=True` to attempt a best-effort
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
recommendation to run the validate module first; pass `permissive=True` to collect best-effort metrics from a
non-conformant file anyway.

Note that the element counts are per element type across the whole document, so the ItemRef count includes both the
dataset variables and the value-level ItemRefs under each def:ValueListDef. The `Variables` column in the dataset
table, and the `total_variable_refs` property, count only the ItemRefs belonging to an ItemGroupDef.

## Running defineutils from the Command-line

When you run a module with the -m switch it will execute the defineutils modules from the command-line. For example,
to transform a define.xml file into HTML using the stylesheet, the following command-line example executes the module
to generate define.html. The -m parameter instructs Python to run the module as an application. The definehtml program
uses the -d parameter to specify the define.xml file path and the -o to specify the define.html file path.

```commandline
python3 -m defineutils.definehtml -d tests/define.xml -o tests/define.html
```

The validate command can be executed using the command-line the same way. For validate, only the -d parameter is 
required to indicate the file path of the define.xml to validate. The -s parameter is optional and gives the file path
of the schema to validate against; without it the bundled Define-XML v2.1 schema is used. Without -o the formatted
listing goes to the console; with -o it is written to the given file. The --json switch emits machine-readable results
instead of the listing, and -L sets how many example locations are shown per finding (0 shows all).

```commandline
# validate against the bundled Define-XML v2.1 schema
python3 -m defineutils.validate -d tests/define.xml

# validate against a different version of the schema
python3 -m defineutils.validate -d tests/define.xml -s cdisc-define-2.0/define2-0-0.xsd

# save the listing to a file
python3 -m defineutils.validate -d tests/define.xml -o validation_report.txt

# machine-readable results for CI or other tooling
python3 -m defineutils.validate -d tests/define.xml --json

# show every location of every error, rather than the first 5 per finding
python3 -m defineutils.validate -d tests/define.xml -L 0
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

validate sets an exit code so it can gate a CI job: 0 when the define.xml is valid, 1 when it is invalid, and 2 when
the validation could not be run at all -- the schema would not load, the define.xml could not be read or parsed, or the
report could not be written. The report is written to stdout and the failure messages to stderr, so a redirected report
stays clean.

The definepp command pretty-prints a define.xml. Use the -d parameter to specify the define.xml file path and the -o
parameter to specify the formatted output file path. If no -o is given, the formatted define.xml is written to the
console, which can be paged with a tool like `more`. When printing to the console, the -H parameter limits the number
of lines shown.

```commandline
# write the formatted define.xml to a file
python3 -m defineutils.definepp -d tests/define.xml -o tests/define.pretty.xml

# print the formatted define.xml to the console, one screen at a time
python3 -m defineutils.definepp -d tests/define.xml | more

# print only the first 40 lines to the console
python3 -m defineutils.definepp -d tests/define.xml -H 40
```

The definerefs command checks the OID references and definitions in a define.xml. Use the -d parameter to specify
the define.xml file path. Without -o the formatted listing goes to the console; with -o it is written to the given
file. The --json switch emits machine-readable results instead of the listing, --errors-only suppresses the orphan
definition warnings, -L sets how many example locations are shown per finding (0 shows all), and --permissive
attempts a best-effort check of a define.xml that is not conformant enough to load normally.

```commandline
# print the listing to the console
python3 -m defineutils.definerefs -d tests/define.xml

# save the listing to a file
python3 -m defineutils.definerefs -d tests/define.xml -o refdef_report.txt

# machine-readable results for CI or other tooling
python3 -m defineutils.definerefs -d tests/define.xml --json

# errors only, with every location listed
python3 -m defineutils.definerefs -d tests/define.xml --errors-only -L 0

# best-effort check of a non-conformant define.xml
python3 -m defineutils.definerefs -d broken_define.xml --permissive
```

definerefs sets an exit code, like validate, so it can gate a CI job: 0 when there are no errors (a clean
define.xml, or one that only has orphan definition warnings), 1 when there are errors (dangling references,
duplicate OIDs or type mismatches), and 2 when the check could not be run at all -- the define.xml would not load,
or the report could not be written. A file that will not load is reported with a recommendation to run the validate
module to find out why.

The metrics command reports what is in a define.xml. Use the -d parameter to specify the define.xml file path.
Without -o the report goes to the console; with -o it is written to the given file. The --json switch emits
machine-readable results instead of the report, --no-datasets leaves the per-dataset table out, and --permissive
collects best-effort metrics from a define.xml that is not conformant enough to load normally.

```commandline
# print the report to the console
python3 -m defineutils.metrics -d tests/define.xml

# save the report to a file
python3 -m defineutils.metrics -d tests/define.xml -o metrics_report.txt

# machine-readable results for CI or other tooling
python3 -m defineutils.metrics -d tests/define.xml --json

# the counts and totals without the per-dataset table
python3 -m defineutils.metrics -d tests/define.xml --no-datasets

# best-effort metrics for a non-conformant define.xml
python3 -m defineutils.metrics -d broken_define.xml --permissive
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

metrics sets an exit code: 0 when the report was produced, and 2 when it could not be -- the define.xml is missing or
would not load, or the report could not be written. Unlike validate and definerefs it never exits 1, because a
metrics report describes a define.xml rather than judging it.

If you are running defineutils from the source code using a virtual environment, you may need to activate that virtual
environment before running the code from the command-line.

```commandline
source .venv/bin/activate
python3 -m defineutils.validate -d tests/define.xml
```
