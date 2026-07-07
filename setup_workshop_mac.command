#!/bin/bash
# NED Workshop Setup (macOS)
#
# Double-click this file to set up everything needed to run NED locally.
# If macOS blocks it ("cannot be opened because it is from an unidentified
# developer"), right-click the file and choose "Open" instead.

cd "$(dirname "$0")" || exit 1

fail() {
    echo ""
    echo "------------------------------------------------------------"
    echo " Setup did NOT complete. Please review the message above,"
    echo " or ask a workshop host for help."
    echo "------------------------------------------------------------"
    read -r -p "Press Return to close this window..."
    exit 1
}

echo "============================================================"
echo " NED - Nonstructural Element Database - Workshop Setup"
echo "============================================================"
echo ""
echo "This script will:"
echo "  1. Install the 'uv' Python manager (if not already installed)"
echo "  2. Create a private Python 3.12 environment in ./venv"
echo "  3. Install all required packages"
echo "  4. Build the NED database from the source JSON data"
echo ""
echo "No admin rights are needed. Nothing is installed outside your"
echo "home folder and this project folder. Safe to re-run anytime."
echo ""

export PYTHONUTF8=1

# ---- Step 1: find or install uv ----------------------------------
if command -v uv >/dev/null 2>&1 || [ -x "$HOME/.local/bin/uv" ]; then
    echo "[1/4] uv is already installed."
else
    echo "[1/4] Installing uv (this does not require admin rights)..."
    curl -LsSf https://astral.sh/uv/install.sh | sh || fail
fi
export PATH="$HOME/.local/bin:$PATH"
command -v uv >/dev/null 2>&1 || fail

# ---- Step 2: create the Python environment -----------------------
echo ""
echo "[2/4] Setting up a Python 3.12 environment in ./venv..."
if [ -x venv/bin/python ]; then
    echo "       Found an existing environment - reusing it."
else
    uv venv venv --python 3.12 || fail
fi

# ---- Step 3: install packages -------------------------------------
echo ""
echo "[3/4] Installing required packages..."
uv pip install --python venv/bin/python -r requirements-workshop.txt || fail

# ---- Step 4: build the database -----------------------------------
echo ""
echo "[4/4] Building the NED database (migrate + ingest)..."
venv/bin/python manage.py migrate || fail
venv/bin/python manage.py ingest || fail

echo ""
echo "============================================================"
echo " Setup complete!"
echo "============================================================"
echo ""
echo "This window is now a ready-to-use NED terminal. The '(venv)'"
echo "prefix on the prompt means the project environment is active."
echo ""
echo "Next steps:"
echo "  * To open the NED web app: double-click start_app_mac.command"
echo "  * To run project commands, type them right here, e.g.:"
echo "      python manage.py import_model --model Experiment --input_file my_data.csv"
echo "      python manage.py ingest"
echo ""
echo "Need this terminal again later? Double-click this file again."
echo "Re-running is safe and only takes a few seconds."
echo ""
exec bash --rcfile venv/bin/activate -i
