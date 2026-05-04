#!/bin/bash
# X-Platform device setup script.
# Run once on a fresh Syslogic Orin to configure networking, services, and dependencies.
#
# Usage:
#   ./scripts/setup.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV_PATH="$REPO_ROOT/venv"
USER_NAME="${SUDO_USER:-$(whoami)}"
USER_HOME="/home/$USER_NAME"

# Must be run as root for network and systemd configuration
if [ "$EUID" -ne 0 ]; then
    echo "Run with sudo: sudo ./scripts/setup.sh"
    exit 1
fi

echo ""
echo "=================================================="
echo " X-Platform Device Setup"
echo "=================================================="
echo " Repo:  $REPO_ROOT"
echo " User:  $USER_NAME"
echo ""

# --------------------------------------------------
# 1. Python venv and dependencies
# --------------------------------------------------
echo "[1/4] Setting up Python venv..."

if [ ! -d "$VENV_PATH" ]; then
    sudo -u "$USER_NAME" python3 -m venv "$VENV_PATH"
    echo "      Created venv at $VENV_PATH"
else
    echo "      Venv already exists at $VENV_PATH"
fi

sudo -u "$USER_NAME" "$VENV_PATH/bin/pip" install --upgrade pip -q
sudo -u "$USER_NAME" "$VENV_PATH/bin/pip" install -r "$REPO_ROOT/requirements.txt" -q
echo "      Dependencies installed."

# Install farm-ng SDK if available
AMIGA_ADK="$USER_HOME/Amiga/amiga-adk"
if [ -d "$AMIGA_ADK" ]; then
    echo "      Installing farm-ng SDK from $AMIGA_ADK..."
    sudo -u "$USER_NAME" "$VENV_PATH/bin/pip" install -e "$AMIGA_ADK" -q
    echo "      farm-ng SDK installed."
else
    echo "      WARNING: farm-ng SDK not found at $AMIGA_ADK — skipping."
    echo "               Clone amiga-adk and re-run if needed."
fi

# --------------------------------------------------
# 2. Network configuration
# --------------------------------------------------
echo ""
echo "[2/4] Configuring network interfaces..."

# lan1 — toughbook link (192.168.1.0/24)
if nmcli connection show lan1 &>/dev/null; then
    nmcli connection modify lan1 \
        ipv4.method manual \
        ipv4.addresses 192.168.1.1/24 \
        ipv4.gateway "" \
        connection.autoconnect yes
    echo "      Updated lan1 → 192.168.1.1/24"
else
    nmcli connection add \
        type ethernet \
        ifname lan1 \
        con-name lan1 \
        ipv4.method manual \
        ipv4.addresses 192.168.1.1/24 \
        connection.autoconnect yes
    echo "      Created lan1 → 192.168.1.1/24"
fi

# poe1 — OAK-D camera link (10.95.76.0/24)
if nmcli connection show poe1 &>/dev/null; then
    nmcli connection modify poe1 \
        ipv4.method manual \
        ipv4.addresses 10.95.76.1/24 \
        ipv4.gateway "" \
        connection.autoconnect yes
    echo "      Updated poe1 → 10.95.76.1/24"
else
    nmcli connection add \
        type ethernet \
        ifname poe1 \
        con-name poe1 \
        ipv4.method manual \
        ipv4.addresses 10.95.76.1/24 \
        connection.autoconnect yes
    echo "      Created poe1 → 10.95.76.1/24"
fi

nmcli connection up lan1 2>/dev/null && echo "      lan1 up." || echo "      WARNING: lan1 failed to come up (cable unplugged?)"
nmcli connection up poe1 2>/dev/null && echo "      poe1 up." || echo "      WARNING: poe1 failed to come up (camera unplugged?)"

# --------------------------------------------------
# 3. Systemd services
# --------------------------------------------------
echo ""
echo "[3/4] Installing systemd services..."

cat > /etc/systemd/system/x-platform-gui.service << EOF
[Unit]
Description=X-Platform Flask GUI
After=network-online.target
Wants=network-online.target

[Service]
User=$USER_NAME
WorkingDirectory=$REPO_ROOT
ExecStart=$REPO_ROOT/scripts/start_gui.sh
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

cat > /etc/systemd/system/x-platform-camera.service << EOF
[Unit]
Description=X-Platform OAK-D Camera Streamer
After=network-online.target
Wants=network-online.target

[Service]
User=$USER_NAME
WorkingDirectory=$REPO_ROOT
ExecStart=$REPO_ROOT/scripts/camera.sh
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable x-platform-gui.service x-platform-camera.service
echo "      Services installed and enabled."

# --------------------------------------------------
# 4. Script permissions
# --------------------------------------------------
echo ""
echo "[4/4] Ensuring scripts are executable..."
chmod +x "$REPO_ROOT"/scripts/*.sh
echo "      Done."

# --------------------------------------------------
# Summary
# --------------------------------------------------
echo ""
echo "=================================================="
echo " Setup complete. Start services now with:"
echo "   sudo systemctl start x-platform-gui x-platform-camera"
echo ""
echo " Check status:"
echo "   systemctl status x-platform-gui x-platform-camera"
echo ""
echo " View logs:"
echo "   journalctl -fu x-platform-gui"
echo "   journalctl -fu x-platform-camera"
echo ""
echo " Toughbook static IP settings:"
echo "   IP:      192.168.1.24"
echo "   Mask:    255.255.255.0"
echo "   Gateway: (blank)"
echo "   DNS:     (blank)"
echo "=================================================="
echo ""
