# defineutils

## CDISC Define-XML v2.1 utilities

The defineutils package currently includes 2 modules:
1. `definehtml.py`: transforms a define.xml into a define.html using the stylesheet
2. `validate.py`: schema validates a define.xml file

The `definehtml.py` module includes the Define-XML v2.1 style sheet to simplify usage. It generates a define.html file,
or alternatively will generate an HTML string.

The `validate.py` module includes the Define-XML v2.1 schema to simplify usage. It schema validates a define.xml file
and returns a define.xml is valid message to indicate success, or a detailed message documenting the schema validation
issues.

## Using defineutils

Currently, defineutils contains 2 modules, one for generating an HTML rendition and one for schema validation.

Example code used to generate a define.html from a define.xml:
```python
from pathlib import Path
from definehtml import DefineHtml, DefineHtmlGenerationError

out_file = Path(__file__).parent.joinpath("define.html")
dh = DefineHtml(Path(__file__).parent.joinpath("define.xml"))
dh.transform_to_html_file(out_file)
```

The above code applies the Define-XML v2.1 stylesheet to the define.xml to generation the define.html file. The 
stylesheet is embedded in the module. For error handling, use the custom DefineHtmlGenerationError exception.

Example code used to schema validate a define.xml:
```python
from pathlib import Path
from validate import DefineSchemaValidator, DefineSchemaValidationError

validator = DefineSchemaValidator(Path(__file__).parent.joinpath("define.xml"))
try:
    result = validator.validate_define_file()
except DefineSchemaValidationError as e:
    print(e)
```

The above code schema validates the specified define.xml file. The Define-XML v2.1 schema is embedded into the module.
The schema validation errors are reported via the DefineSchemaValidationError exception.

## Running defineutils from the Command-line

When you run a module with the -m switch it will execute the defineutils modules from the command-line. For example,
to transform a define.xml file into HTML using the stylesheet, the following command-line example executes the module
to generate define.html. The -m parameter instructs Python to run the module as an application. The definehtml program
uses the -d parameter to specify the define.xml file path, and the -o to specify the define.html file path.

```commandline
 python3 -m definehtml -d tests/define.xml -o tests/define.html
```

The validate command can be executed using the command-line the same way. For validate, only the -d parameter is 
required to indicate the file path of the define.xml to validate.

```commandline
python3 -m validate -d tests/define.xml
```
