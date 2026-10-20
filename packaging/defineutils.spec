# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller build definition for the defineutils executables: seven one-folder executables passed to one shared COLLECT,
so they share a single _internal runtime folder. Build with packaging/build_executables.py, which also adds README.txt
and LICENSES/ and zips the result.

A new data file or computed import in defineutils or a dependency must be added here, or the frozen build fails only
when that code runs; the CI run of the tests against the executables is what catches it.
"""
import os
import re
import sys

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

from defineutils import __version__

# each command is built from packaging/entry/<command>.py, which calls the run() its console or GUI script calls
COMMANDS = ["definehtml", "definevalidate", "definepp", "definerefs", "definemetrics", "defineview", "defineconform"]

# defineview is what opening a define.xml with a double-click runs, so on Windows it is built windowed and no console
# window opens; it shows its errors on a page or in a message box instead. Elsewhere it keeps the console bootloader
WINDOWED = {"defineview"} if sys.platform == "win32" else set()

# the Windows FileDescription, which Explorer's Properties show and "Open with" is expected to list the program by
DESCRIPTIONS = {"defineview": "defineutils Define-XML viewer"}


def version_resource(command):
    """the command's Windows version resource, or None when it has no description or this isn't Windows"""
    if sys.platform != "win32" or command not in DESCRIPTIONS:
        return None
    # imported here: versioninfo imports pefile, which PyInstaller installs only on Windows
    from PyInstaller.utils.win32 import versioninfo
    numbers = tuple(int(number) for number in re.match(r"(\d+)\.(\d+)\.(\d+)", __version__).groups()) + (0,)
    strings = {"FileDescription": DESCRIPTIONS[command], "FileVersion": __version__, "InternalName": command,
               "OriginalFilename": f"{command}.exe", "ProductName": "defineutils", "ProductVersion": __version__}
    return versioninfo.VSVersionInfo(
        ffi=versioninfo.FixedFileInfo(filevers=numbers, prodvers=numbers),
        kids=[versioninfo.StringFileInfo([versioninfo.StringTable(
                  "040904B0", [versioninfo.StringStruct(name, value) for name, value in strings.items()])]),
              # US English, Unicode: the language and code page of the StringTable above
              versioninfo.VarFileInfo([versioninfo.VarStruct("Translation", [0x0409, 1200])])])

# defineutils loads its stylesheet and schemas via Path(__file__).parent, which a frozen module resolves inside
# _internal/, so the files are collected at the same relative paths
datas = collect_data_files("defineutils")
# odmlib has no hook: it imports its models by computed name and reads its data/ and schemas/ folders
datas += collect_data_files("odmlib")
hiddenimports = collect_submodules("odmlib")
# elementpath has no hook: validators/*.xsd. xmlschema's contrib hook collects its data files, and its one computed
# import (xmlschema.xpath.xpath3) happens only with use_xpath3, which defineutils never sets. collect_all("xmlschema")
# would also bundle xmlschema.testing, which pulls in unittest, pdb and asyncio
datas += collect_data_files("elementpath")

# setuptools is a PyInstaller requirement, not a defineutils one: it would be pulled in through cerberus's conditional
# imports, and its runtime hook adds about 0.15 s to every start-up
excludes = ["setuptools", "pkg_resources", "_distutils_hack"]

# UTF-8 mode, so output redirected to a file or pipe is UTF-8 on Windows too, as on macOS
options = [("X utf8", None, "OPTION")]

analyses = []
executables = []
for command in COMMANDS:
    # noarchive keeps the Python modules as .pyc files in the shared _internal folder; an archive would be embedded
    # in each executable, five copies of about 4.5 MB
    analysis = Analysis([os.path.join(SPECPATH, "entry", f"{command}.py")], datas=datas,
                        hiddenimports=hiddenimports, excludes=excludes, noarchive=True)
    pyz = PYZ(analysis.pure)
    # icon="NONE" leaves out PyInstaller's own icon
    executable = EXE(pyz, analysis.scripts, options, exclude_binaries=True, name=command,
                     console=command not in WINDOWED, version=version_resource(command), icon="NONE", strip=False,
                     upx=False)
    analyses.append(analysis)
    executables.append(executable)

COLLECT(*executables,
        *[analysis.binaries for analysis in analyses],
        *[analysis.datas for analysis in analyses],
        strip=False, upx=False, name="defineutils")
