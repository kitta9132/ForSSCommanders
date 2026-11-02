@echo off
rem Naming only: does not enable, disable or verify ATM.
call "%~dp0record-13357625.bat" --with-atm
exit /b %ERRORLEVEL%
