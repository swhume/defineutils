defineutils command-line tools
==============================

Tools for CDISC Define-XML v2.1 files. Python does not need to be installed.

  definehtml      render a define.xml as HTML
  definevalidate  schema validate a define.xml
  definepp        pretty-print (re-indent) a define.xml
  definerefs      check OID references and definitions
  definemetrics   report element counts and study metrics
  defineview      show a define.xml in the browser (on Windows, with a double-click: see below)

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


Opening a define.xml with a double-click (Windows)
--------------------------------------------------
defineview renders a define.xml and opens it in your default browser. To have a double-click do that:

  1. Keep this folder where it will stay, e.g. %LOCALAPPDATA%\Programs\defineutils. Windows remembers where
     defineview.exe is, so to update, replace this folder's contents rather than unzipping somewhere else.
  2. Right-click a define.xml > Open with > Choose another app > "Choose an app on your PC" (Windows 10: More apps >
     "Look for another app on this PC") > select defineview.exe in this folder.
  3. "Just once" leaves .xml files opening as they do now, and keeps defineview in the Open with menu.
     "Always" opens every .xml file with defineview; one that isn't Define-XML v2.1 gets a page saying so.

The HTML is written beside the define.xml (define.html for define.xml, replacing any file of that name), or to your
temp folder when that folder can't be written to. To use the temp folder every time, make a shortcut to defineview.exe,
add " --temp" to the end of its Target (shortcut Properties), and drop define.xml files onto it; move the shortcut to
the folder that typing shell:sendto in File Explorer's address bar opens, to add it to the Send to menu too.

To undo "Always": Settings > Apps > Default apps > find .xml > choose another app.


First run: security warnings
----------------------------
These builds are not code-signed, so Windows and macOS warn about them.

  Windows:  before extracting, right-click the downloaded zip > Properties > tick "Unblock" > OK.
            If "Windows protected your PC" appears, choose "More info" > "Run anyway".
  macOS:    remove the download quarantine once, in Terminal:
              xattr -dr com.apple.quarantine /path/to/defineutils
            (type it without the path, then drag this folder onto the Terminal window to add the path)


Licenses
--------
defineutils is MIT licensed. The LICENSES folder holds the licenses of defineutils and of the components it
bundles: Python, lxml (with libxml2 and libxslt), xmlschema, elementpath, odmlib and its dependencies, and the
PyInstaller bootloader.

Documentation and source: https://github.com/swhume/defineutils
