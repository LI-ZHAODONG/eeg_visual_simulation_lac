@ECHO OFF
SETLOCAL ENABLEDELAYEDEXPANSION

REM --- Paths (relative to this script's location) ---
SET "SCRIPT_DIR=%~dp0"
SET "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
FOR %%A IN ("%SCRIPT_DIR%\..\..")  DO SET "PROJECT_DIR=%%~fA"

IF "%BIDS_DIR%"=="" (
    FOR %%A IN ("%PROJECT_DIR%\..\ds006547") DO SET "BIDS_DIR=%%~fA"
)

SET "THRESHOLD=0.60"

ECHO ==================================================
ECHO   STARTING FULL PHASE 1 AUTOMATION
ECHO ==================================================

SET "PYTHONUTF8=1"
SET "PYTHONIOENCODING=utf-8"

CD /D "%PROJECT_DIR%"
IF %ERRORLEVEL% NEQ 0 (ECHO ERROR: Could not find project folder at %PROJECT_DIR% & EXIT /B 1)

CALL "%PROJECT_DIR%\eeg-env\Scripts\activate.bat"

FOR /L %%i IN (1,1,31) DO CALL :PROCESS_SUBJECT %%i

ECHO.
ECHO ==================================================
ECHO   ALL SUBJECTS FINISHED PHASE 1 PROCESSING
ECHO ==================================================
ENDLOCAL
GOTO :EOF

REM ================================================================
REM  Subroutine: process one subject
REM  %1 = subject number (integer)
REM ================================================================
:PROCESS_SUBJECT
SET /A NUM=%1
IF %NUM% LSS 10 (SET "SUB_ID=sub-0%NUM%") ELSE (SET "SUB_ID=sub-%NUM%")
SET "BASE_NAME=%SUB_ID%_ses-01_task-visual_eeg"

SET "RAW_VHDR=%BIDS_DIR%\%SUB_ID%\ses-01\eeg\%BASE_NAME%.vhdr"
SET "OUT_DIR=%PROJECT_DIR%\Custom_pipeline_Dataset\outputs\%SUB_ID%"

SET "ICA_PATH=%OUT_DIR%\%BASE_NAME%-ica.fif"
SET "REVIEW_JSON=%OUT_DIR%\%BASE_NAME%-ica_component_review.json"
SET "REFINED_REVIEW_JSON=%OUT_DIR%\%BASE_NAME%-ica_component_review-refined.json"
SET "EPOCHS_PATH=%OUT_DIR%\%BASE_NAME%-final-epo.fif"

SET "ALPHA_COND=%OUT_DIR%\%BASE_NAME%-alpha_by_condition.npz"
SET "GAMMA_COND=%OUT_DIR%\%BASE_NAME%-gamma_by_condition.npz"
SET "BAND_SUMMARY=%OUT_DIR%\%BASE_NAME%-band_power_summary.json"

SET "ERSP_NPY=%OUT_DIR%\%BASE_NAME%-component_ersp.npy"
SET "ERSP_EVENTS=%OUT_DIR%\%BASE_NAME%-component_ersp_event_codes.npy"
SET "ERSP_FREQS=%OUT_DIR%\%BASE_NAME%-component_ersp_freqs.npy"
SET "ERSP_TIMES=%OUT_DIR%\%BASE_NAME%-component_ersp_times.npy"

ECHO.
ECHO ==================================================
ECHO   Processing %SUB_ID%...
ECHO ==================================================

IF NOT EXIST "%RAW_VHDR%" (
    ECHO ERROR: Raw VHDR not found for %SUB_ID%. Skipping.
    EXIT /B 0
)

MKDIR "%OUT_DIR%" 2>NUL

REM Step 1: Preprocess raw data and fit ICA
ECHO [Step 1] Preprocessing raw EEG and fitting ICA...
python "%SCRIPT_DIR%\preprocess.py" --vhdr "%RAW_VHDR%" --out-dir "%OUT_DIR%"
IF %ERRORLEVEL% NEQ 0 (ECHO ERROR on Step 1 for %SUB_ID%. Skipping. & EXIT /B 0)

IF NOT EXIST "%ICA_PATH%" (
    ECHO ERROR: ICA file not found for %SUB_ID%. Skipping.
    EXIT /B 0
)

REM Step 2: Automated ICA inspection
ECHO [Step 2] Running mne-icalabel...
python "%SCRIPT_DIR%\auto_inspect_ica.py" --ica-path "%ICA_PATH%" --vhdr "%RAW_VHDR%" --threshold "%THRESHOLD%"
IF %ERRORLEVEL% NEQ 0 (ECHO ERROR on Step 2 for %SUB_ID%. Skipping. & EXIT /B 0)

IF NOT EXIST "%REVIEW_JSON%" (
    ECHO ERROR: Review JSON not found for %SUB_ID%. Skipping.
    EXIT /B 0
)

REM Step 2.5: Refine ICA review
ECHO [Step 2.5] Refining borderline ICA decisions...
python "%SCRIPT_DIR%\refine_ica_review.py" --review-json "%REVIEW_JSON%" --out-json "%REFINED_REVIEW_JSON%"
IF %ERRORLEVEL% NEQ 0 (ECHO ERROR on Step 2.5 for %SUB_ID%. Skipping. & EXIT /B 0)

IF NOT EXIST "%REFINED_REVIEW_JSON%" (
    ECHO ERROR: Refined review JSON not found for %SUB_ID%. Skipping.
    EXIT /B 0
)

REM Step 3: Apply ICA
ECHO [Step 3] Applying ICA exclusions...
python "%SCRIPT_DIR%\apply_reviewed_ica.py" --ica-path "%ICA_PATH%" --vhdr "%RAW_VHDR%" --review-json "%REFINED_REVIEW_JSON%"
IF %ERRORLEVEL% NEQ 0 (ECHO ERROR on Step 3 for %SUB_ID%. Skipping. & EXIT /B 0)

IF NOT EXIST "%EPOCHS_PATH%" (
    ECHO ERROR: Epochs file not found for %SUB_ID%. Skipping.
    EXIT /B 0
)

REM Step 4: Extract Band Power
ECHO [Step 4] Extracting Alpha/Gamma Power...
python "%SCRIPT_DIR%\extract_band_power.py" --epochs-path "%EPOCHS_PATH%"
IF %ERRORLEVEL% NEQ 0 (ECHO ERROR on Step 4 for %SUB_ID%. Skipping. & EXIT /B 0)

REM Step 5: Retinotopy
ECHO [Step 5] Building Retinotopy Summaries...
python "%SCRIPT_DIR%\condition_analysis.py" --alpha-by-condition "%ALPHA_COND%" --gamma-by-condition "%GAMMA_COND%" --band-power-summary "%BAND_SUMMARY%"
IF %ERRORLEVEL% NEQ 0 (ECHO ERROR on Step 5 for %SUB_ID%. Skipping. & EXIT /B 0)

REM Step 6: Orientation tuning
ECHO [Step 6] Building Orientation Summaries...
python "%SCRIPT_DIR%\orientation_tuning_analysis.py" --alpha-by-condition "%ALPHA_COND%" --gamma-by-condition "%GAMMA_COND%" --band-power-summary "%BAND_SUMMARY%"
IF %ERRORLEVEL% NEQ 0 (ECHO ERROR on Step 6 for %SUB_ID%. Skipping. & EXIT /B 0)

REM Step 7: ERSP extraction
ECHO [Step 7] Extracting Single-Trial ERSPs...
python "%SCRIPT_DIR%\extract_component_ersp.py" --vhdr "%RAW_VHDR%" --ica-path "%ICA_PATH%"
IF %ERRORLEVEL% NEQ 0 (ECHO ERROR on Step 7 for %SUB_ID%. Skipping. & EXIT /B 0)

REM Step 8: ERSP stats
ECHO [Step 8] Computing ERSP Statistics...
python "%SCRIPT_DIR%\orientation_ersp_stats.py" --ersp-npy "%ERSP_NPY%" --event-codes-npy "%ERSP_EVENTS%" --freqs-npy "%ERSP_FREQS%" --times-npy "%ERSP_TIMES%"
IF %ERRORLEVEL% NEQ 0 (ECHO ERROR on Step 8 for %SUB_ID%. Skipping. & EXIT /B 0)

ECHO SUCCESS: Phase 1 fully completed for %SUB_ID%!
EXIT /B 0
