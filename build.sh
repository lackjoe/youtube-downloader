#!/bin/bash
# Build YouTube Downloader as macOS .app bundle

set -e

APP_NAME="YouTube Downloader"

echo "=== Building ${APP_NAME} ==="

# Ensure dependencies are installed
pip install -r requirements.txt

# Clean previous build
rm -rf build dist

# Run PyInstaller
pyinstaller \
    --name "${APP_NAME}" \
    --windowed \
    --onedir \
    --noconfirm \
    --add-data "assets:assets" \
    --hidden-import "yt_dlp" \
    --hidden-import "customtkinter" \
    --collect-all "customtkinter" \
    main.py

echo ""
echo "=== Build complete ==="
echo "App bundle: dist/${APP_NAME}.app"
echo "Run: open \"dist/${APP_NAME}.app\""
