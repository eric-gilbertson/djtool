#!/bin/bash

APP_NAME="DJTool"
SCRIPT_NAME="djtool.py"

if [[ -z $VIRTUAL_ENV ]]; then
  echo "\$VIRUTALN_ENV is empty or not set"
  exit 0
fi

rm -rf dist/*
pyinstaller --noconfirm  --onefile --windowed --runtime-hook rthook_gettext_safe.py --hidden-import=RapidFffuzz --hidden-import=CTkMessageBox --hidden-import=pyaudio --add-data "djtool.ico:images" djtool.py
#pyinstaller --noconfirm  --onefile --windowed --runtime-hook rthook_gettext_safe.py --hidden-import=pyaudio --add-data "yt-dlp.exe:helpers" --add-data "ffmpeg.exe:helpers" --add-data "djtool.png:images" djtool.py
#rm -rf dist/djtool
scp dist/djtool.exe ericg@kzsu.stanford.edu:/media/kzsu-audio-archive1/kzsu-aircheck-archives/featured_programs


# Build the .app bundle with PyInstaller
#pyinstaller --windowed --name "$APP_NAME" "$SCRIPT_NAME"
#pyinstaller --onedir --windowed --add-data "djtool.png:images" djtool.py

# Create the DMG from the .app bundle
#create-dmg "./dist/$APP_NAME.app"

#create-dmg \
#  --app-bundle "dist/djtool.app" \
#  --icon "djtool.app" 100 100 \
#  --app-drop-link 300 100 \
#  "dist/DJTool.dmg"
#
##create-dmg --app-bundle "dist/DJTool.app"  --icon "DJTool.app" 100 100  --app-drop-link 300 100  "dist/DJTool.dmg"
#
##hdiutil create  -volname "DJTool"  -srcfolder dist/DJTool.app  -ov  -format UDZO  DJTool.dmg
#
#echo "Packaging complete. The DMG installer is in the dist/ directory."
#
#create-dmg \
#    --volname "DJTool Installer" \
#    --volicon "icon.icns" \
#    --window-pos 200 120 \
#    --window-size 800 400 \
#    --icon-size 100 \
#    --icon "Application.app" 200 190 \
#    --hide-extension "Application.app" \
#    --app-drop-link 600 185 \
#    "DJTool.dmg" dist/"
