#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3가 필요합니다. https://www.python.org/downloads/ 에서 설치해 주세요."
  exit 1
fi

python3 - <<'PY'
import sys
if sys.version_info < (3, 11):
    raise SystemExit("Python 3.11 이상이 필요합니다.")
print(f"Python {sys.version.split()[0]} 확인")
PY

python3 -m venv .venv
rm -f .venv/.setup-complete
.venv/bin/python -m pip install --upgrade pip
# 가상환경을 다른 폴더에서 복사한 경우 pip 실행 파일의 shebang은 이전 경로를
# 가리킬 수 있다. 항상 현재 가상환경의 Python을 통해 pip를 실행한다.
.venv/bin/python -m pip install -r requirements.txt
touch .venv/.setup-complete
mkdir -p logs local
# 교실에 맞게 고칠 설정 파일을 예시에서 만든다. 이미 있으면 그대로 둔다.
for name in roster_names.txt seats.csv; do
  example="config/${name%.*}.example.${name##*.}"
  [[ -f "local/$name" ]] || cp "$example" "local/$name"
done
echo
echo "설치 완료. ./start.sh 를 실행하세요."

