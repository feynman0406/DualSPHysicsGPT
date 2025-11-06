import os
import pathlib
import shutil
import subprocess
import tempfile
import textwrap
import xml.etree.ElementTree as ET
from contextlib import contextmanager

# ---- Runtime Options ----
# For .bat execution, headless is default; set USE_EXISTING_BATCH=1 to reuse existing .bat script
USE_EXISTING_BATCH = os.environ.get("USE_EXISTING_BATCH", "0") == "1"
USE_DIRECT_EXEC = os.environ.get("USE_DIRECT_EXEC", "0") == "1"
BATCH_PATH = os.environ.get("DSPH_BATCH_PATH", "")

# DualSPHysics binary folder and case name
DSPH_BIN_DIR = os.environ.get("DSPH_BIN_DIR", r"bin/windows")          # Example: C:\DualSPHysics\bin\windows
CASE_NAME = os.environ.get("DSPH_CASE_NAME", "Case")        # Will generate <CASE_NAME>_Def.xml and <CASE_NAME>_out\
USE_GPU = os.environ.get("DSPH_USE_GPU", "0") == "1"        # Use GPU if true; fallback to CPU otherwise

# List of required DualSPHysics binaries (executables)
DUALSPHYSICS_BINARIES = (
    "GenCase_win64.exe",
    "DualSPHysics5.4CPU_win64.exe",
    "DualSPHysics5.4_win64.exe",
    "BoundaryVTK_win64.exe",
    "PartVTK_win64.exe",
    "PartVTKOut_win64.exe",
    "MeasureTool_win64.exe",
    "ComputeForces_win64.exe",
    "IsoSurface_win64.exe",
    "FlowTool_win64.exe",
    "FloatingInfo_win64.exe",
    "TracerParts_win64.exe",
)

ALLOWED_COPY_MODES = {"off", "warn", "strict"}
# Recognized data/geometry asset suffixes for dependency collection
DATA_FILE_SUFFIXES = (
    ".dat",
    ".txt",
    ".csv",
    ".vtk",
    ".vtp",
    ".vtu",
    ".vtm",
    ".stl",
    ".obj",
    ".xyz",
)
PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_ASSET_DIRS = [
    PROJECT_ROOT / "AutoXml_script" / "external_assets",
    PROJECT_ROOT / "AutoXml_script",
    PROJECT_ROOT,
]

def _get_copy_mode() -> str:
    mode = os.environ.get("DSPH_COPY_DATA", "warn").strip().lower()
    if mode not in ALLOWED_COPY_MODES:
        return "warn"
    return mode


def _compute_asset_dirs():
    dirs = []
    env_paths = os.environ.get("DSPH_ASSET_PATHS")
    if env_paths:
        for raw in env_paths.split(os.pathsep):
            if raw:
                dirs.append(pathlib.Path(raw).expanduser())
    dirs.extend(DEFAULT_ASSET_DIRS)
    seen = set()
    normalized = []
    for directory in dirs:
        try:
            expanded = directory.expanduser()
        except Exception:
            continue
        key = str(expanded.resolve()) if expanded.exists() else str(expanded)
        if key in seen:
            continue
        seen.add(key)
        normalized.append(expanded)
    return normalized


ASSET_SEARCH_DIRS = _compute_asset_dirs()


@contextmanager
def _temporary_env(overrides):
    """Temporarily set environment variables, restoring previous values afterwards."""

    sentinel = object()
    original = {}
    for key, value in (overrides or {}).items():
        original[key] = os.environ.get(key, sentinel)
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    try:
        yield
    finally:
        for key, prior in original.items():
            if prior is sentinel:
                os.environ.pop(key, None)
            else:
                os.environ[key] = prior


def _looks_like_data_file(value: str) -> bool:
    if value is None:
        return False
    candidate = value.strip().strip('"\'')

    if not candidate or candidate.upper() == "NONE":
        return False

    lowered = candidate.lower()
    if "[" in candidate or "]" in candidate:
        return False

    return lowered.endswith(DATA_FILE_SUFFIXES)


def _collect_asset_paths(xml_str: str):
    warnings = []
    try:
        root = ET.fromstring(xml_str)
    except ET.ParseError as exc:
        warnings.append(f"Failed to parse XML for auxiliary assets: {exc}")
        return [], warnings

    assets = set()
    for elem in root.iter():
        tag_lower = elem.tag.lower()

        if tag_lower == "copy":
            for key in ("from", "src", "source", "path", "file"):
                val = elem.attrib.get(key)
                if _looks_like_data_file(val):
                    assets.add(val.strip().strip('"\''))
            for child in elem:
                for key in ("file", "path"):
                    val = child.attrib.get(key)
                    if _looks_like_data_file(val):
                        assets.add(val.strip().strip('"\''))
                if child.text and _looks_like_data_file(child.text):
                    assets.add(child.text.strip().strip('"\''))
            continue

        for attr_value in elem.attrib.values():
            if _looks_like_data_file(attr_value):
                assets.add(attr_value.strip().strip('"\''))
        if elem.text and _looks_like_data_file(elem.text):
            assets.add(elem.text.strip().strip('"\''))
        for child in elem:
            for attr_value in child.attrib.values():
                if _looks_like_data_file(attr_value):
                    assets.add(attr_value.strip().strip('"\''))
            if child.text and _looks_like_data_file(child.text):
                assets.add(child.text.strip().strip('"\''))
    return sorted(assets), warnings


def _resolve_asset_path(asset_name: str):
    candidate = pathlib.Path(asset_name)
    if candidate.is_absolute():
        return candidate if candidate.exists() else None

    for base_dir in ASSET_SEARCH_DIRS:
        try:
            base_dir_resolved = base_dir.resolve()
        except FileNotFoundError:
            base_dir_resolved = base_dir
        candidate_path = base_dir_resolved / candidate
        if candidate_path.exists():
            return candidate_path

    if candidate.exists():
        return candidate

    return None


def _safe_asset_destination(workdir_path: pathlib.Path, asset_name: str) -> pathlib.Path:
    pure = pathlib.PurePath(asset_name)
    if pure.is_absolute() or ".." in pure.parts:
        return workdir_path / pathlib.Path(asset_name).name
    return workdir_path / pathlib.Path(asset_name)


def _materialize_assets(workdir_path: pathlib.Path, asset_names, copy_mode: str):
    warnings = []
    copied = []

    if not asset_names or copy_mode == "off":
        return warnings, copied

    workdir_path.mkdir(parents=True, exist_ok=True)

    for asset_name in asset_names:
        source_path = _resolve_asset_path(asset_name)
        if source_path is None:
            msg = f"Auxiliary asset not found: {asset_name}"
            warnings.append(msg)
            if copy_mode == "strict":
                raise FileNotFoundError(msg)
            continue

        dest_path = _safe_asset_destination(workdir_path, asset_name)
        try:
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, dest_path)
        except Exception as exc:
            msg = f"Failed to copy asset '{asset_name}' from '{source_path}': {exc}"
            warnings.append(msg)
            if copy_mode == "strict":
                raise RuntimeError(msg) from exc
            continue

        copied.append(str(dest_path))

    return warnings, copied


def _augment_result(result: dict, workspace: dict | None):
    if workspace is None:
        return result

    workdir_path = workspace.get("workdir")
    xml_path = workspace.get("xml_path")
    asset_names = workspace.get("asset_names", [])
    assets_copied = workspace.get("assets_copied", [])
    copy_mode = workspace.get("copy_mode")
    workspace_warnings = workspace.get("warnings") or []

    if workdir_path is not None:
        result.setdefault("workdir", str(workdir_path))
    if xml_path is not None:
        result.setdefault("xml_path", str(xml_path))
    if asset_names:
        result.setdefault("assets_requested", asset_names)
    elif "assets_requested" not in result:
        result["assets_requested"] = []
    if assets_copied:
        result.setdefault("assets_copied", assets_copied)
    elif "assets_copied" not in result:
        result["assets_copied"] = []
    if copy_mode is not None:
        result.setdefault("copy_mode", copy_mode)

    if workspace_warnings:
        existing = result.get("warnings")
        if existing:
            if isinstance(existing, list):
                merged = existing + workspace_warnings
            else:
                merged = [existing] + workspace_warnings
            result["warnings"] = merged
        else:
            result["warnings"] = list(workspace_warnings)
    else:
        result.setdefault("warnings", [])

    return result
# The following optional output control environment variables are supported:
#   DSPH_POINTS_VEL / DSPH_POINTS_PRESS_INC / DSPH_POINTS_PRESS_COR / DSPH_FILEBOXES / DSPH_ONLYMK
HEADLESS_BAT = r'''@echo off
setlocal EnableDelayedExpansion
rem Don't remove the two jump line after than the next line [set NL=^]
set NL=^

rem "name" and "dirout" are named according to the testcase
set name=%~1
if "%name%"=="" set name=CaseTest
set dirout=%name%_out
set diroutdata=%dirout%\data

rem "executables" are renamed and called from their directory
set dirbin=%~2
if "%dirbin%"=="" set dirbin=../bin/windows
set gencase="%dirbin%\GenCase_win64.exe"
set dualsphysicscpu="%dirbin%\DualSPHysics5.4CPU_win64.exe"
set dualsphysicsgpu="%dirbin%\DualSPHysics5.4_win64.exe"
set boundaryvtk="%dirbin%\BoundaryVTK_win64.exe"
set partvtk="%dirbin%\PartVTK_win64.exe"
set partvtkout="%dirbin%\PartVTKOut_win64.exe"
set measuretool="%dirbin%\MeasureTool_win64.exe"
set computeforces="%dirbin%\ComputeForces_win64.exe"
set isosurface="%dirbin%\IsoSurface_win64.exe"
set flowtool="%dirbin%\FlowTool_win64.exe"
set floatinginfo="%dirbin%\FloatingInfo_win64.exe"
set tracerparts="%dirbin%\TracerParts_win64.exe"

set mode=%~3
if "%mode%"=="" set mode=CPU
if /I "%mode%"=="GPU" (
    set solver=%dualsphysicsgpu%
) else (
    set solver=%dualsphysicscpu%
)

set errorcode=0

rem Stage control flags
if "%RUN_GENCASE%"=="" set RUN_GENCASE=1
if "%RUN_SOLVER%"=="" set RUN_SOLVER=1
if "%RUN_POST%"=="" set RUN_POST=1

:menu
if exist "%dirout%" (
    if /I "%DSPH_AUTODELETE_OUT%"=="1" goto run
    set /p option=The folder "%dirout%" already exists. Choose an option.!NL!  [1]- Delete it and continue.!NL!  [2]- Execute post-processing.!NL!  [3]- Abort and exit.!NL!
    if "!option!"=="1" goto run
    if "!option!"=="2" goto postprocessing
    if "!option!"=="3" (
        set errorcode=1
        goto fail
    )
    goto menu
)

:run
rem "dirout" to store results is removed if it already exists
if "%RUN_GENCASE%"=="1" (
    if exist "%dirout%" rd /s /q "%dirout%"
)

rem CODES are executed according the selected parameters of execution in this testcase

rem Executes GenCase to create initial files for simulation.
if "%RUN_GENCASE%"=="1" (
    %gencase% "%name%_Def" "%dirout%\%name%" -save:all
    if not "%ERRORLEVEL%"=="0" (
        set errorcode=101
        goto fail
    )
)

if "%RUN_GENCASE%"=="1" (
    if "%RUN_SOLVER%"=="0" if "%RUN_POST%"=="0" goto success
)

rem Executes DualSPHysics to simulate SPH method.
if "%RUN_SOLVER%"=="1" (
    %solver% "%dirout%\%name%" "%dirout%"
    if not "%ERRORLEVEL%"=="0" (
        set errorcode=102
        goto fail
    )
) else (
    if "%RUN_POST%"=="1" goto postprocessing
    goto success
)

:postprocessing
if not "%RUN_POST%"=="1" goto success
rem Executes PartVTK to create VTK files with particles.
set dirout2=%dirout%\particles
if not exist "%dirout2%" mkdir "%dirout2%"
%partvtk% -dirdata "%diroutdata%" -savevtk "%dirout2%\PartMoving" -onlytype:-all,+moving -vars:+idp,+vel,+rhop,+press
if not "%ERRORLEVEL%"=="0" (
    set errorcode=201
    goto fail
)
%partvtk% -dirdata "%diroutdata%" -savevtk "%dirout2%\PartFloating" -onlytype:-all,+floating
if not "%ERRORLEVEL%"=="0" (
    set errorcode=202
    goto fail
)
%partvtk% -dirdata "%diroutdata%" -savevtk "%dirout2%\PartFluid" -onlytype:-all,+fluid
if not "%ERRORLEVEL%"=="0" (
    set errorcode=203
    goto fail
)

rem Executes PartVTKOut to create VTK files with excluded particles.
%partvtkout% -dirdata "%diroutdata%" -savevtk "%dirout2%\PartFluidOut" -SaveResume "%dirout2%\_ResumeFluidOut"
if not "%ERRORLEVEL%"=="0" (
    set errorcode=204
    goto fail
)

rem Executes MeasureTool to create VTK files with velocity and a CSV file with velocity at each simulation time.
set dirout2=%dirout%\measuretool
if not exist "%dirout2%" mkdir "%dirout2%"
%measuretool% -dirdata "%diroutdata%" -points CaseDambreak_PointsVelocity.txt -onlytype:-all,+fluid -vars:-all,+vel.x,+vel.m -savevtk "%dirout2%\PointsVelocity" -savecsv "%dirout2%\_PointsVelocity"
if not "%ERRORLEVEL%"=="0" (
    set errorcode=211
    goto fail
)

rem Executes MeasureTool to create VTK files with incorrect pressure and a CSV file with value at each simulation time.
%measuretool% -dirdata "%diroutdata%" -points CaseDambreak_PointsPressure_Incorrect.txt -onlytype:-all,+fluid -vars:-all,+press,+kcorr -kcusedummy:0 -kclimit:0.5 -savevtk "%dirout2%\PointsPressure_Incorrect" -savecsv "%dirout2%\_PointsPressure_Incorrect"
if not "%ERRORLEVEL%"=="0" (
    set errorcode=212
    goto fail
)

rem Executes MeasureTool to create VTK files with correct pressure and a CSV file with value at each simulation time.
%measuretool% -dirdata "%diroutdata%" -points CaseDambreak_PointsPressure_Correct.txt -onlytype:-all,+fluid -vars:-all,+press,+kcorr -kcusedummy:0 -kclimit:0.5 -savevtk "%dirout2%\PointsPressure_Correct" -savecsv "%dirout2%\_PointsPressure_Correct"
if not "%ERRORLEVEL%"=="0" (
    set errorcode=213
    goto fail
)

rem Executes ComputeForces to create a CSV file with force at each simulation time.
set dirout2=%dirout%\forces
if not exist "%dirout2%" mkdir "%dirout2%"
%computeforces% -dirdata "%diroutdata%" -onlymk:20 -viscoart:0.1 -savecsv "%dirout2%\_ForceBuilding"
if not "%ERRORLEVEL%"=="0" (
    set errorcode=221
    goto fail
)

rem Executes IsoSurface to create VTK files with surface fluid and slices of surface.
set dirout2=%dirout%\surface
if not exist "%dirout2%" mkdir "%dirout2%"
set planesy="-slicevec:0:0.1:0:0:1:0 -slicevec:0:0.2:0:0:1:0 -slicevec:0:0.3:0:0:1:0 -slicevec:0:0.4:0:0:1:0 -slicevec:0:0.5:0:0:1:0 -slicevec:0:0.6:0:0:1:0"
set planesx="-slicevec:0.1:0:0:1:0:0 -slicevec:0.2:0:0:1:0:0 -slicevec:0.3:0:0:1:0:0 -slicevec:0.4:0:0:1:0:0 -slicevec:0.5:0:0:1:0:0 -slicevec:0.6:0:0:1:0:0 -slicevec:0.7:0:0:1:0:0 -slicevec:0.8:0:0:1:0:0 -slicevec:0.9:0:0:1:0:0 -slicevec:1.0:0:0:1:0:0"
set planesd="-slice3pt:0:0:0:1:0.7:0:1:0.7:1"
%isosurface% -dirdata "%diroutdata%" -saveiso "%dirout2%\Surface" -vars:-all,vel,rhop,idp,type -saveslice "%dirout2%\Slices" %planesy% %planesx% %planesd%
if not "%ERRORLEVEL%"=="0" (
    set errorcode=231
    goto fail
)

rem Executes FlowTool to create VTK files with particles assigned to different zones and a CSV file with information of each zone.
set dirout2=%dirout%\flow
if not exist "%dirout2%" mkdir "%dirout2%"
%flowtool% -dirdata "%diroutdata%" -fileboxes CaseDambreak_FileBoxes.txt -savecsv "%dirout2%\_ResultFlow.csv" -savevtk "%dirout2%\Boxes.vtk"
if not "%ERRORLEVEL%"=="0" (
    set errorcode=241
    goto fail
)

:success
echo All done
exit /b 0

:fail
if "%errorcode%"=="0" set errorcode=1
echo Execution aborted.
exit /b %errorcode%
'''


def _prepare_case_workspace(xml_str: str):
    copy_mode = _get_copy_mode()
    asset_names, asset_warnings = _collect_asset_paths(xml_str)
    warnings = list(asset_warnings)

    base = os.environ.get("DSPH_WORKDIR")
    if base:
        workdir_path = pathlib.Path(base).expanduser()
        workdir_path.mkdir(parents=True, exist_ok=True)
        workdir_path = workdir_path.resolve()
    else:
        workdir_path = pathlib.Path(tempfile.mkdtemp(prefix="dsph_"))

    outdir = workdir_path / f"{CASE_NAME}_out"
    try:
        if outdir.exists():
            shutil.rmtree(outdir)
    except Exception as exc:
        msg = f"Failed to remove previous output directory: {exc}"
        warnings.append(msg)
        return None, {
            "status": "fail",
            "stage": "precheck",
            "stdout": "",
            "stderr": msg,
            "workdir": str(workdir_path),
            "warnings": warnings,
            "assets_requested": asset_names,
            "assets_copied": [],
            "copy_mode": copy_mode,
        }

    xml_path = workdir_path / f"{CASE_NAME}_Def.xml"
    xml_path.write_text(xml_str, encoding="utf-8", errors="ignore")

    try:
        asset_copy_warnings, copied_assets = _materialize_assets(workdir_path, asset_names, copy_mode)
        warnings.extend(asset_copy_warnings)
    except Exception as exc:
        msg = f"Failed to materialize auxiliary assets: {exc}"
        warnings.append(msg)
        return None, {
            "status": "fail",
            "stage": "precheck",
            "stdout": "",
            "stderr": msg,
            "workdir": str(workdir_path),
            "warnings": warnings,
            "assets_requested": asset_names,
            "assets_copied": [],
            "copy_mode": copy_mode,
        }

    workspace = {
        "workdir": workdir_path,
        "xml_path": xml_path,
        "asset_names": asset_names,
        "assets_copied": copied_assets,
        "warnings": warnings,
        "copy_mode": copy_mode,
    }
    return workspace, None


def _stage_from_headless_return(code: int) -> str:
    if code == 0:
        return "post"
    if code == 101:
        return "gencase"
    if code == 102:
        return "solver"
    if 200 <= code < 300:
        return "post"
    return "unknown"


def _infer_stage_from_logs(stdout: str, stderr: str, default: str = "unknown") -> str:
    blob = f"{stdout}\n{stderr}".lower()
    if "all done" in blob:
        return "post"
    if "dualsphysics" in blob:
        return "solver"
    if "gencase" in blob:
        return "gencase"
    return default


def _run_direct_exec(xml_str: str):
    if not DSPH_BIN_DIR:
        return {"status": "fail", "stage": "precheck", "stdout": "", "stderr": "DSPH_BIN_DIR not set", "workdir": ""}
    workspace, error = _prepare_case_workspace(xml_str)
    if error:
        return error
    workdir_path = workspace["workdir"]
    bin_dir = pathlib.Path(DSPH_BIN_DIR).expanduser()
    gencase_path = (bin_dir / "GenCase_win64.exe").resolve()
    solver_name = "DualSPHysics5.4_win64.exe" if USE_GPU else "DualSPHysics5.4CPU_win64.exe"
    solver_path = (bin_dir / solver_name).resolve()

    run_gencase = os.environ.get("RUN_GENCASE", "1") != "0"
    run_solver = os.environ.get("RUN_SOLVER", "1") != "0"

    required = []
    if run_gencase:
        required.append(gencase_path)
    if run_solver:
        required.append(solver_path)
    missing = [str(p) for p in required if not p.exists()]
    if missing:
        msg = "Missing executables: " + ", ".join(missing)
        result = {
            "status": "fail",
            "stage": "precheck",
            "stdout": "",
            "stderr": msg,
            "workdir": str(workspace["workdir"]),
        }
        return _augment_result(result, workspace)

    dirout = f"{CASE_NAME}_out"
    base_name = os.path.join(dirout, CASE_NAME)

    stdout_sections = []
    stderr_sections = []
    env = os.environ.copy()
    env.setdefault("DSPH_AUTODELETE_OUT", "1")

    if run_gencase:
        gencase_cmd = [str(gencase_path), f"{CASE_NAME}_Def", base_name, "-save:all"]
        gencase_proc = subprocess.run(
            gencase_cmd,
            cwd=str(workdir_path),
            capture_output=True,
            text=True,
            env=env,
        )
        gencase_stdout = gencase_proc.stdout or ""
        gencase_stderr = gencase_proc.stderr or ""
        stdout_sections.append(f"=== gencase stdout ===\n{gencase_stdout}")
        stderr_sections.append(f"=== gencase stderr ===\n{gencase_stderr}")
        if gencase_proc.returncode != 0:
            result = {
                "status": "fail",
                "stage": "gencase",
                "stdout": "".join(stdout_sections).strip(),
                "stderr": "".join(stderr_sections).strip(),
                "workdir": str(workdir_path),
            }
            return _augment_result(result, workspace)
        
        # Check if GenCase actually produced the output XML
        expected_case_xml = workdir_path / dirout / f"{CASE_NAME}.xml"
        if not expected_case_xml.exists():
            stderr_sections.append(f"\n=== validation error ===\nGenCase succeeded (exit code 0) but did not produce the expected output file: {expected_case_xml}")
            result = {
                "status": "fail",
                "stage": "gencase",
                "stdout": "".join(stdout_sections).strip(),
                "stderr": "".join(stderr_sections).strip(),
                "workdir": str(workdir_path),
            }
            return _augment_result(result, workspace)
    else:
        stdout_sections.append("=== gencase stdout ===\n<skipped>")
        stderr_sections.append("=== gencase stderr ===\n<skipped>")

    if not run_solver:
        stage = "gencase" if run_gencase else "precheck"
        result = {
            "status": "success",
            "stage": stage,
            "stdout": "".join(stdout_sections).strip(),
            "stderr": "".join(stderr_sections).strip(),
            "workdir": str(workdir_path),
        }
        return _augment_result(result, workspace)

    solver_cmd = [str(solver_path), base_name, dirout]
    solver_proc = subprocess.run(
        solver_cmd,
        cwd=str(workdir_path),
        capture_output=True,
        text=True,
        env=env,
    )
    solver_stdout = solver_proc.stdout or ""
    solver_stderr = solver_proc.stderr or ""
    stdout_sections.append(f"=== solver stdout ===\n{solver_stdout}")
    stderr_sections.append(f"=== solver stderr ===\n{solver_stderr}")
    stdout_full = "".join(stdout_sections).strip()
    stderr_full = "".join(stderr_sections).strip()

    if solver_proc.returncode != 0:
        result = {
            "status": "fail",
            "stage": "solver",
            "stdout": stdout_full,
            "stderr": stderr_full,
            "workdir": str(workdir_path),
        }
        return _augment_result(result, workspace)

    result = {
        "status": "success",
        "stage": "solver",
        "stdout": stdout_full,
        "stderr": stderr_full,
        "workdir": str(workdir_path),
    }
    return _augment_result(result, workspace)

def _run_headless_bat(xml_str: str):
    if not DSPH_BIN_DIR:
        return {"status": "fail", "stage": "precheck", "stdout": "", "stderr": "DSPH_BIN_DIR not set", "workdir": ""}
    workspace, error = _prepare_case_workspace(xml_str)
    if error:
        return error
    workdir_path = workspace["workdir"]
    xml_path = workspace["xml_path"]
    bat_path = workdir_path / "run_headless.bat"
    bat_path.write_text(HEADLESS_BAT, encoding="utf-8")
    mode = "GPU" if USE_GPU else "CPU"
    bin_dir = str(pathlib.Path(DSPH_BIN_DIR).resolve())
    cmd = ["cmd", "/c", str(bat_path), CASE_NAME, bin_dir, mode]
    env = os.environ.copy()
    env.setdefault("DSPH_AUTODELETE_OUT", "1")
    proc = subprocess.run(cmd, cwd=str(workdir_path), capture_output=True, text=True, env=env)
    stage_value = _stage_from_headless_return(proc.returncode)
    status = "success" if proc.returncode == 0 else "fail"
    result = {
        "status": status,
        "stage": stage_value,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "workdir": str(workdir_path),
    }
    return _augment_result(result, workspace)

def _run_existing_bat(xml_str: str):
    if not BATCH_PATH:
        return {"status": "fail", "stage": "precheck", "stdout": "", "stderr": "DSPH_BATCH_PATH not set", "workdir": ""}
    bat_dir = str(pathlib.Path(BATCH_PATH).resolve().parent)
    xml_path = pathlib.Path(bat_dir) / f"{CASE_NAME}_Def.xml"
    xml_path.write_text(xml_str, encoding="utf-8", errors="ignore")
    try:
        proc = subprocess.run(["cmd", "/c", BATCH_PATH], cwd=bat_dir, input="1\n\n", capture_output=True, text=True)
    except Exception as e:
        return {"status": "fail", "stage": "precheck", "stdout": "", "stderr": str(e), "workdir": bat_dir}
    stdout = proc.stdout or ""
    stderr = proc.stderr or ""
    status = "success" if proc.returncode == 0 or ("All done" in stdout) else "fail"
    stage = _infer_stage_from_logs(stdout, stderr, "post" if status == "success" else "unknown")
    result = {"status": status, "stage": stage, "stdout": stdout, "stderr": stderr, "workdir": bat_dir}
    return result

def run_gencase(xml_file: str | os.PathLike[str], *, output_dir: str | os.PathLike[str] | None = None) -> dict:
    """Execute GenCase on a generated XML file."""

    xml_path = pathlib.Path(xml_file)
    if not xml_path.exists():
        raise FileNotFoundError(f"XML file not found: {xml_path}")

    xml_text = xml_path.read_text(encoding="utf-8", errors="ignore")

    env_overrides = {"RUN_GENCASE": "1", "RUN_SOLVER": "0", "RUN_POST": "0"}
    with _temporary_env(env_overrides):
        result = _run_direct_exec(xml_text)

    if result.get("status") != "success":
        stderr = (result.get("stderr") or "").strip()
        stdout = (result.get("stdout") or "").strip()
        message = stderr or stdout or "GenCase execution failed"
        raise RuntimeError(message)

    workdir_value = result.get("workdir")
    if output_dir is not None:
        source_dir = None
        if workdir_value:
            source_dir = pathlib.Path(workdir_value) / f"{CASE_NAME}_out"
        if source_dir is None or not source_dir.exists():
            raise RuntimeError(f"GenCase completed but produced no output directory at: {source_dir}")

        destination = pathlib.Path(output_dir)
        try:
            if destination.exists():
                shutil.rmtree(destination)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(source_dir, destination)
        except Exception as exc:
            raise RuntimeError(f"Failed to publish GenCase output to '{destination}': {exc}")

        result["output_dir"] = str(destination)

    return result

def run_dualsphysics(xml_str: str):
    if USE_EXISTING_BATCH:
        return _run_existing_bat(xml_str)
    if USE_DIRECT_EXEC:
        return _run_direct_exec(xml_str)
    return _run_headless_bat(xml_str)


