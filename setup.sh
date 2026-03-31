#!/bin/bash

# Servboard Setup Script
echo "--- Servboard Setup starting ---"

# Check for Python3
if ! command -v python3 &> /dev/null
then
    echo "Python3 is not installed. Please install it first."
    exit 1
fi

# Install dependencies
echo "Installing Python dependencies..."
pip3 install -r requirements.txt


# Create directory structure
mkdir -p public

# Update systemd service user
USER_NAME=$(whoami)
SERVICE_PATH="/etc/systemd/system/servboard.service"

echo "Configuring systemd service for user: $USER_NAME"
sed -i "s/User=ed/User=$USER_NAME/g" servboard.service
sed -i "s|WorkingDirectory=/home/ed/Davit/Projects/Servboard|WorkingDirectory=$(pwd)|g" servboard.service

echo "To install the service, run:"
echo "sudo cp servboard.service $SERVICE_PATH"
echo "sudo systemctl daemon-reload"
echo "sudo systemctl enable servboard"
echo "sudo systemctl start servboard"

echo "--- Setup Complete ---"
echo "Run 'python3 main.py' to test immediately."


