@ECHO OFF
SETLOCAL

REM BIDS Pipeline - Phase 2: Custom analysis scripts (band power, retinotopy, orientation, group stats)

SET "SCRIPT_DIR=%~dp0"
SET "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
FOR %%A IN ("%SCRIPT_DIR%\..\..")  DO SET "PROJECT_DIR=%%~fA"

ECHO ==================================================
ECHO   BIDS PIPELINE - PHASE 2: CUSTOM ANALYSES
ECHO ==================================================
ECHO   Project : %PROJECT_DIR%
ECHO ==================================================

SET "PYTHONUTF8=1"
SET "PYTHONIOENCODING=utf-8"

CD /D "%PROJECT_DIR%" || (ECHO ERROR: Could not find project folder at %PROJECT_DIR% & EXIT /B 1)
CALL "%PROJECT_DIR%\eeg-env\Scripts\activate.bat"

ECHO Running all custom analyses (band power, retinotopy, orientation, group stats)...
python "%SCRIPT_DIR%\run_all.py"
IF %ERRORLEVEL% NEQ 0 (
    ECHO ERROR: Custom analysis pipeline failed.
    EXIT /B 1
)

ECHO.
ECHO ==================================================
ECHO   PHASE 2 COMPLETE
ECHO   Group outputs: %PROJECT_DIR%\Bids_pipeline_Dataset\outputs\derivatives\bids_analysis\group_level
ECHO ==================================================
ENDLOCAL
