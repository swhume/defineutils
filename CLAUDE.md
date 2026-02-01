# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

defineutils is a Python package for working with CDISC Define-XML v2.1 files. It provides two modules:
- **definehtml**: Transforms define.xml files to HTML using an embedded XSL stylesheet
- **validate**: Schema validates define.xml files using embedded XSD schemas

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

# Schema validate a define.xml
python -m defineutils.validate -d tests/define.xml
```

## Architecture

The package is structured as `defineutils` with two submodules:
- `defineutils/definehtml/` - HTML generation from Define-XML
- `defineutils/validate/` - Schema validation

Each submodule follows the same pattern:
- Main class in `<submodule>.py` with a custom exception class
- `__init__.py` exports the main class and exception
- `__main__.py` enables CLI usage via `python -m defineutils.<submodule>`

**definehtml module**: Uses lxml for XSLT transformation. The `DefineHtml` class takes a define.xml path, applies the bundled `define2-1.xsl` stylesheet, and outputs HTML via `transform_to_html_string()` or `transform_to_html_file()`.

**validate module**: Uses xmlschema for validation. The `DefineSchemaValidator` class validates against bundled Define-XML v2.1 schemas in `defineutils/validate/schema/`. Returns success message or raises `DefineSchemaValidationError` with details.

Both modules bundle their required resources (XSL stylesheet, XSD schemas) to simplify usage.
