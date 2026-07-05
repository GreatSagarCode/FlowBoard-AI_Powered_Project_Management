#!/bin/bash
set -e

APP_NAME="flowboard"
APP_DIR="/home/ubuntu/${APP_NAME}"
NGINX_SITE="/etc/nginx/sites-available/${APP_NAME}"
NGINX_ENABLED="/etc/nginx/sites-enabled/${APP_NAME}"

echo ">>> Updating packages"
sudo apt update
sudo apt install -y python3-pip python3-venv nginx

echo ">>> Creating app directory"
sudo mkdir -p "$APP_DIR"
sudo chown -R "$USER":"$USER" "$APP_DIR"

echo ">>> Ensure code is copied to $APP_DIR before continuing."
echo "    If not already there, run: git clone <repo-url> $APP_DIR"
cd "$APP_DIR"

echo ">>> Setting up Python virtualenv"
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

echo ">>> Ensuring SQLite directory exists"
mkdir -p instance

echo ">>> Creating systemd service"
sudo cp "$APP_DIR/${APP_NAME}.service" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable "$APP_NAME"
sudo systemctl restart "$APP_NAME"

echo ">>> Setting up nginx"
sudo cp "$APP_DIR/nginx/${APP_NAME}" "$NGINX_SITE"
sudo ln -sf "$NGINX_SITE" "$NGINX_ENABLED"
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx

echo ">>> Deployment complete."
