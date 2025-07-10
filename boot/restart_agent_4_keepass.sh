#!/usr/bin/env bash
#
# Script Name: restart_agent_4_keepass.sh 
# Description: Restart ssh-agent before running keepassxc.
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 

# Notes:
#   Dependencies:
#       keepassxc
#

export SSH_AUTH_SOCK=/run/user/1000/ssh-agent.socket
systemctl --user restart ssh-agent.service
keepassxc
