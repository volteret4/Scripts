#!/usr/bin/env bash
#
# Script Name: chat_GPT.sh 
# Description: _ _ _
# Author: volteret4
# Repository: https://github.com/volteret4/
# License: 
# TODO: 
# Notes:
#
#

carpeta=$(dirname $(readlink "$0"))
source "${carpeta}/.env"

#GPT_API=""


curl -X POST -H "Authorization: Bearer ${api}" -H "Content-Type: application/json" -d '{
"model": "gpt-3.5-turbo",
"messages": [
{
    "role": "system",
    "content": "You are"
},
{
    "role": "user",
    "content": "'"${1}"'"
}
]
}' "https://api.openai.com/v1/chat/completions"
