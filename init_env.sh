#!/bin/bash

UPDATE=false

while getopts "u" flag; do
    case $flag in
        u) UPDATE=true ;;
    esac
done

if [ "$UPDATE" = true ]; then
    echo "Updating dependencies..."
    venv/bin/pip install -r requirements.txt -r requirements.txt
else
    echo "Initializing environment..."
    python3 -m venv venv
    venv/bin/pip install -r requirements.txt -r requirements.txt
fi
