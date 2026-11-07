@echo off
rem Naming only: does not enable, disable or verify ATM.
call "%~dp0record.bat" --with-atm
exit /b %ERRORLEVEL%
