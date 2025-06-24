#!/bin/bash
# Setup systemd services for Plytix-Webflow integration

set -e

APP_DIR="/opt/plytix-webflow"
USER_SERVICE_DIR="$HOME/.config/systemd/user"

echo "🔧 Setting up systemd user services..."

# Create user service directory
mkdir -p $USER_SERVICE_DIR

# Create API service
cat > $USER_SERVICE_DIR/plytix-api.service << EOF
[Unit]
Description=Plytix-Webflow API Server
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$APP_DIR
Environment=PATH=$APP_DIR/venv/bin
ExecStart=$APP_DIR/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=default.target
EOF

# Create scheduler service
cat > $USER_SERVICE_DIR/plytix-scheduler.service << EOF
[Unit]
Description=Plytix-Webflow Scheduler
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$APP_DIR
Environment=PATH=$APP_DIR/venv/bin
ExecStart=$APP_DIR/venv/bin/python -m app.scheduler.scheduler_daemon
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=default.target
EOF

# Create Celery worker service (optional)
cat > $USER_SERVICE_DIR/plytix-worker.service << EOF
[Unit]
Description=Plytix-Webflow Celery Worker
After=network.target redis.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$APP_DIR
Environment=PATH=$APP_DIR/venv/bin
ExecStart=$APP_DIR/venv/bin/celery -A app.tasks.celery_app worker --loglevel=info
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=default.target
EOF

# Create Celery beat service (optional)
cat > $USER_SERVICE_DIR/plytix-beat.service << EOF
[Unit]
Description=Plytix-Webflow Celery Beat Scheduler
After=network.target redis.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$APP_DIR
Environment=PATH=$APP_DIR/venv/bin
ExecStart=$APP_DIR/venv/bin/celery -A app.tasks.celery_app beat --loglevel=info
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=default.target
EOF

# Enable lingering for the user (allows user services to run without login)
sudo loginctl enable-linger $USER

# Reload systemd user daemon
systemctl --user daemon-reload

echo "✅ Systemd services created successfully!"
echo ""
echo "📋 Available services:"
echo "  - plytix-api.service      (FastAPI server)"
echo "  - plytix-scheduler.service (Main scheduler)"
echo "  - plytix-worker.service   (Celery worker - optional)"
echo "  - plytix-beat.service     (Celery beat - optional)"
echo ""
echo "🔧 Service management commands:"
echo "  systemctl --user start plytix-scheduler"
echo "  systemctl --user stop plytix-scheduler"
echo "  systemctl --user enable plytix-scheduler"
echo "  systemctl --user status plytix-scheduler"
echo "  journalctl --user -u plytix-scheduler -f"
echo ""
echo "💡 To enable auto-start:"
echo "  systemctl --user enable plytix-scheduler"
echo "  systemctl --user enable plytix-api"