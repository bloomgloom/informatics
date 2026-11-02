#!/usr/bin/env python3
"""참가자 전원이 질문자와 증인으로 활동하는 한 판 전체 흐름 시뮬레이터."""
import argparse
import asyncio
import random

import httpx


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:9000")
    parser.add_argument("--students", type=int, default=30)
    parser.add_argument("--token", required=True, help="서버를 켤 때 정한 비밀번호")
    args = parser.parse_args()
    async with httpx.AsyncClient(base_url=args.url, timeout=60) as client:
        await client.post("/api/admin/setup", json={"admin_token": args.token})
        for seat in range(1, args.students + 1):
            headers = {"X-Debug-Seat": str(seat)}
            await client.get("/api/student", headers=headers)
            response = await client.post("/api/join", headers=headers)
            response.raise_for_status()
        (await client.post("/api/admin/action", json={"admin_token": args.token, "action": "start"})).raise_for_status()
        for seat in range(1, args.students + 1):
            (await client.post("/api/ack-rules", headers={"X-Debug-Seat": str(seat)})).raise_for_status()
        print(f"{args.students}명 참여 및 게임 시작 완료")

        while True:
            admin = (await client.get("/api/admin/state", headers={"X-Admin-Token": args.token})).json()
            phase = admin["phase"]
            active = [s for s in admin["seats"] if s["participating"] and not s["eliminated"]]
            if phase == "Q_WRITE":
                for s in active:
                    (await client.post("/api/submit", headers={"X-Debug-Seat": str(s["seat"])},
                                       json={"kind": "question", "text": random.choice([
                                           "요즘 뭐가 제일 재밌어?", "급식 어땠음?", "주말에 뭐함?",
                                       ])})).raise_for_status()
            elif phase == "A_WRITE":
                for s in active:
                    (await client.post("/api/submit", headers={"X-Debug-Seat": str(s["seat"])},
                                       json={"kind": "answer", "text": random.choice([
                                           "그냥 게임함ㅋㅋ", "급식은 좀 별로", "집에서 잤지 뭐",
                                       ])})).raise_for_status()
            elif phase == "JUDGE":
                for s in active:
                    (await client.post("/api/submit", headers={"X-Debug-Seat": str(s["seat"])},
                                       json={"kind": "judge", "choice": random.choice(["A", "B"]),
                                             "confidence": random.randint(1, 5),
                                             "reason": "말투가 자연스러움"})).raise_for_status()
            elif phase == "RESULTS":
                assert len(admin["groups"]) == args.students
                print(f"{args.students}명 · 5턴 · 게임 {len(admin['groups'])}개 시뮬레이션 성공")
                break
            (await client.post("/api/admin/action",
                               json={"admin_token": args.token, "action": "next"})).raise_for_status()


if __name__ == "__main__":
    asyncio.run(main())
