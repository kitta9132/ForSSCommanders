@echo off
setlocal EnableExtensions
set "SCRIPT_DIR=%~dp0"
set "PS1=%SCRIPT_DIR%restore-atm.ps1"
set "BUILD=13357625"
set "GAMEROOT=C:\Program Files (x86)\Steam\steamapps\common\World of Warships"
set "DRYRUN="

if /I "%~1"=="--dry-run" set "DRYRUN=-DryRun"
if /I "%~1"=="-dryrun" set "DRYRUN=-DryRun"
if /I "%~1"=="/dry-run" set "DRYRUN=-DryRun"

echo ATM restore for WoWS build %BUILD%
echo Target: %GAMEROOT%\bin\%BUILD%
echo.

if not exist "%PS1%" (
  echo [ERROR] restore-atm.ps1 was not found next to this .bat.
  echo [ERROR] Keep both files in the same folder.
  goto :failed
)

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%PS1%" -Build "%BUILD%" -GameRoot "%GAMEROOT%" %DRYRUN%
set "RC=%ERRORLEVEL%"

if not "%RC%"=="0" goto :failed_rc

echo.
if defined DRYRUN (
  echo Dry run completed. No files were moved.
) else (
  echo ATM restore completed successfully.
)
echo.
pause
exit /b 0

:failed_rc
echo.
echo [ERROR] ATM restore did not complete. Exit code: %RC%
echo [ERROR] No success was reported. Review the messages above.
echo.
pause
exit /b %RC%

:failed
echo.
pause
exit /b 1
