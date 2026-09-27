# Plan: Restructure defineutils as a proper package

## Goal
Enable import patterns like:
- `from defineutils import validate`
- `from defineutils.validate import DefineSchemaValidator, DefineSchemaValidationError`
- `from defineutils import definehtml`
- `from defineutils.definehtml import DefineHtml, DefineHtmlGenerationError`

## Current Structure
```
definehtml/          <- top-level package
validate/            <- top-level package
tests/
pyproject.toml
```

## Target Structure
```
defineutils/
  __init__.py        <- new: exports definehtml and validate submodules
  definehtml/
    __init__.py
    __main__.py
    definehtml.py
    define2-1.xsl
    define2-1.xsl.LICENSE
  validate/
    __init__.py
    __main__.py
    validate.py
    schema/
tests/
pyproject.toml
```

## Changes

### 1. Create defineutils package directory and move modules
- Create `defineutils/` directory
- Move `definehtml/` into `defineutils/`
- Move `validate/` into `defineutils/`

### 2. Create defineutils/__init__.py
```python
__version__ = "0.2.0"

from defineutils import definehtml, validate

__all__ = ["definehtml", "validate", "__version__"]
```

### 3. Update defineutils/definehtml/__init__.py
Change import from relative to absolute:
```python
from defineutils.definehtml import DefineHtml, DefineHtmlGenerationError
```

### 4. Update defineutils/validate/__init__.py
Change import from relative to absolute:
```python
from defineutils.validate import DefineSchemaValidator, DefineSchemaValidationError
```

### 5. Update defineutils/definehtml/__main__.py
Change import to use new package path:
```python
from defineutils.definehtml import DefineHtml, DefineHtmlGenerationError
```

### 6. Update defineutils/validate/__main__.py
Change import to use new package path:
```python
from defineutils.validate import DefineSchemaValidator, DefineSchemaValidationError
```

### 7. Update pyproject.toml
- Bump version to 0.2.0
- Update `[tool.setuptools]` packages to `["defineutils", "defineutils.definehtml", "defineutils.validate"]`
- Update `[tool.setuptools.package-data]` paths

### 8. Update tests/test_definehtml.py
Change imports to:
```python
from defineutils.definehtml import DefineHtml, DefineHtmlGenerationError
```

### 9. Update tests/test_validate.py
Change imports to:
```python
from defineutils.validate import DefineSchemaValidator, DefineSchemaValidationError
```

### 10. Update README.md
- Update example imports to use `defineutils.` prefix
- Update CLI commands to use `python -m defineutils.definehtml` and `python -m defineutils.validate`

### 11. Update CLAUDE.md
- Update CLI commands to reflect new module paths

## Files to Modify
- `defineutils/__init__.py` (create)
- `defineutils/definehtml/__init__.py` (move + modify)
- `defineutils/definehtml/__main__.py` (move + modify)
- `defineutils/validate/__init__.py` (move + modify)
- `defineutils/validate/__main__.py` (move + modify)
- `pyproject.toml`
- `tests/test_definehtml.py`
- `tests/test_validate.py`
- `README.md`
- `CLAUDE.md`

## Verification
1. Run `pip install -e .` to install in development mode
2. Run `pytest` to verify all tests pass
3. Test CLI: `python -m defineutils.definehtml -d tests/define.xml -o /tmp/define.html`
4. Test CLI: `python -m defineutils.validate -d tests/define.xml`
5. Test imports in Python REPL:
   ```python
   from defineutils import validate
   from defineutils.validate import DefineSchemaValidator
   from defineutils import definehtml
   from defineutils.definehtml import DefineHtml
   ```
