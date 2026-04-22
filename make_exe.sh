#!/bin/bash

set -e

APP_NAME="DJTool"
SCRIPT_NAME="djtool.py"
#INNO_PATH="C:/Users/engineering/AppData/Local/Programs/Inno Setup 6/iscc.exe"
INNO_PATH="iscc.exe"

if [[ -z $VIRTUAL_ENV ]]; then
  echo "\$VIRUTALN_ENV is empty or not set"
  exit 0
fi


rm -rf dist/* Output/*

pyinstaller --noconfirm  --onefile --windowed --runtime-hook rthook_gettext_safe.py --hidden-import=RapidFffuzz --hidden-import=CTkMessageBox --hidden-import=pyaudio --add-data "djtool.ico:images" djtool.py

"$INNO_PATH" djtool.iss

scp Output/djtool_setup.exe ericg@kzsu.stanford.edu:/media/kzsu-audio-archive1/kzsu-aircheck-archives/featured_programs
