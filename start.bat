@echo off
ECHO "Checking for pip..."
pip --version >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    ECHO "pip not found, trying python -m pip"
    SET PIP_CMD=python -m pip
) ELSE (
    SET PIP_CMD=pip
)

ECHO "Installing dependencies..."
%PIP_CMD% install -r requirements.txt

ECHO "Starting server with waitress..."
python -m waitress --host 127.0.0.1 --port 5000 app:app
