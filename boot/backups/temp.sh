#!/usr/bin/env bash
#
# Script Name: temp.sh 
# Description: _ _ _
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 

# Notes:
#
#


cat > temporal.service << 'ENDTXT'
[Unit]
Description=Back up my dotfiles

[Service]
Type=oneshot
ExecStart=bash /home/huan/Scripts/backups/backup-arco.sh
ENDTXT

cat > temporal.timer << 'ENDTXT'
[Unit]
Description=Run backupdot at start an every day

[Timer]
OnBootSec=20min
OnCalendar=weekly

[Install]
WantedBy=timers.target
ENDTXT

mkdir -p ~/.config/systemd/user
mv temporal.service ~/.config/systemd/user/
mv temporal.timer ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable temporal.timer
systemctl --user start temporal.timer