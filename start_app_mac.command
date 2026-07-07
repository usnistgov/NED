#!/bin/bash
# NED Web App launcher (macOS)
#
# Double-click this file to open the NED web app in your browser.
# If macOS blocks it, right-click the file and choose "Open" instead.

cd "$(dirname "$0")" || exit 1

if [ ! -x venv/bin/python ]; then
    echo "The project environment was not found."
    echo "Please run setup_workshop_mac.command first."
    read -r -p "Press Return to close this window..."
    exit 1
fi

if [ ! -f db.sqlite3 ]; then
    echo "The NED database was not found."
    echo "Please run setup_workshop_mac.command first to build it."
    read -r -p "Press Return to close this window..."
    exit 1
fi

cd ui || exit 1
export DB_PATH=../db.sqlite3
export AUTH_ENABLED=false
export STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

echo "Starting the NED web app... a browser tab should open shortly."
echo ""
echo "Keep this window open while using the app."
echo "Press Ctrl+C here (or close this window) to stop the app."
echo ""
../venv/bin/python -m streamlit run app.py
read -r -p "Press Return to close this window..."
