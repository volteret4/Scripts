#!/usr/bin/env bash
#
# Script Name: restart_agent_4_keepass.sh 
# Description: Restart ssh-agent before running keepassxc.
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# TODO: 
# Notes:
#   Dependencies:
#       keepassxc
#


systemctl --user restart ssh-agent.service
keepassxc
