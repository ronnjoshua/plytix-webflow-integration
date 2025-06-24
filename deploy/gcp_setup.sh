#!/bin/bash
# GCP VM Setup Script for Plytix-Webflow Integration
# This script sets up the environment on a fresh Ubuntu VM

set -e

echo "🚀 Setting up Plytix-Webflow Integration on GCP VM"
echo "=================================================="

# Colors for output
RED='\\033[0;31m'
GREEN='\\033[0;32m'
YELLOW='\\033[1;33m'
BLUE='\\033[0;34m'
NC='\\033[0m' # No Color

log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   log_error "This script should not be run as root. Please run as regular user with sudo privileges."
   exit 1
fi

# Update system packages
log_info "Updating system packages..."
sudo apt-get update -y
sudo apt-get upgrade -y

# Install Python 3.10+ and pip
log_info "Installing Python and dependencies..."
sudo apt-get install -y python3 python3-pip python3-venv python3-dev
sudo apt-get install -y build-essential libssl-dev libffi-dev
sudo apt-get install -y curl wget git unzip jq

# Install Docker and Docker Compose
log_info "Installing Docker..."
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo usermod -aG docker $USER
    rm get-docker.sh
    log_success "Docker installed"
else
    log_info "Docker already installed"
fi

# Install Docker Compose
if ! command -v docker-compose &> /dev/null; then
    sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    sudo chmod +x /usr/local/bin/docker-compose
    log_success "Docker Compose installed"
else
    log_info "Docker Compose already installed"
fi

# Install Node.js (for any frontend needs)
log_info "Installing Node.js..."
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt-get install -y nodejs

# Create application directory
APP_DIR="/opt/plytix-webflow"
log_info "Creating application directory: $APP_DIR"
sudo mkdir -p $APP_DIR
sudo chown $USER:$USER $APP_DIR

# Create logs directory
sudo mkdir -p /var/log/plytix-webflow
sudo chown $USER:$USER /var/log/plytix-webflow

# Create systemd service directory for user services
mkdir -p ~/.config/systemd/user

# Install Python requirements globally (will be overridden by virtual env)
log_info "Setting up Python environment..."
pip3 install --user virtualenv

# Create helpful aliases
log_info "Setting up shell aliases..."
cat >> ~/.bashrc << 'EOF'

# Plytix-Webflow Integration Aliases
alias plytix='cd /opt/plytix-webflow && ./plytix-cli'
alias plytix-logs='tail -f /var/log/plytix-webflow/sync.log'
alias plytix-status='cd /opt/plytix-webflow && ./plytix-cli status'
alias plytix-start='cd /opt/plytix-webflow && ./deploy/start_services.sh'
alias plytix-stop='cd /opt/plytix-webflow && ./deploy/stop_services.sh'
EOF

# Install monitoring tools
log_info "Installing monitoring tools..."
sudo apt-get install -y htop iftop ncdu tree

# Configure firewall (allow SSH and application ports)
log_info "Configuring firewall..."
sudo ufw --force reset
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow 8000  # FastAPI
sudo ufw allow 5555  # Flower (Celery monitoring)
sudo ufw --force enable

# Create swap file if not exists (for small VMs)
if [ ! -f /swapfile ]; then
    log_info "Creating swap file..."
    sudo fallocate -l 2G /swapfile
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile
    sudo swapon /swapfile
    echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
    log_success "Swap file created"
fi

# Install and configure fail2ban for security
log_info "Installing fail2ban for security..."
sudo apt-get install -y fail2ban
sudo systemctl enable fail2ban
sudo systemctl start fail2ban

# Set up automatic security updates
log_info "Configuring automatic security updates..."
sudo apt-get install -y unattended-upgrades
sudo dpkg-reconfigure -plow unattended-upgrades

# Create deployment script
log_info "Creating deployment scripts..."
cat > /tmp/deploy_app.sh << 'EOF'
#!/bin/bash
# Application deployment script

set -e

APP_DIR="/opt/plytix-webflow"
REPO_URL="$1"

if [ -z "$REPO_URL" ]; then
    echo "Usage: $0 <repository_url>"
    exit 1
fi

echo "🚀 Deploying Plytix-Webflow Integration"

# Clone or update repository
if [ -d "$APP_DIR/.git" ]; then
    echo "📥 Updating existing repository..."
    cd $APP_DIR
    git pull origin main
else
    echo "📥 Cloning repository..."
    git clone $REPO_URL $APP_DIR
    cd $APP_DIR
fi

# Set permissions
sudo chown -R $USER:$USER $APP_DIR

# Create virtual environment
echo "🐍 Setting up Python virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install requirements
echo "📦 Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Make CLI executable
chmod +x plytix-cli

# Create environment configuration
echo "⚙️  Setting up environment configuration..."
if [ ! -f .env ]; then
    cp .env.example .env
    echo "⚠️  Please edit .env file with your API credentials"
fi

# Set up systemd services
echo "🔧 Setting up systemd services..."
./deploy/setup_systemd.sh

echo "✅ Deployment complete!"
echo ""
echo "Next steps:"
echo "1. Edit configuration: nano $APP_DIR/.env"
echo "2. Set up environment: $APP_DIR/plytix-cli env setup production --interactive"
echo "3. Configure mappings: $APP_DIR/plytix-cli mapping list"
echo "4. Start services: $APP_DIR/plytix-cli schedule start"
EOF

chmod +x /tmp/deploy_app.sh
sudo mv /tmp/deploy_app.sh /usr/local/bin/deploy-plytix
log_success "Deployment script created at /usr/local/bin/deploy-plytix"

# Create monitoring script
cat > /tmp/monitor.sh << 'EOF'
#!/bin/bash
# Simple monitoring script for Plytix-Webflow integration

check_service() {
    local service=$1
    if systemctl --user is-active --quiet $service; then
        echo "✅ $service: Running"
    else
        echo "❌ $service: Stopped"
    fi
}

echo "🔍 Plytix-Webflow Integration Status"
echo "=================================="
echo ""

echo "📊 System Resources:"
echo "CPU: $(top -bn1 | grep "Cpu(s)" | awk '{print $2 + $4"%"}')"
echo "Memory: $(free | awk '/^Mem:/{printf "%.1f%%", $3/$2 * 100.0}')"
echo "Disk: $(df -h / | awk 'NR==2{printf "%s", $5}')"
echo ""

echo "🔧 Services:"
check_service "plytix-scheduler"
check_service "plytix-api"
echo ""

echo "📋 Recent Logs:"
tail -5 /var/log/plytix-webflow/sync.log 2>/dev/null || echo "No logs found"
EOF

chmod +x /tmp/monitor.sh
sudo mv /tmp/monitor.sh /usr/local/bin/plytix-monitor
log_success "Monitoring script created at /usr/local/bin/plytix-monitor"

# Create maintenance script
cat > /tmp/maintenance.sh << 'EOF'
#!/bin/bash
# Maintenance script for Plytix-Webflow integration

case "$1" in
    backup)
        echo "📦 Creating backup..."
        backup_dir="/var/backups/plytix-$(date +%Y%m%d_%H%M%S)"
        sudo mkdir -p $backup_dir
        sudo cp -r /opt/plytix-webflow/config $backup_dir/
        sudo cp /opt/plytix-webflow/.env $backup_dir/ 2>/dev/null || true
        sudo tar -czf $backup_dir/logs.tar.gz /var/log/plytix-webflow/
        echo "✅ Backup created: $backup_dir"
        ;;
    logs)
        echo "📋 Log files:"
        ls -la /var/log/plytix-webflow/
        ;;
    cleanup)
        echo "🧹 Cleaning up old logs..."
        sudo find /var/log/plytix-webflow/ -name "*.log" -mtime +30 -delete
        echo "✅ Cleanup complete"
        ;;
    update)
        echo "🔄 Updating application..."
        cd /opt/plytix-webflow
        git pull origin main
        source venv/bin/activate
        pip install --upgrade -r requirements.txt
        systemctl --user restart plytix-scheduler plytix-api
        echo "✅ Update complete"
        ;;
    *)
        echo "Usage: $0 {backup|logs|cleanup|update}"
        exit 1
        ;;
esac
EOF

chmod +x /tmp/maintenance.sh
sudo mv /tmp/maintenance.sh /usr/local/bin/plytix-maintenance
log_success "Maintenance script created at /usr/local/bin/plytix-maintenance"

# Clean up
sudo apt-get autoremove -y
sudo apt-get autoclean

log_success "GCP VM setup completed successfully!"
echo ""
echo "🎉 Setup Summary:"
echo "=================="
echo "✅ System packages updated"
echo "✅ Python 3 and pip installed"
echo "✅ Docker and Docker Compose installed"
echo "✅ Application directory created: $APP_DIR"
echo "✅ Firewall configured"
echo "✅ Security tools installed"
echo "✅ Helpful scripts created:"
echo "   - /usr/local/bin/deploy-plytix"
echo "   - /usr/local/bin/plytix-monitor"
echo "   - /usr/local/bin/plytix-maintenance"
echo ""
echo "📝 Next Steps:"
echo "1. Logout and login again to apply group changes"
echo "2. Deploy your application: deploy-plytix <repository_url>"
echo "3. Configure your environment and API keys"
echo "4. Start monitoring: plytix-monitor"
echo ""
echo "⚠️  Important: You may need to reboot for all changes to take effect"