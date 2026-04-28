#!/usr/bin/env bash
set -euo pipefail

show_help() {
  cat <<'EOF'
Usage:
  sudo bash deploy/setup_single_server.sh [options]

Options:
  --domain <name>       Domain for Nginx server_name (default: _)
  --app-dir <path>      Project directory on server (default: /opt/urban_water_ditection)
  --app-user <user>     User/group to run service (default: www-data)
  --service-name <name> Systemd service name (default: urban-water)
  --help                Show this help message
EOF
}

DOMAIN="_"
APP_DIR="/opt/urban_water_ditection"
APP_USER="www-data"
SERVICE_NAME="urban-water"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --domain)
      DOMAIN="$2"
      shift 2
      ;;
    --app-dir)
      APP_DIR="$2"
      shift 2
      ;;
    --app-user)
      APP_USER="$2"
      shift 2
      ;;
    --service-name)
      SERVICE_NAME="$2"
      shift 2
      ;;
    --help)
      show_help
      exit 0
      ;;
    *)
      echo "Unknown argument: $1"
      show_help
      exit 1
      ;;
  esac
done

if [[ "${EUID}" -ne 0 ]]; then
  echo "Please run as root (sudo)."
  exit 1
fi

if [[ ! -d "$APP_DIR" ]]; then
  echo "Project directory not found: $APP_DIR"
  echo "Copy this repository to the server path first."
  exit 1
fi

echo "Installing system packages..."
apt update
apt install -y python3 python3-venv python3-pip nginx

if ! id "$APP_USER" >/dev/null 2>&1; then
  echo "Creating user $APP_USER ..."
  useradd --system --no-create-home --shell /usr/sbin/nologin "$APP_USER"
fi

echo "Preparing virtual environment and dependencies..."
cd "$APP_DIR"
if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

if [[ ! -f deploy/.env ]]; then
  cp deploy/.env.example deploy/.env
fi

echo "Writing systemd service..."
cat >/etc/systemd/system/${SERVICE_NAME}.service <<EOF
[Unit]
Description=Urban Water Loss Detection (Gunicorn)
After=network.target

[Service]
Type=simple
User=${APP_USER}
Group=${APP_USER}
WorkingDirectory=${APP_DIR}
EnvironmentFile=${APP_DIR}/deploy/.env
ExecStart=${APP_DIR}/.venv/bin/gunicorn --config ${APP_DIR}/deploy/gunicorn.conf.py wsgi:app
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

echo "Writing Nginx site config..."
cat >/etc/nginx/sites-available/${SERVICE_NAME}.conf <<EOF
server {
    listen 80;
    server_name ${DOMAIN};

    client_max_body_size 20M;

    location /static/ {
        alias ${APP_DIR}/static/;
        expires 7d;
        add_header Cache-Control "public";
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_set_header Connection "";
    }
}
EOF

ln -sf /etc/nginx/sites-available/${SERVICE_NAME}.conf /etc/nginx/sites-enabled/${SERVICE_NAME}.conf
if [[ -f /etc/nginx/sites-enabled/default ]]; then
  rm -f /etc/nginx/sites-enabled/default
fi

echo "Starting services..."
systemctl daemon-reload
systemctl enable ${SERVICE_NAME}
systemctl restart ${SERVICE_NAME}
nginx -t
systemctl restart nginx

echo "Deployment complete."
echo "Service status: systemctl status ${SERVICE_NAME}"
echo "Open: http://${DOMAIN}"
