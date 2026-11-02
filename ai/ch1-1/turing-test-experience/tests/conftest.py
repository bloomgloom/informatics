import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config"
LOCAL = ROOT / "local"

# 새로 받은 저장소에서도 시험이 돌도록 setup처럼 설정 파일을 만든다.
for name, example in (("seats.csv", "seats.example.csv"), ("roster_names.txt", "roster_names.example.txt")):
    if not (LOCAL / name).exists():
        LOCAL.mkdir(exist_ok=True)
        shutil.copyfile(CONFIG / example, LOCAL / name)
