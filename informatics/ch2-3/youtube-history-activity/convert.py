"""
유튜브 시청 기록(구글 테이크아웃 JSON)을 CSV로 바꿉니다. 고치지 않고 실행만 합니다.

    %run convert.py

local/watch-history.json 을 읽어 local/watch.csv 로 저장합니다.
제목, 채널, 시각만 남기고 광고와 YouTube Music 기록은 뺍니다.
"""

import csv
import json
import os
import sys

SOURCE = os.path.join("local", "watch-history.json")
TARGET = os.path.join("local", "watch.csv")

if len(sys.argv) > 1:
    SOURCE = sys.argv[1]

if not os.path.exists(SOURCE):
    print(f"파일이 없습니다: {SOURCE}")
    print("시청 기록을 JSON으로 받아 local 폴더에 watch-history.json으로 넣어 주세요.")
    print("시청 기록이 없으면 sample-watch.csv를 쓰면 됩니다.")
    raise SystemExit

with open(SOURCE, encoding="utf-8") as f:
    records = json.load(f)


def clean_title(title):
    """'Watched 제목' 또는 '제목 을(를) 시청했습니다.'에서 제목만 남깁니다."""
    if title.startswith("Watched "):
        title = title[len("Watched "):]
    for suffix in ("을(를) 시청했습니다.", " 시청함"):
        if title.endswith(suffix):
            title = title[: -len(suffix)]
    return title.strip()


rows = []
for record in records:
    if record.get("header") != "YouTube":          # YouTube Music 등은 뺌
        continue
    details = " ".join(d.get("name", "") for d in record.get("details", []))
    if "Ads" in details or "광고" in details:       # 광고는 뺌
        continue
    subtitles = record.get("subtitles") or [{}]
    rows.append({
        "title": clean_title(record.get("title", "")),
        "channel": subtitles[0].get("name", ""),
        "time": record.get("time", ""),
    })

os.makedirs("local", exist_ok=True)
with open(TARGET, "w", encoding="utf-8-sig", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=["title", "channel", "time"])
    writer.writeheader()
    writer.writerows(rows)

print(f"영상 {len(rows)}개를 {TARGET}로 저장했습니다.")
