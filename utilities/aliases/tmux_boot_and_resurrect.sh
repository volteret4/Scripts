#!/bin/bash
tmux -f /home/huan/.tmux/tmux.conf 
tmux run-shell ~/.tmux/plugins/tmux-resurrect/scripts/restore.sh