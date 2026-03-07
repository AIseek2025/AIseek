#!/bin/bash
set -e

# Setup Worker
echo "Setting up Worker..."
cd worker
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
deactivate
cd ..

# Setup Web
echo "Setting up Web..."
cd web
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
deactivate
cd ..

# Create placeholder video directory
mkdir -p worker/assets
echo "Please place 'bg_placeholder.mp4' in worker/assets/"

echo "Setup complete!"
