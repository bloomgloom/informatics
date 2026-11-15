#!/bin/sh
# config.example.json으로 config.json을 만듭니다.
cd "$(dirname "$0")" || exit 1
exec python3 server.py setup
