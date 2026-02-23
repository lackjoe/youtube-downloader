@echo off
REM Build YouTube Downloader for Windows (.exe)

echo === Building YouTube Downloader (Windows) ===

pip install -r requirements.txt

rmdir /s /q build 2>nul
rmdir /s /q dist 2>nul

pyinstaller ^
    --name "YouTube Downloader" ^
    --windowed ^
    --onedir ^
    --noconfirm ^
    --add-data "assets;assets" ^
    --hidden-import "yt_dlp" ^
    --hidden-import "customtkinter" ^
    --collect-all "customtkinter" ^
    main.py

echo.
echo === Build complete ===
echo Executable: dist\YouTube Downloader\YouTube Downloader.exe
pause
