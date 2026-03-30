#!/bin/bash

# Servboard Setup Script
echo "--- Servboard Setup starting ---"

# Check for Node.js
if ! command -v node &> /dev/null
then
    echo "Node.js is not installed. Please install it first."
    exit 1
fi

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
echo "Run 'node server.js' to test immediately."
