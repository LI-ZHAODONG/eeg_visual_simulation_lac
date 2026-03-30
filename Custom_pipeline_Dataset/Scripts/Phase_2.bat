@ECHO OFF
SETLOCAL ENABLEDELAYEDEXPANSION

REM --- Paths (relative to this script's location) ---
SET "SCRIPT_DIR=%~dp0"
SET "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
FOR %%A IN ("%SCRIPT_DIR%\..\..")  DO SET "PROJECT_DIR=%%~fA"

SET "OUTPUTS_DIR=%PROJECT_DIR%\Custom_pipeline_Dataset\outputs"
SET "PHASE2_DIR=%OUTPUTS_DIR%\group_level"
SET "MAPPING_JSON=%SCRIPT_DIR%\condition_mapping.json"

ECHO ==================================================
ECHO   STARTING PHASE 2 GROUP-LEVEL AUTOMATION
ECHO ==================================================

SET "PYTHONUTF8=1"
SET "PYTHONIOENCODING=utf-8"

CD /D "%PROJECT_DIR%"
IF %ERRORLEVEL% NEQ 0 (ECHO ERROR: Could not find project folder at %PROJECT_DIR% & EXIT /B 1)

CALL "%PROJECT_DIR%\eeg-env\Scripts\activate.bat"

MKDIR "%PHASE2_DIR%" 2>NUL

ECHO Building manifest of valid subjects...
python "%SCRIPT_DIR%\build_manifest.py" "%OUTPUTS_DIR%" "%PHASE2_DIR%"
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

REM Step 6: Group Orientation ERSP Stats
IF EXIST "%SCRIPT_DIR%\group_orientation_ersp_stats.py" (
    ECHO Running group orientation ERSP statistics...
    python "%SCRIPT_DIR%\group_orientation_ersp_stats.py" --outputs-root "%OUTPUTS_DIR%" --out-dir "%PHASE2_DIR%"
    IF %ERRORLEVEL% NEQ 0 ECHO ERROR on group orientation ERSP stats.
) ELSE (
    ECHO WARNING: group_orientation_ersp_stats.py not found. Skipping.
)

REM Step 7: Group Sensor ERSP
IF EXIST "%SCRIPT_DIR%\group_sensor_ersp.py" (
    ECHO Running group sensor ERSP summary...
    python "%SCRIPT_DIR%\group_sensor_ersp.py" --outputs-root "%OUTPUTS_DIR%" --out-dir "%PHASE2_DIR%"
    IF %ERRORLEVEL% NEQ 0 ECHO ERROR on group sensor ERSP summary.
) ELSE (
    ECHO WARNING: group_sensor_ersp.py not found. Skipping.
)

REM Step 8: Group Sensor ANOVA
IF EXIST "%SCRIPT_DIR%\group_sensor_anova.py" (
    ECHO Running group sensor ANOVA mapping...
    python "%SCRIPT_DIR%\group_sensor_anova.py" --outputs-root "%OUTPUTS_DIR%" --out-dir "%PHASE2_DIR%"
    IF %ERRORLEVEL% NEQ 0 ECHO ERROR on group sensor ANOVA mapping.
) ELSE (
    ECHO WARNING: group_sensor_anova.py not found. Skipping.
)

REM Step 9: Group Orientation/Direction Analysis
IF EXIST "%SCRIPT_DIR%\group_orientation_direction_analysis.py" (
    ECHO Running group orientation/direction analysis...
    python "%SCRIPT_DIR%\group_orientation_direction_analysis.py" --outputs-root "%OUTPUTS_DIR%"
    IF %ERRORLEVEL% NEQ 0 ECHO ERROR on group orientation/direction analysis.
) ELSE (
    ECHO WARNING: group_orientation_direction_analysis.py not found. Skipping.
)

ECHO.
ECHO ==================================================
ECHO   PHASE 2 COMPLETED
ECHO ==================================================
ENDLOCAL
