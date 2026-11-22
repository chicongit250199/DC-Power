@echo off
REM Build DC Power ra file .exe tren Windows (can Python 3.9+ da cai san)
cd /d %~dp0
if not exist .venv python -m venv .venv
call .venv\Scripts\activate
pip install -r requirements-dev.txt

set ICON_ARG=
for %%f in (upload\*.ico upload\*.png) do if not defined ICON_ARG set ICON_ARG=--icon "%%f"

pyinstaller --noconfirm --windowed --name "DC Power" --paths src --add-data "upload;upload" %ICON_ARG% run.py

echo.
echo Xong: dist\DC Power\DC Power.exe
pause
