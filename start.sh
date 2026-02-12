#!/bin/bash

# Check for pip
if ! command -v pip &> /dev/null
then
    echo "pip could not be found, trying python -m pip"
    PIP_CMD="python -m pip"
else
    PIP_CMD="pip"
fi

# Install dependencies
echo "Installing dependencies..."
$PIP_CMD install -r requirements.txt

# Check if gunicorn is installed, if not, install it
if ! $PIP_CMD show gunicorn &> /dev/null
then
    echo "gunicorn not found, installing..."
    $PIP_CMD install gunicorn
fi


# Start the server
echo "Starting server with gunicorn..."
python -m gunicorn -w 4 'app:app'
