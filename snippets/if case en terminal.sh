#!/usr/bin/env bash
#
# Script Name: if_case_terminal.sh
# Description: Personal snippet to create selectable options within a script launched from terminal.
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# TODO: 
# Notes:
#   Example snippet.
#

PS3='Selecciona momento: '
options=("ambient" "deep" "ket" "awakenings" "techno" "metal")
select opt in "${options[@]}"
do
    case $opt in
        "ambient")
            echo "you chose choice 1"
            ;;
        "deep")
            echo "you chose choice 2"
            ;;
        "ket")
            echo "you chose choice $REPLY which is $opt"
            ;;
        "awakenings")
            break
            ;;
        *) echo "invalid option $REPLY";;
        "techno")
            break
            ;;
        *) echo "invalid option $REPLY";;
         "metal")
            break
            ;;
        *) echo "invalid option $REPLY";; 
    esac
done

