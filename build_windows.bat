@echo off
chcp 65001 >nul
REM Build DC Power ra file .exe tren Windows (can Python 3.9+ da cai san)
REM Ket qua: dist\DC Power\DC Power.exe  (copy NGUYEN thu muc "dist\DC Power" sang may khac)
cd /d %~dp0
if not exist .venv python -m venv .venv
call .venv\Scripts\activate
pip install -r requirements-dev.txt || goto :loi

REM Tao icon .ico va logo thu nho tu anh trong upload\
python tools\make_icon.py || goto :loi

set ICON_ARG=
if exist build\assets\app.ico set ICON_ARG=--icon build\assets\app.ico

REM Bo cac module Qt khong dung de ban build nhe hon (QtOpenGL phai GIU vi pyqtgraph can)
pyinstaller --noconfirm --windowed --name "DC Power" --paths src %ICON_ARG% ^
  --add-data "build\assets\upload;upload" ^
  --exclude-module tkinter --exclude-module psutil --exclude-module pytest --exclude-module PIL ^
  --exclude-module PySide6.QtQuick --exclude-module PySide6.QtQml --exclude-module PySide6.QtPdf ^
  --exclude-module PySide6.QtNetwork --exclude-module PySide6.QtQuickWidgets --exclude-module pyqtgraph.opengl ^
  run.py || goto :loi

REM Xoa DLL Qt khong dung (opengl32sw.dll ~20 MB la bo ve OpenGL bang phan mem, app khong can)
for %%f in (opengl32sw.dll Qt6Pdf.dll Qt6Quick.dll Qt6Qml.dll Qt6QmlModels.dll Qt6QmlMeta.dll Qt6QmlWorkerScript.dll Qt6Network.dll qpdf.dll) do (
  for /r "dist\DC Power\_internal" %%g in (%%f) do if exist "%%g" del "%%g"
)

REM Kiem tra nhanh ban build bang may gia lap (chi doc, khong dieu khien may that)
"dist\DC Power\DC Power.exe" --selftest "Giả lập (Demo)" build\selftest.json
type build\selftest.json

echo.
echo Xong: dist\DC Power\DC Power.exe
pause
exit /b 0

:loi
echo.
echo BUILD LOI - xem thong bao phia tren.
pause
exit /b 1
