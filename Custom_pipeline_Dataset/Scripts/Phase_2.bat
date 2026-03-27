@ECHO OFF
SETLOCAL ENABLEDELAYEDEXPANSION

REM --- Paths (relative to this script's location) ---
SET "SCRIPT_DIR=%~dp0"
SET "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
FOR %%A IN ("%SCRIPT_DIR%\..\..")  DO SET "PROJECT_DIR=%%~fA"

SET "OUTPUTS_DIR=%PROJECT_DIR%\Custom_pipeline_Dataset\outputs"
SET "PHASE2_DIR=%OUTPUTS_DIR%\group_level"
SET "MANIFEST_JSON=%PHASE2_DIR%\phase2_manifest.json"
SET "MAPPING_JSON=%SCRIPT_DIR%\condition_mapping.json"

ECHO ==================================================
ECHO   STARTING PHASE 2 GROUP-LEVEL AUTOMATION
ECHO ==================================================

CD /D "%PROJECT_DIR%" || (ECHO ERROR: Could not find project folder at %PROJECT_DIR% & EXIT /B 1)

REM Activate the virtual environment
CALL "%PROJECT_DIR%\eeg-env\Scripts\activate.bat"

MKDIR "%PHASE2_DIR%" 2>NUL

ECHO Building manifest of valid subjects...

python - <<EOF 2>NUL
python -c "
import json, sys
from pathlib import Path

outputs_dir = Path(r'%OUTPUTS_DIR%')
phase2_dir  = Path(r'%PHASE2_DIR%')
manifest_path = Path(r'%MANIFEST_JSON%')

subjects = []
for i in range(1, 32):
    sub_id = f'sub-{i:02d}'
    base   = f'{sub_id}_ses-01_task-visual_eeg'
    out_dir = outputs_dir / sub_id
    files = {
        'subject': sub_id,
        'out_dir': str(out_dir),
        'epochs_fif':          str(out_dir / f'{base}-final-epo.fif'),
        'band_power_summary':  str(out_dir / f'{base}-band_power_summary.json'),
        'alpha_by_condition':  str(out_dir / f'{base}-alpha_by_condition.npz'),
        'gamma_by_condition':  str(out_dir / f'{base}-gamma_by_condition.npz'),
        'retinotopy_summary':  str(out_dir / 'retinotopy_summary.json'),
        'orientation_summary': str(out_dir / 'orientation_tuning_summary.json'),
        'ersp_npy':            str(out_dir / f'{base}-component_ersp.npy'),
        'ersp_event_codes':    str(out_dir / f'{base}-component_ersp_event_codes.npy'),
        'ersp_freqs':          str(out_dir / f'{base}-component_ersp_freqs.npy'),
        'ersp_times':          str(out_dir / f'{base}-component_ersp_times.npy'),
    }
    required = [Path(files[k]) for k in ('epochs_fif','band_power_summary','alpha_by_condition','gamma_by_condition')]
    if all(p.exists() for p in required):
        files['has_retinotopy'] = Path(files['retinotopy_summary']).exists()
        files['has_orientation'] = Path(files['orientation_summary']).exists()
        files['has_ersp'] = all(Path(files[k]).exists() for k in ('ersp_npy','ersp_event_codes','ersp_freqs','ersp_times'))
        subjects.append(files)

manifest = {'n_subjects': len(subjects), 'subjects': subjects, 'group_output_dir': str(phase2_dir)}
manifest_path.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
print(f'Saved manifest: {manifest_path}')
print(f'Valid subjects found: {len(subjects)}')
for s in subjects:
    print(f'  - {s[\"subject\"]}')
"
IF %ERRORLEVEL% NEQ 0 (ECHO ERROR: Manifest creation failed. & EXIT /B 1)

ECHO.
ECHO ==================================================
ECHO   STARTING GROUP ANALYSIS
ECHO ==================================================

REM Step 1: Grand Average
IF EXIST "%SCRIPT_DIR%\grand_average_analysis.py" (
    ECHO Running grand average analysis...
    python "%SCRIPT_DIR%\grand_average_analysis.py" --outputs-root "%OUTPUTS_DIR%" --mapping-json "%MAPPING_JSON%" --out-dir "%PHASE2_DIR%"
    IF %ERRORLEVEL% NEQ 0 ECHO ERROR on grand average analysis.
) ELSE (
    ECHO WARNING: grand_average_analysis.py not found. Skipping.
)

REM Step 2: Topomaps
IF EXIST "%SCRIPT_DIR%\group_topomaps.py" (
    ECHO Running group topomaps...
    python "%SCRIPT_DIR%\group_topomaps.py" --outputs-root "%OUTPUTS_DIR%" --mapping-json "%MAPPING_JSON%" --out-dir "%PHASE2_DIR%"
    IF %ERRORLEVEL% NEQ 0 ECHO ERROR on group topomaps.
) ELSE (
    ECHO WARNING: group_topomaps.py not found. Skipping.
)

REM Step 3: Retinotopy Model Fit
IF EXIST "%SCRIPT_DIR%\retinotopy_model_fit.py" (
    ECHO Running retinotopy model fit...
    python "%SCRIPT_DIR%\retinotopy_model_fit.py" --outputs-root "%OUTPUTS_DIR%"
    IF %ERRORLEVEL% NEQ 0 ECHO ERROR on retinotopy model fit.
) ELSE (
    ECHO WARNING: retinotopy_model_fit.py not found. Skipping.
)

REM Step 4: Group Statistical Analysis
IF EXIST "%SCRIPT_DIR%\group_statistical_analysis.py" (
    ECHO Running group statistical analysis...
    python "%SCRIPT_DIR%\group_statistical_analysis.py" --outputs-dir "%OUTPUTS_DIR%" --mapping "%MAPPING_JSON%" --out-dir "%PHASE2_DIR%"
    IF %ERRORLEVEL% NEQ 0 ECHO ERROR on group statistical analysis.
) ELSE (
    ECHO WARNING: group_statistical_analysis.py not found. Skipping.
)

REM Step 5: Group ERSP Statistics
IF EXIST "%SCRIPT_DIR%\group_ersp_statistics.py" (
    ECHO Running group ERSP statistics...
    python "%SCRIPT_DIR%\group_ersp_statistics.py" --outputs-dir "%OUTPUTS_DIR%" --out-dir "%PHASE2_DIR%"
    IF %ERRORLEVEL% NEQ 0 ECHO ERROR on group ERSP statistics.
) ELSE (
    ECHO WARNING: group_ersp_statistics.py not found. Skipping.
)

ECHO.
ECHO ==================================================
ECHO   PHASE 2 COMPLETED
ECHO ==================================================
ENDLOCAL
