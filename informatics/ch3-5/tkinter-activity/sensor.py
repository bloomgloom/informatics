"""
온도 센서 시뮬레이터

실제 온도 센서 대신 방의 온도를 흉내 냅니다. 이 파일은 고치지 않고 불러와서 씁니다.

    import sensor
    now = sensor.read()       # 현재 온도 읽기
    sensor.aircon("냉방 중")   # 에어컨에 작동 상태 알리기

- "냉방 중"이면 read()를 부를 때마다 0.1℃씩 내려갑니다.
- "난방 중"이면 read()를 부를 때마다 0.1℃씩 올라갑니다.
- "유지"면 그대로입니다.
- 처음 온도는 26℃입니다. 커널을 다시 시작하면 처음 온도로 돌아갑니다.

실제 온도 센서를 붙이면 read() 안만 센서 값을 읽도록 바꾸면 됩니다.
"""

now = 26.0
state = "유지"


def read():
    global now
    if "냉방" in state:
        now = now - 0.1
    elif "난방" in state:
        now = now + 0.1
    now = round(now, 1)
    return now


def aircon(new_state):
    global state
    state = new_state
