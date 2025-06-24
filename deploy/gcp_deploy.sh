#!/bin/bash
# Complete GCP VM Deployment Script for Plytix-Webflow Integration
# This script sets up the entire application on a fresh Ubuntu VM

set -e

# Configuration
APP_NAME="plytix-webflow-integration"
APP_USER="plytix"
APP_DIR="/opt/$APP_NAME"
REPO_URL="https://github.com/your-username/plytix-webflow-integration.git"  # Update this
SERVICE_FILES_DIR="/etc/systemd/system"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')] $1${NC}"
}

error() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}"
}

warning() {
    echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}"
}

info() {
    echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')] INFO: $1${NC}"
}

# Check if running as root
check_root() {
    if [[ $EUID -eq 0 ]]; then
        error "This script should not be run as root. Please run as a regular user with sudo privileges."
        exit 1
    fi
}

# Update system packages
update_system() {
    log "Updating system packages..."
    sudo apt-get update -y
    sudo apt-get upgrade -y
    sudo apt-get install -y curl wget git vim htop unzip software-properties-common apt-transport-https ca-certificates gnupg lsb-release
}

# Install Docker
install_docker() {
    log "Installing Docker..."
    
    # Remove old versions
    sudo apt-get remove -y docker docker-engine docker.io containerd runc 2>/dev/null || true
    
    # Add Docker's official GPG key
    sudo mkdir -p /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    
    # Add Docker repository
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
    
    # Install Docker
    sudo apt-get update -y
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    
    # Add user to docker group
    sudo usermod -aG docker $USER
    
    # Start and enable Docker
    sudo systemctl start docker
    sudo systemctl enable docker
    
    log "Docker installed successfully"
}

# Install Docker Compose (standalone)
install_docker_compose() {
    log "Installing Docker Compose..."
    
    DOCKER_COMPOSE_VERSION="v2.24.0"
    sudo curl -L "https://github.com/docker/compose/releases/download/$DOCKER_COMPOSE_VERSION/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
    
    # Create symlink for docker-compose plugin compatibility
    sudo ln -sf /usr/local/bin/docker-compose /usr/bin/docker-compose
    
    log "Docker Compose installed successfully"
}

# Create application user
create_app_user() {
    log "Creating application user..."
    
    if ! id "$APP_USER" &>/dev/null; then
        sudo useradd -r -s /bin/bash -d $APP_DIR -m $APP_USER
        log "User $APP_USER created"
    else
        warning "User $APP_USER already exists"
    fi
    
    # Add to docker group
    sudo usermod -aG docker $APP_USER
}

# Setup application directory
setup_app_directory() {
    log "Setting up application directory..."
    
    # Create directory structure
    sudo mkdir -p $APP_DIR/{logs,data,backups}
    sudo chown -R $APP_USER:$APP_USER $APP_DIR
    sudo chmod -R 755 $APP_DIR
    
    # Create logs directory
    sudo mkdir -p /var/log/$APP_NAME
    sudo chown -R $APP_USER:$APP_USER /var/log/$APP_NAME
}

# Clone or update repository
setup_repository() {
    log "Setting up repository..."
    
    if [ -d "$APP_DIR/.git" ]; then
        warning "Repository already exists, updating..."
        sudo -u $APP_USER git -C $APP_DIR pull
    else
        log "Cloning repository..."
        # For now, copy from current directory since we don't have a remote repo
        sudo cp -r $(pwd)/* $APP_DIR/
        sudo chown -R $APP_USER:$APP_USER $APP_DIR
        
        # If you have a remote repository, uncomment this:
        # sudo -u $APP_USER git clone $REPO_URL $APP_DIR
    fi
}

# Setup environment configuration
setup_environment() {
    log "Setting up environment configuration..."
    
    # Copy environment file
    if [ ! -f "$APP_DIR/.env" ]; then
        sudo -u $APP_USER cp $APP_DIR/.env.production $APP_DIR/.env
        warning "Environment file created from template. Please update with actual credentials!"
        warning "Edit $APP_DIR/.env with your API credentials before starting services."
    fi
    
    # Set proper permissions
    sudo chmod 600 $APP_DIR/.env
    sudo chown $APP_USER:$APP_USER $APP_DIR/.env
}

# Setup systemd services
setup_systemd_services() {
    log "Setting up systemd services..."
    
    # Create Docker Compose service
    cat << EOF | sudo tee $SERVICE_FILES_DIR/plytix-integration.service > /dev/null
[Unit]
Description=Plytix-Webflow Integration
Requires=docker.service
After=docker.service
StartLimitIntervalSec=0

[Service]
Type=oneshot
RemainAfterExit=yes
User=$APP_USER
Group=$APP_USER
WorkingDirectory=$APP_DIR
ExecStart=/usr/local/bin/docker-compose -f docker-compose.prod.yml up -d
ExecStop=/usr/local/bin/docker-compose -f docker-compose.prod.yml down
ExecReload=/usr/local/bin/docker-compose -f docker-compose.prod.yml restart
TimeoutStartSec=300
Restart=on-failure
RestartSec=30

[Install]
WantedBy=multi-user.target
EOF

    # Create backup service
    cat << EOF | sudo tee $SERVICE_FILES_DIR/plytix-backup.service > /dev/null
[Unit]
Description=Plytix-Webflow Integration Backup
After=plytix-integration.service

[Service]
Type=oneshot
User=$APP_USER
Group=$APP_USER
WorkingDirectory=$APP_DIR
ExecStart=/bin/bash $APP_DIR/scripts/backup.sh
EOF

    # Create backup timer
    cat << EOF | sudo tee $SERVICE_FILES_DIR/plytix-backup.timer > /dev/null
[Unit]
Description=Daily backup of Plytix-Webflow Integration
Requires=plytix-backup.service

[Timer]
OnCalendar=daily
Persistent=true

[Install]
WantedBy=timers.target
EOF

    # Reload systemd
    sudo systemctl daemon-reload
    
    # Enable services
    sudo systemctl enable plytix-integration.service
    sudo systemctl enable plytix-backup.timer
    
    log "Systemd services configured"
}

# Setup firewall
setup_firewall() {
    log "Configuring firewall..."
    
    # Install and configure UFW
    sudo apt-get install -y ufw
    
    # Default policies
    sudo ufw default deny incoming
    sudo ufw default allow outgoing
    
    # Allow SSH
    sudo ufw allow ssh
    
    # Allow HTTP and HTTPS
    sudo ufw allow 80/tcp
    sudo ufw allow 443/tcp
    
    # Allow API port (if needed for direct access)
    sudo ufw allow 8000/tcp comment 'Plytix API'
    
    # Allow Flower monitoring (restrict to specific IPs in production)
    sudo ufw allow 5555/tcp comment 'Flower Monitoring'
    
    # Enable firewall
    sudo ufw --force enable
    
    log "Firewall configured"
}

# Setup monitoring
setup_monitoring() {
    log "Setting up monitoring..."
    
    # Create monitoring script
    cat << 'EOF' | sudo tee $APP_DIR/scripts/monitor.sh > /dev/null
#!/bin/bash
# System monitoring script

APP_NAME="plytix-webflow-integration"
LOG_FILE="/var/log/$APP_NAME/monitor.log"

# Function to log with timestamp
log_with_timestamp() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> $LOG_FILE
}

# Check if containers are running
check_containers() {
    CONTAINERS=$(docker-compose -f /opt/$APP_NAME/docker-compose.prod.yml ps -q)
    RUNNING_CONTAINERS=$(docker inspect $CONTAINERS | grep '"Status"' | grep -c "running")
    TOTAL_CONTAINERS=$(echo $CONTAINERS | wc -w)
    
    log_with_timestamp "Containers: $RUNNING_CONTAINERS/$TOTAL_CONTAINERS running"
    
    if [ $RUNNING_CONTAINERS -lt $TOTAL_CONTAINERS ]; then
        log_with_timestamp "WARNING: Not all containers are running"
        return 1
    fi
    return 0
}

# Check disk space
check_disk_space() {
    DISK_USAGE=$(df /opt/$APP_NAME | tail -1 | awk '{print $5}' | sed 's/%//')
    log_with_timestamp "Disk usage: $DISK_USAGE%"
    
    if [ $DISK_USAGE -gt 80 ]; then
        log_with_timestamp "WARNING: Disk usage is above 80%"
        return 1
    fi
    return 0
}

# Main monitoring
main() {
    log_with_timestamp "Starting system check"
    
    check_containers
    CONTAINER_STATUS=$?
    
    check_disk_space
    DISK_STATUS=$?
    
    if [ $CONTAINER_STATUS -eq 0 ] && [ $DISK_STATUS -eq 0 ]; then
        log_with_timestamp "System check passed"
    else
        log_with_timestamp "System check failed"
    fi
}

main
EOF

    sudo chmod +x $APP_DIR/scripts/monitor.sh
    sudo chown $APP_USER:$APP_USER $APP_DIR/scripts/monitor.sh
    
    # Create monitoring cron job
    echo "*/5 * * * * /opt/$APP_NAME/scripts/monitor.sh" | sudo -u $APP_USER crontab -
    
    log "Monitoring configured"
}

# Setup SSL certificates (Let's Encrypt)
setup_ssl() {
    log "Setting up SSL certificates..."
    
    # Install certbot
    sudo apt-get install -y certbot
    
    # Create SSL directory
    sudo mkdir -p $APP_DIR/docker/nginx/ssl
    sudo chown -R $APP_USER:$APP_USER $APP_DIR/docker/nginx/ssl
    
    warning "SSL certificates not automatically generated."
    warning "To set up SSL, run: sudo certbot certonly --standalone -d your-domain.com"
    warning "Then copy certificates to $APP_DIR/docker/nginx/ssl/"
}

# Create management scripts
create_management_scripts() {
    log "Creating management scripts..."
    
    # Create start script
    cat << EOF | sudo tee $APP_DIR/scripts/start.sh > /dev/null
#!/bin/bash
# Start Plytix-Webflow Integration
cd $APP_DIR
docker-compose -f docker-compose.prod.yml up -d
echo "Services started. Check status with: $APP_DIR/scripts/status.sh"
EOF

    # Create stop script
    cat << EOF | sudo tee $APP_DIR/scripts/stop.sh > /dev/null
#!/bin/bash
# Stop Plytix-Webflow Integration
cd $APP_DIR
docker-compose -f docker-compose.prod.yml down
echo "Services stopped."
EOF

    # Create status script
    cat << EOF | sudo tee $APP_DIR/scripts/status.sh > /dev/null
#!/bin/bash
# Check status of Plytix-Webflow Integration
cd $APP_DIR
echo "=== Container Status ==="
docker-compose -f docker-compose.prod.yml ps
echo ""
echo "=== Service Status ==="
systemctl status plytix-integration.service --no-pager
echo ""
echo "=== Recent Logs ==="
docker-compose -f docker-compose.prod.yml logs --tail=10 api
EOF

    # Create update script
    cat << EOF | sudo tee $APP_DIR/scripts/update.sh > /dev/null
#!/bin/bash
# Update Plytix-Webflow Integration
cd $APP_DIR
echo "Stopping services..."
docker-compose -f docker-compose.prod.yml down
echo "Pulling latest changes..."
git pull
echo "Rebuilding containers..."
docker-compose -f docker-compose.prod.yml build --no-cache
echo "Starting services..."
docker-compose -f docker-compose.prod.yml up -d
echo "Update completed. Check status with: $APP_DIR/scripts/status.sh"
EOF

    # Create backup script
    cat << EOF | sudo tee $APP_DIR/scripts/backup.sh > /dev/null
#!/bin/bash
# Backup Plytix-Webflow Integration data
BACKUP_DIR="$APP_DIR/backups"
DATE=\$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="\$BACKUP_DIR/backup_\$DATE.tar.gz"

mkdir -p \$BACKUP_DIR

echo "Creating backup..."
tar -czf \$BACKUP_FILE \\
    --exclude="$APP_DIR/backups" \\
    --exclude="$APP_DIR/logs" \\
    --exclude="$APP_DIR/.git" \\
    $APP_DIR

# Keep only last 7 backups
find \$BACKUP_DIR -name "backup_*.tar.gz" -mtime +7 -delete

echo "Backup created: \$BACKUP_FILE"
EOF

    # Make scripts executable
    sudo chmod +x $APP_DIR/scripts/*.sh
    sudo chown -R $APP_USER:$APP_USER $APP_DIR/scripts/
    
    log "Management scripts created"
}

# Main deployment function
main() {
    log "Starting GCP VM deployment for Plytix-Webflow Integration"
    
    check_root
    update_system
    install_docker
    install_docker_compose
    create_app_user
    setup_app_directory
    setup_repository
    setup_environment
    setup_systemd_services
    setup_firewall
    setup_monitoring
    setup_ssl
    create_management_scripts
    
    log "Deployment completed successfully!"
    echo ""
    info "Next steps:"
    info "1. Edit $APP_DIR/.env with your actual API credentials"
    info "2. Start services: sudo systemctl start plytix-integration"
    info "3. Check status: $APP_DIR/scripts/status.sh"
    info "4. View logs: docker-compose -f $APP_DIR/docker-compose.prod.yml logs -f"
    echo ""
    info "Available management commands:"
    info "- Start:  $APP_DIR/scripts/start.sh"
    info "- Stop:   $APP_DIR/scripts/stop.sh"
    info "- Status: $APP_DIR/scripts/status.sh"
    info "- Update: $APP_DIR/scripts/update.sh"
    info "- Backup: $APP_DIR/scripts/backup.sh"
    echo ""
    warning "Remember to:"
    warning "- Configure SSL certificates for production"
    warning "- Set up monitoring alerts"
    warning "- Configure regular backups"
    warning "- Review firewall rules for your specific needs"
}

# Run main function
main "$@"