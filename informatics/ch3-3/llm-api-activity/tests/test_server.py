"""가짜 API를 띄워 놓고 실제 anthropic 라이브러리로 서버와 노트북을 시험합니다."""
import builtins
import contextlib
import io
import json
import os
import sys
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT))
import anthropic
import server

REAL_KEY = "sk-real-secret"
STUDENT_KEY = "sk-class-test"
MODEL = "claude-haiku-5-5"
state = {}
mu = threading.Lock()


def reset(**kw):
    state.clear()
    state.update(calls=0, active=0, peak=0, mode="ok", delay=0.0, bodies=[], keys=[], used=0, window=0.0, budget=0)
    state.update(kw)
    server.class_count = 0
    server.student_counts.clear()
    server.recent_requests.clear()


class Mock(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        with mu:
            state["calls"] += 1
            state["active"] += 1
            state["peak"] = max(state["peak"], state["active"])
            state["bodies"].append(body)
            state["keys"].append(self.headers.get("x-api-key"))
            limited = False
            if state["mode"] == "budget":
                now = time.monotonic()
                if now - state["window"] > 1:
                    state["window"], state["used"] = now, 0
                state["used"] += 1
                limited = state["used"] > state["budget"]
        time.sleep(state["delay"])
        with mu:
            state["active"] -= 1

        mode, headers = state["mode"], {}
        if mode == "always429":
            code, headers = 429, {"retry-after": "0"}
        elif mode == "529":
            code, headers = 529, {"retry-after": "0"}
        elif mode == "long429":
            code, headers = 429, {"retry-after": "999"}
        elif limited:
            code, headers = 429, {"retry-after": "1"}
        elif mode == "401":
            code = 401
        elif mode == "400":
            code = 400
        else:
            code = 200

        if code == 200:
            prompt = str(body["messages"][0]["content"])
            text = state["key_text"].pop(0) if "수업용 암호" in prompt else "apple,사과" if "퀴즈" in str(body.get("system")) else f"메시지 {len(body['messages'])}개 받음"
            data = {"id": "msg_1", "type": "message", "role": "assistant", "model": body["model"],
                    "content": ([] if body.get("thinking") == {"type": "disabled"} else [{"type": "thinking", "thinking": "음", "signature": "x"}]) + [{"type": "text", "text": text}], "stop_reason": "end_turn",
                    "stop_sequence": None, "usage": {"input_tokens": 3, "output_tokens": 5}}
        else:
            message = f"upstream {REAL_KEY}" if code == 401 else "upstream says no"
            data = {"type": "error", "error": {"type": "api_error", "message": message}}
        encoded = json.dumps(data).encode()
        self.send_response(code)
        for key, value in headers.items():
            self.send_header(key, value)
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def start(handler):
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd.server_port


server.API_URL = f"http://127.0.0.1:{start(Mock)}/v1/messages"
server.config = {"api_key": REAL_KEY, "student_key": STUDENT_KEY, "model": MODEL, "max_tokens": 100, "port": 0,
                 "limit_per_minute": 100000, "limit_per_student": 100000, "limit_per_class": 100000, "max_input_chars": 50, "max_concurrent": 5}
server.api_slots = threading.BoundedSemaphore(5)
base_url = f"http://127.0.0.1:{start(server.Handler)}"
client = anthropic.Anthropic(base_url=base_url, api_key=STUDENT_KEY, max_retries=0)

failed = []


def check(name, condition, extra=""):
    print("OK  " if condition else "FAIL", name, extra)
    if not condition:
        failed.append(name)


def create(**kw):
    kw.setdefault("model", MODEL)
    kw.setdefault("max_tokens", 50)
    kw.setdefault("messages", [{"role": "user", "content": "안녕"}])
    return client.messages.create(**kw)


def error_of(func):
    try:
        func()
    except anthropic.APIStatusError as error:
        return error
    return None


# --- 공식 형식
reset()
response = create()
check("응답 형식", response.content[0].text == "메시지 1개 받음" and response.usage.output_tokens == 5 and response.role == "assistant")
check("실제 키로 교체", state["keys"] == [REAL_KEY])
check("모델 목록", [m.id for m in client.models.list()] == [MODEL])
reset()
create(max_tokens=4000, system="역할", extra_body={"temperature": 0.5})
body = state["bodies"][0]
check("max_tokens 상한", body["max_tokens"] == 100)
check("system, temperature 전달", body["system"] == "역할" and body["temperature"] == 0.5)
reset()
create(system=[{"type": "text", "text": "역할"}], messages=[{"role": "user", "content": [{"type": "text", "text": "a"}]}])
check("글자 블록 형식", state["calls"] == 1)

# --- 생각 블록
reset()
response = create()
check("Haiku는 생각 끔", state["bodies"][0]["thinking"] == {"type": "disabled"} and len(response.content) == 1)
reset()
server.config["model"] = "claude-sonnet-5-5"
response = create(model="claude-sonnet-5-5")
check("다른 모델은 끄지 않고 응답에서 뺌", "thinking" not in state["bodies"][0] and response.content[0].text == "메시지 1개 받음")
server.config["model"] = MODEL

# --- 거절
reset()
wrong = anthropic.Anthropic(base_url=base_url, api_key="sk-wrong", max_retries=0)
check("잘못된 수업용 키 401", isinstance(error_of(lambda: wrong.messages.create(model=MODEL, max_tokens=5, messages=[{"role": "user", "content": "a"}])), anthropic.AuthenticationError))
check("모델 목록도 키 필요", isinstance(error_of(lambda: list(wrong.models.list())), anthropic.AuthenticationError))
error = error_of(lambda: create(model="claude-opus-5-5"))
check("다른 모델 거절", isinstance(error, anthropic.BadRequestError) and MODEL in error.body["error"]["message"], error.body["error"]["message"])
check("스트리밍 거절", isinstance(error_of(lambda: create(extra_body={"stream": True})), anthropic.BadRequestError))
check("도구 거절", isinstance(error_of(lambda: create(extra_body={"tools": []})), anthropic.BadRequestError))
check("긴 입력 거절", isinstance(error_of(lambda: create(messages=[{"role": "user", "content": "가" * 51}])), anthropic.BadRequestError))
check("이미지 거절", isinstance(error_of(lambda: create(messages=[{"role": "user", "content": [{"type": "image", "source": {"type": "url", "url": "http://x"}}]}])), anthropic.BadRequestError))
check("거절은 API 호출 없음", state["calls"] == 0)

# --- API 오류
reset(mode="401")
error = error_of(create)
check("API 인증 오류 502, 키 숨김", error.status_code == 502 and REAL_KEY not in str(error.body))
reset(mode="400")
error = error_of(create)
check("API 400 안내 전달", error.status_code == 400 and error.body["error"]["message"] == "upstream says no")

# --- 사용량 제한
reset()
server.config["limit_per_minute"] = 2
codes = [getattr(error_of(create), "status_code", 200) for _ in range(3)]
check("분당 제한", codes == [200, 200, 429], str(codes))
server.config["limit_per_minute"] = 100000
reset()
server.config["limit_per_student"] = 2
codes = [getattr(error_of(create), "status_code", 200) for _ in range(3)]
check("학생당 수업 제한", codes == [200, 200, 429] and "이번 수업에서" in error_of(create).body["error"]["message"], str(codes))
server.student_counts["1.2.3.4"] = 2
check("다른 학생 횟수와 따로 셈", state["calls"] == 2 and server.student_counts["127.0.0.1"] == 2)
server.config["limit_per_student"] = 100000
reset()
server.config["limit_per_class"] = 1
codes = [getattr(error_of(create), "status_code", 200) for _ in range(2)]
check("수업 전체 제한", codes == [200, 429] and "전체 사용량" in error_of(create).body["error"]["message"], str(codes))
server.config["limit_per_class"] = 100000
reset()
create()
error_of(lambda: create(model="claude-opus-5-5"))
check("거절된 요청은 횟수에 안 셈", server.student_counts["127.0.0.1"] == 1)


# --- 혼잡
def burst(count):
    def one(_):
        error = error_of(create)
        return error.status_code if error else 200
    with ThreadPoolExecutor(count) as pool:
        return Counter(pool.map(one, range(count)))


reset(delay=0.5)
check("30명 동시, 호출 5개 이하", burst(30) == {200: 30} and state["peak"] == 5, f"peak={state['peak']}")
reset(mode="budget", budget=4, delay=0.1)
counts = burst(30)
check("한도 걸려도 재시도로 성공", counts == {200: 30}, f"{dict(counts)} 호출 {state['calls']}회")
for mode in ("always429", "529"):
    reset(mode=mode)
    error = error_of(create)
    check(f"{mode}: 5번 시도 후 529 안내", error.status_code == 529 and "사용자가 많아요" in error.body["error"]["message"] and state["calls"] == 5)
reset(mode="long429")
started = time.time()
check("대기가 너무 길면 바로 안내", error_of(create).status_code == 529 and state["calls"] == 1 and time.time() - started < 2)
server.TOTAL_WAIT, server.MIN_CALL_TIME = 3, 2
reset(delay=2.5)
counts = burst(8)
check("시간 부족하면 호출 없이 안내", counts == {200: 5, 529: 3} and state["calls"] == 5, str(dict(counts)))
server.TOTAL_WAIT, server.MIN_CALL_TIME = 100, 15
check("자리 반환", server.api_slots._value == 5)

# --- 수업용 키 만들기
for texts, expected in ((["we-love-python"], "we-love-python"), (["I am a teacher."], "i-am-a-teacher"), (["안녕", "the-cat-likes-fish"], "the-cat-likes-fish")):
    reset(key_text=list(texts))
    check(f"수업용 키 {texts}", server.make_student_key() == expected and state["bodies"][0]["model"] == MODEL)
reset(key_text=["안녕", "하나", "one two three four five six seven eight"])
try:
    server.make_student_key()
    check("이상한 답 3번이면 실패", False)
except ValueError:
    check("이상한 답 3번이면 실패", state["calls"] == 3)

# --- setup은 config.json만 만들고, 예전 파일에 남은 키는 지웁니다.
import tempfile

with tempfile.TemporaryDirectory() as folder:
    saved_path = server.CONFIG_PATH
    server.CONFIG_PATH = Path(folder) / "config.json"
    with contextlib.redirect_stdout(io.StringIO()):
        server.setup()
        server.setup()
    example = json.loads(server.EXAMPLE_PATH.read_text(encoding="utf-8"))
    check("setup: 예시 그대로 복사", json.loads(server.CONFIG_PATH.read_text(encoding="utf-8")) == example)
    check("예시에 키 없음", "api_key" not in example)
    server.CONFIG_PATH.write_text(json.dumps({"api_key": "sk-old", "port": 9}), encoding="utf-8")
    loaded = server.load_config()
    check("예전 키 삭제", loaded["port"] == 9 and "api_key" not in loaded and "sk-old" not in server.CONFIG_PATH.read_text(encoding="utf-8"))
    server.CONFIG_PATH = saved_path

# 해설지는 비공개 저장소에 있습니다. 없으면 해설지 시험을 건너뜁니다.
ANSWER_KEY = ROOT.parents[3] / "informatics-private/informatics/ch3-3/llm-api-activity/llm-api-activity.ipynb"
student = json.loads((ROOT / "llm-api-activity.ipynb").read_text(encoding="utf-8"))
teacher_code = []
if ANSWER_KEY.exists():
    # --- 해설지를 처음부터 끝까지 실행
    reset()
    server.config["max_input_chars"] = 4000
    teacher = json.loads(ANSWER_KEY.read_text(encoding="utf-8"))
    inputs = iter(["과일", "apple"])
    original_input = builtins.input
    builtins.input = lambda prompt="": (print(prompt, end=""), next(inputs))[1]
    namespace = {}
    for cell in teacher["cells"]:
        if cell["cell_type"] != "code":
            continue
        source = "".join(cell["source"]).replace("http://선생님IP:8000", base_url).replace("수업용키", STUDENT_KEY)
        if "server.accept()" in source:  # 실행하면 기다리는 챗봇 칸은 아래에서 따로 시험합니다.
            chatbot_code = source
            continue
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            exec(source, namespace)
        print(f"--- {source.splitlines()[0][:45]}\n{output.getvalue().rstrip()}")
    builtins.input = original_input
    for name in ("ANTHROPIC_BASE_URL", "ANTHROPIC_API_KEY"):
        os.environ.pop(name, None)

    # --- 챗봇 서버: 앞에서 만든 ask로 답합니다. 실행은 학생 선택이므로 코드가 맞는지 확인합니다.
    import socket as socket_module

    check("챗봇 칸: writefile 없음", "%%writefile" not in chatbot_code and "input(" not in chatbot_code)
    with socket_module.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        chatbot_port = probe.getsockname()[1]
    chatbot_output = io.StringIO()


    def run_chatbot():
        with contextlib.redirect_stdout(chatbot_output):
            exec(chatbot_code.replace("6000", str(chatbot_port)), namespace)


    chatbot = threading.Thread(target=run_chatbot, daemon=True)
    chatbot.start()
    guest = None
    for _ in range(100):
        try:
            guest = socket_module.create_connection(("127.0.0.1", chatbot_port), timeout=20)
            break
        except OSError:
            time.sleep(0.1)
    guest.sendall("떡볶이 있어요?".encode())
    answer = guest.recv(1024).decode()
    guest.close()
    chatbot.join(timeout=10)
    check("챗봇 칸: 손님에게 답 전달", bool(answer) and not chatbot.is_alive(), answer[:40])

# --- 활동지: 설치 칸 외에는 코드 칸이 비어 있어야 합니다.
student_code = ["".join(c["source"]) for c in student["cells"] if c["cell_type"] == "code"]
if ANSWER_KEY.exists():
    teacher_code = ["".join(c["source"]) for c in teacher["cells"] if c["cell_type"] == "code"]
check("활동지 첫 칸은 설치 코드", "pip" in student_code[0])
check("활동지 나머지 코드 칸 비어 있음", all(not code.strip() or code.startswith("# 여기에") for code in student_code[1:]), f"{len(student_code)}칸")
markdown = "\n".join("".join(c["source"]) for c in student["cells"] if c["cell_type"] == "markdown")
check("활동지에 코드가 보이지 않음", "```python" not in markdown and not any(code in markdown for code in teacher_code[1:]))
check("활동지에 설명 있음", all(word in markdown for word in ("채팅에서 코드로", "API 키", "중계 서버", "코드 형식은 동일")))
check("활동지 단계 9에 input 없음", "while True" not in markdown and "input(" not in markdown)
for word in ("[교사]", "QUIZ_RULE", "sk-", "해설지"):
    check(f"활동지에 '{word}' 없음", word not in markdown)

print("\n실패:", failed if failed else "없음")
sys.exit(1 if failed else 0)
