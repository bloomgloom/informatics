#!/bin/sh
# 수업용 서버를 켭니다.
cd "$(dirname "$0")" || exit 1
exec python3 server.py start
