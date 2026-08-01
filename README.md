# defineutils

## CDISC Define-XML v2.1 utilities

The defineutils package currently includes 4 modules:
1. `definehtml.py`: transforms a define.xml into a define.html using the stylesheet
2. `validate.py`: schema validates a define.xml file
3. `definepp.py`: pretty-prints (re-indents) a define.xml file
4. `definerefs.py`: checks the OID reference/definition integrity of a define.xml file

The `definehtml.py` module includes the Define-XML v2.1 style sheet to simplify usage. It generates a define.html file,
or alternatively will generate an HTML string.

The `validate.py` module includes the Define-XML v2.1 schema to simplify usage. It schema validates a define.xml file
and returns a define.xml is valid message to indicate success, or a detailed message documenting the schema validation
issues. The bundled schema is the default, but any schema file can be used instead -- the `-s` command-line parameter,
or the `xsd_file` argument in code -- to validate against a different Define-XML version.

The `definepp.py` module pretty-prints a define.xml file. The reformat is byte-preserving apart from whitespace:
comments, processing instructions, element/attribute order and namespaces are all retained. It writes the formatted
define.xml to a file, or, if no output file is given, to the console where it can be paged with a tool like `more`.

The `definerefs.py` module checks the OID reference/definition integrity of a define.xml file and prints a formatted
listing of everything it finds: references to OIDs nothing defines, references that resolve to the wrong kind of
element, duplicate OIDs, and definitions nothing references. It also checks the Define-XML document leaves
(`def:leaf`) and the `def:ArchiveLocationID` / `leafID` references to them. Errors and warnings are listed together
with the location of each occurrence; the report can be written to the console, to a file, or as JSON.

## Using defineutils

Currently, defineutils contains 4 modules: one for generating an HTML rendition, one for schema validation, one
for pretty-printing, and one for OID reference/definition checking.

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
The schema validation errors are reported via the DefineSchemaValidationError exception.

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
of the schema to validate against; without it the bundled Define-XML v2.1 schema is used.

```commandline
# validate against the bundled Define-XML v2.1 schema
python3 -m defineutils.validate -d tests/define.xml

# validate against a different version of the schema
python3 -m defineutils.validate -d tests/define.xml -s cdisc-define-2.0/define2-0-0.xsd
```

validate sets an exit code so it can gate a CI job: 0 when the define.xml is valid, 1 when it is invalid, and 2 when
the validation could not be run at all -- the schema would not load, or the define.xml could not be read or parsed.
Errors are written to stderr and the file is valid message to stdout.

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

If you are running defineutils from the source code using a virtual environment, you may need to activate that virtual
environment before running the code from the command-line.

```commandline
source .venv/bin/activate
python3 -m defineutils.validate -d tests/define.xml
```
