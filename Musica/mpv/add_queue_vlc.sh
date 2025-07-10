#!/usr/bin/env bash
#
# Script Name: add_queue_vlc.sh 
# Description: _ _ _
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# Notes:
#
#



#
url="$(xclip -o)"
yt="^https://www.youtube*|^http://youtube*|^http://www.youtu.be*|^https://youtu.be*"

if [[ "${url}" =~ $yt ]]
    then

        echo "yt link"
        mpv "$(youtube-dl -ge --audio-quality 0 -f best "${url}" | sed '1~2 s/ /_/g')"
		if [ $? != 0 ]
			then
				notify-send 'Ver videos en mpv' -t 10000 'Error'
			else
				notify-send 'Video añadido' -t 10000
		fi
    else

		"${HOME}"/Scripts/tareas/if_firefox_active.sh
		sleep 0.5
		xdotool key Ctrl+l
		xdotool key ctrl+c

		if [[ "${url}" =~ $yt ]]
			then

				echo "yt link extraido de firefox"
				mpv "$(youtube-dl -ge --audio-quality 0 -f best "${url}" | sed '1~2 s/ /_/g')
"
			else

				echo "bc link"
				mpv "$(youtube-dl -ge --write-thumbnail "${url}" | sed '1~2 s/ /_/g')"

		fi
fi
