fakelock — сборка .exe для Windows
===================================

Собрать exe можно только НА Windows (или через Wine/CI), на Linux
кросс-компиляции для Windows нет. Поэтому:

1. Скопируй папку ~/fakelock целиком на Windows-машину:
   fakelock.py
   build_exe.bat
   assets\          (cat.png, pink_art.png, sfx\*.wav)

2. Двойной клик по build_exe.bat
   (нужен Python 3.10+ с python.org, галочка "Add python.exe to PATH")

3. Через минуту появится dist\fakelock.exe — один файл, всё внутри:
   арт, розовый экран, звуки.

Запуск exe: сразу фуллскрин на весь экран.
Выход: Esc.  Ctrl+Q — тоже выход.  Ctrl+M — вкл/выкл звук.

Флаги (если запускать из консоли):
   fakelock.exe --windowed   окно вместо фуллскрина
   fakelock.exe --no-music   без звука

Примечание: PyInstaller-сборки иногда ругает Windows Defender
(ложное срабатывание на упаковщик). Если это мешает — собери
с ключом --onedir вместо --onefile.
