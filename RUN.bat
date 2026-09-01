@echo off
chcp 65001 >nul
cd /d "%~dp0"
where python >nul 2>&1
if %errorlevel%==0 (
  python "%~dp0scan.py" %*
) else (
  py "%~dp0scan.py" %*
)
echo.
pause
