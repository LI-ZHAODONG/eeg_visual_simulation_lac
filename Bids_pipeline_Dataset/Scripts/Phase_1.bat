@ECHO OFF
SETLOCAL ENABLEDELAYEDEXPANSION

REM BIDS Pipeline - Phase 1: MNE-BIDS-Pipeline preprocessing

SET "SCRIPT_DIR=%~dp0"
SET "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
FOR %%A IN ("%SCRIPT_DIR%\..\..")  DO SET "PROJECT_DIR=%%~fA"

IF "%BIDS_DIR%"=="" (
    FOR %%A IN ("%PROJECT_DIR%\..\ds006547") DO SET "BIDS_DIR=%%~fA"
)

ECHO ==================================================
ECHO   BIDS PIPELINE - PHASE 1: PREPROCESSING
ECHO ==================================================
ECHO   Project : %PROJECT_DIR%
ECHO   BIDS    : %BIDS_DIR%
ECHO ==================================================

SET "PYTHONUTF8=1"
SET "PYTHONIOENCODING=utf-8"

CD /D "%PROJECT_DIR%" || (ECHO ERROR: Could not find project folder at %PROJECT_DIR% & EXIT /B 1)
CALL "%PROJECT_DIR%\eeg-env\Scripts\activate.bat"

IF NOT EXIST "%BIDS_DIR%" (
    ECHO ERROR: BIDS dataset not found at %BIDS_DIR%
    ECHO   Set the BIDS_DIR environment variable to the ds006547 path:
    ECHO     set BIDS_DIR=C:\path\to\ds006547
    EXIT /B 1
)

SET "BIDS_ROOT=%BIDS_DIR%"

ECHO Running MNE-BIDS-Pipeline preprocessing...
python "%SCRIPT_DIR%\run_pipeline.py" --steps preprocessing --n-jobs 4
IF %ERRORLEVEL% NEQ 0 (
    ECHO ERROR: MNE-BIDS-Pipeline preprocessing failed.
    EXIT /B 1
)

ECHO.
ECHO ==================================================
ECHO   PHASE 1 COMPLETE
ECHO   Outputs: %PROJECT_DIR%\Bids_pipeline_Dataset\outputs\derivatives
ECHO ==================================================
ENDLOCAL
