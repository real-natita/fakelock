@echo off
chcp 65001 >nul
cd /d "%~dp0"

set PY=python
where python >nul 2>&1 || set PY=py -3
%PY% --version >nul 2>&1 || goto nopython

echo === сборка fakelock.exe ===
echo.

%PY% -m pip install --upgrade pyinstaller pillow numpy
if errorlevel 1 goto fail

%PY% -m PyInstaller --noconfirm --clean --onefile --noconsole ^
  --name fakelock ^
  --add-data "assets;assets" ^
  fakelock.py
if errorlevel 1 goto fail

echo.
echo ============================================
echo   ГОТОВО:  dist\fakelock.exe
echo   Кот, розовый арт и звуки упакованы внутрь.
echo   Запуск двойным кликом - сразу фуллскрин.
echo   Выход: Esc  (или Ctrl+Q, или Ctrl+M - звук)
echo ============================================
pause
exit /b 0

:nopython
echo.
echo [ОШИБКА] Python не найден.
echo Поставь Python 3.10+ с python.org и включи "Add python.exe to PATH".
pause
exit /b 1

:fail
echo.
echo [ОШИБКА] Сборка не удалась. Смотри текст ошибки выше.
pause
exit /b 1
