"""
Builds the defineutils executables for the platform it runs on, and zips them:

    python packaging/build_executables.py
    python packaging/build_executables.py --zip-only

Runs PyInstaller with packaging/defineutils.spec, adds README.txt and a LICENSES folder to the bundle, and writes
packaging/dist/defineutils-<version>-<platform>.zip (e.g. windows-x64, macos-arm64). --zip-only zips the existing
packaging/dist/defineutils again without rebuilding, which CI does after signing it. Run it with Python 3.12 in an
environment holding defineutils and packaging/requirements-build.txt. Output stays under packaging/, away from the
top-level dist/ that holds the PyPI files.
"""
import argparse
import os
import platform
import shutil
import stat
import sys
import sysconfig
import time
import zipfile
from importlib import metadata
from pathlib import Path

import PyInstaller.__main__
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

from defineutils import __version__
from defineutils.definehtml.definehtml import STYLESHEET

PACKAGING = Path(__file__).resolve().parent
DIST = PACKAGING / "dist"
WORK = PACKAGING / "build"


def platform_name() -> str:
    """the platform part of the zip name: windows-x64, macos-arm64, linux-x64"""
    system = {"win32": "windows", "darwin": "macos"}.get(sys.platform, sys.platform)
    machine = platform.machine().lower()
    architecture = {"amd64": "x64", "x86_64": "x64", "aarch64": "arm64"}.get(machine, machine)
    return f"{system}-{architecture}"


def bundled_distributions() -> list:
    """defineutils and its runtime dependencies, transitively, as installed here: the packages the bundle holds"""
    found = {}
    pending = ["defineutils"]
    while pending:
        name = canonicalize_name(pending.pop())
        if name in found:
            continue
        found[name] = metadata.distribution(name)
        for requirement in map(Requirement, found[name].requires or []):
            if requirement.marker is None or requirement.marker.evaluate({"extra": ""}):
                pending.append(requirement.name)
    return [found[name] for name in sorted(found)]


def license_files(distribution) -> list:
    """the license files a distribution declares (License-File), from its .dist-info folder"""
    declared = {Path(name).name for name in distribution.metadata.get_all("License-File") or []}
    files = [distribution.locate_file(file) for file in distribution.files or []
             if file.parts[0].endswith(".dist-info") and file.name in declared]
    if not files:
        raise SystemExit(f"no license file found for {distribution.metadata['Name']}; the bundle needs one")
    return files


def python_license() -> Path:
    """Python's LICENSE.txt: in the standard library folder (macOS, Linux) or the install folder (Windows)"""
    for folder in (Path(sysconfig.get_path("stdlib")), Path(sys.base_prefix)):
        if (folder / "LICENSE.txt").is_file():
            return folder / "LICENSE.txt"
    raise SystemExit("Python's LICENSE.txt was not found; the bundle needs it")


def write_licenses(folder: Path) -> None:
    """one folder per bundled component, named <name>-<version>, holding its license files"""
    components = [(f"Python-{platform.python_version()}", [python_license()])]
    for distribution in [*bundled_distributions(), metadata.distribution("pyinstaller")]:
        files = license_files(distribution)
        if distribution.metadata["Name"] == "defineutils":
            # the stylesheet is a modified copy of Lex Jansen's, under its own MIT license
            files.append(STYLESHEET.with_name(STYLESHEET.name + ".LICENSE"))
        components.append((f"{distribution.metadata['Name']}-{distribution.version}", files))
    for name, files in components:
        (folder / name).mkdir(parents=True)
        for file in files:
            shutil.copyfile(file, folder / name / Path(file).name)


def write_zip(folder: Path, zip_path: Path) -> None:
    """
    zips the folder with its permissions and any symlinks, so the executables stay executable when unzipped on
    macOS; zipfile's own write() would store a symlink's target as a copy
    """
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for root, dirs, files in os.walk(folder):
            dirs.sort()
            # os.walk lists a symlinked folder in dirs without walking it, so store it as a link
            for name in sorted(files) + [name for name in dirs if Path(root, name).is_symlink()]:
                path = Path(root, name)
                arcname = path.relative_to(folder.parent).as_posix()
                if path.is_symlink():
                    # not ZipInfo.from_file(), which follows the link
                    info = zipfile.ZipInfo(arcname, date_time=time.localtime(path.lstat().st_mtime)[:6])
                    info.create_system = 3  # Unix, so unzip reads the mode bits below
                    info.external_attr = (stat.S_IFLNK | 0o777) << 16
                    archive.writestr(info, os.readlink(path))
                else:
                    archive.write(path, arcname)


def main() -> None:
    parser = argparse.ArgumentParser(description="builds the defineutils executables for this platform and zips them")
    parser.add_argument("--zip-only", action="store_true",
                        help="rezip the existing packaging/dist/defineutils (e.g. after signing) without rebuilding")
    zip_only = parser.parse_args().zip_only

    bundle = DIST / "defineutils"
    if zip_only:
        if not bundle.is_dir():
            raise SystemExit(f"{bundle} does not exist; build it first")
    else:
        PyInstaller.__main__.run(["--noconfirm", "--clean", "--log-level", "WARN", "--distpath", str(DIST),
                                  "--workpath", str(WORK), str(PACKAGING / "defineutils.spec")])
        shutil.copyfile(PACKAGING / "README.txt", bundle / "README.txt")
        write_licenses(bundle / "LICENSES")

    zip_path = DIST / f"defineutils-{__version__}-{platform_name()}.zip"
    zip_path.unlink(missing_ok=True)
    write_zip(bundle, zip_path)
    print(zip_path)
    # in GitHub Actions, hand the zip's path to the steps that upload and test it; forward slashes, because the upload
    # action reads the path as a glob pattern
    if "GITHUB_OUTPUT" in os.environ:
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
            output.write(f"zip={zip_path.as_posix()}\n")


if __name__ == "__main__":
    main()
