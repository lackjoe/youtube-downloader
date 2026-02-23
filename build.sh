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
    --hidden-import "certifi" \
    --collect-all "customtkinter" \
    --collect-all "certifi" \
    main.py

# Ad-hoc code sign to prevent "damaged app" error
echo "Signing app..."
codesign --force --deep --sign - "dist/${APP_NAME}.app"

# Create DMG for distribution
echo "Creating DMG..."
hdiutil create -volname "${APP_NAME}" -srcfolder "dist/${APP_NAME}.app" -ov -format UDZO "dist/${APP_NAME}.dmg"

echo ""
echo "=== Build complete ==="
echo "App bundle: dist/${APP_NAME}.app"
echo "DMG: dist/${APP_NAME}.dmg"
echo "Run: open \"dist/${APP_NAME}.app\""
