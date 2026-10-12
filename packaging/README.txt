defineutils command-line tools
==============================

Tools for CDISC Define-XML v2.1 files. Python does not need to be installed.

  definehtml      render a define.xml as HTML
  definevalidate  schema validate a define.xml
  definepp        pretty-print (re-indent) a define.xml
  definerefs      check OID references and definitions
  definemetrics   report element counts and study metrics

Keep the commands and the _internal folder together: the commands need it to run.


Running a command
-----------------
Open a terminal in this folder (Windows: PowerShell or Command Prompt; macOS: Terminal) and run, for example:

  Windows:  .\definehtml -d C:\studies\define.xml
  macOS:    ./definehtml -d ~/studies/define.xml

Every command takes --help to list its options and --version to show its version.


Running the commands from any folder
------------------------------------
Add this folder to your PATH, then open a new terminal; the commands no longer need the .\ or ./ prefix.

  Windows:  Settings > search "environment variables" > "Edit environment variables for your account" >
            select Path > Edit > New > enter the full path of this folder > OK.
  macOS:    add this line to ~/.zprofile, with the full path of this folder:
              export PATH="/path/to/defineutils:$PATH"


First run: security warnings
----------------------------
These builds are not code-signed, so Windows and macOS warn about them.

  Windows:  before extracting, right-click the downloaded zip > Properties > tick "Unblock" > OK.
            If "Windows protected your PC" appears, choose "More info" > "Run anyway".
  macOS:    remove the download quarantine once, in Terminal:
              xattr -dr com.apple.quarantine /path/to/defineutils


Licenses
--------
defineutils is MIT licensed. The LICENSES folder holds the licenses of defineutils and of the components it
bundles: Python, lxml (with libxml2 and libxslt), xmlschema, elementpath, odmlib and its dependencies, and the
PyInstaller bootloader.

Documentation and source: https://github.com/swhume/defineutils
