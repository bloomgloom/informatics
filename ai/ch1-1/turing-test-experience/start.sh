#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if [[ ! -x .venv/bin/python || ! -f .venv/.setup-complete || requirements.txt -nt .venv/.setup-complete || ! -f local/seats.csv ]]; then
  echo "먼저 ./setup.sh 를 실행합니다."
  ./setup.sh
fi

exec .venv/bin/python -m app.main "$@"

