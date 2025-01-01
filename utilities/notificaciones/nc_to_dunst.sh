#!/bin/bash
while true; do
  msg=$(nc -l -p 8585 -s 192.168.1.191)
  notify-send "Notificación remota" "$msg"
done
