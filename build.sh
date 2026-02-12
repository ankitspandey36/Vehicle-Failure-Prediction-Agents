#!/bin/bash
# Build script for Render deployment

# Update pip and install wheels first
pip install --upgrade pip setuptools wheel

# Install dependencies with binary wheels only
pip install --only-binary :all: -r requirements.txt

# If that fails, try without strict binary requirement
if [ $? -ne 0 ]; then
    pip install -r requirements.txt
fi
