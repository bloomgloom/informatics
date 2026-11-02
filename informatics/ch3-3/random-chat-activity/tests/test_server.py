"""실제 소켓으로 교사 프로그램과 해설지 코드를 시험합니다. API는 가짜로 대신합니다."""
import json
import socket
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT))
import server

# 해설지는 비공개 저장소에 있습니다. 없으면 해설지 시험을 건너뜁니다.
ANSWER_DIR = ROOT.parents[3] / "informatics-private/informatics/ch3-3/random-chat-activity"

mock = {"fail": False, "calls": 0, "bodies": []}


class Mock(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        mock["calls"] += 1
        mock["bodies"].append(body)
        prompt = body["messages"][0]["content"]
        text = "반가워요!"
        if "검사기" in prompt:
            text = '{"ok":false,"reason":"괴롭힘"}' if "못생겼" in prompt else '{"ok":true}'
        data = {"content": [{"type": "thinking", "thinking": "음"}, {"type": "text", "text": text}], "usage": {}}
        encoded = json.dumps(data).encode()
        self.send_response(500 if mock["fail"] else 200)
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


mock_server = ThreadingHTTPServer(("127.0.0.1", 0), Mock)
threading.Thread(target=mock_server.serve_forever, daemon=True).start()
server.API_URL = f"http://127.0.0.1:{mock_server.server_port}/"
server.config = {"api_key": "sk-test", "model": "claude-haiku-5-5", "port": 0, "student_port": 6000,
                 "student_ip_start": 101, "student_ip_end": 103, "scan_interval": 3, "reply_limit": 5, "max_chars": 200,
                 "min_interval": 0, "strike_limit": 3, "mute_seconds": 60, "max_students": 100,
                 "llm_limit_per_class": 3000, "blocked_words": ["김철수"]}
log_path = Path(tempfile.mkstemp(suffix=".jsonl")[1])
server.log_file = log_path.open("a", encoding="utf-8")
listener = socket.create_server(("127.0.0.1", 0), backlog=128)
SERVER_PORT = listener.getsockname()[1]
threading.Thread(target=server.accept_loop, args=(listener,), daemon=True).start()

# 시험에서는 모두 같은 IP이므로, 클라이언트의 문 번호로 학생 서버를 찾습니다.
server_port_of = {}
server.phone_address = lambda address: ("127.0.0.1", server_port_of.get(address[1], closed_port()))

failed = []


def closed_port():
    with socket.create_server(("127.0.0.1", 0)) as s:
        return s.getsockname()[1]


def check(name, condition, extra=""):
    print("OK  " if condition else "FAIL", name, extra)
    if not condition:
        failed.append(name)


def wait_until(condition, timeout=3):
    end = time.time() + timeout
    while time.time() < end:
        if condition():
            return True
        time.sleep(0.02)
    return False


def talk(sock, text):
    sock.sendall((text + "\n").encode())
    sock.settimeout(3)
    return sock.recv(4096).decode()


class FakeStudent:
    """학생 서버와 클라이언트를 소켓으로 흉내 냅니다."""

    def __init__(self):
        self.listener = socket.create_server(("127.0.0.1", 0))
        self.port = self.listener.getsockname()[1]
        self.client = socket.socket()
        self.client.bind(("127.0.0.1", 0))
        server_port_of[self.client.getsockname()[1]] = self.port
        self.heard = []  # 내 서버로 들어온 말
        self.conn = None
        threading.Thread(target=self.accept, daemon=True).start()
        self.client.connect(("127.0.0.1", SERVER_PORT))

    def accept(self):
        self.conn, _ = self.listener.accept()
        while True:
            try:
                data = self.conn.recv(4096)
            except OSError:
                return
            if not data:
                self.heard.append(None)
                return
            self.heard.append(data.decode().strip())

    def say(self, text):
        return talk(self.client, text)

    def answer(self, text):
        self.conn.sendall((text + "\n").encode())

    def heard_text(self, text):
        return wait_until(lambda: any(line and text in line for line in self.heard))

    def number(self):
        return next(s.number for s in server.students.values() if s.port == self.port)


def reset(mode):
    server.mode = mode
    server.matching_started = False
    for student in list(server.students.values()):
        server.remove(student, "시험")
    server.banned_ips.clear()
    server.reported_pairs.clear()
    server.active_targets.clear()
    mock["fail"] = False
    time.sleep(0.05)


def students_ready(count):
    return wait_until(lambda: len(server.students) == count)


# --- 교사가 서버
reset("server")
c = socket.create_connection(("127.0.0.1", SERVER_PORT))
check("server: LLM 답장", "반가워요!" in talk(c, "안녕"))
check("생각 끔", mock["bodies"][-1].get("thinking") == {"type": "disabled"})
check("server: 빈 줄에도 답함", "내용을 입력" in talk(c, ""))
for i in range(3):
    last = talk(c, f"말 {i}")
last = talk(c, "다섯째")
check("server: 5번째에 인사", "안녕히 계세요" in last and "/끝" in last)
calls = mock["calls"]
check("server: 이후에는 LLM 안 씀", "대화가 끝났습니다" in talk(c, "더") and mock["calls"] == calls)
c.close()
check("server: 끊으면 정리", wait_until(lambda: not server.students))
c = socket.create_connection(("127.0.0.1", SERVER_PORT))
check("server: 다시 접속 가능", "반가워요!" in talk(c, "또 왔어요"))
key = server.config["api_key"]
server.config["api_key"] = ""
check("키 없으면 고정 답장", '"안녕" 잘 받았습니다.' in talk(c, "안녕"))
server.config["api_key"] = key
mock["fail"] = True
check("LLM 실패해도 고정 답장", '"안녕2" 잘 받았습니다.' in talk(c, "안녕2"))
mock["fail"] = False
reset("server")

# --- 차단 (교사가 서버)
c = socket.create_connection(("127.0.0.1", SERVER_PORT))
for text, reason in (("내 번호 010-1234-5678", "개인정보"), ("http://x.kr 들어와", "링크")):
    check(f"규칙 차단: {reason}", reason in talk(c, text))
check("규칙 차단: 욕설", "초 동안" in talk(c, "시 발 아"))  # 세 번째 차단이라 일시 차단 안내가 나옵니다.
reset("server")
c = socket.create_connection(("127.0.0.1", SERVER_PORT))
check("차단 단어", "차단 단어" in talk(c, "김철수 맞지"))
check("LLM 차단", "괴롭힘" in talk(c, "너 진짜 못생겼어"))
check("3회 차단 시 일시 차단", "초 동안" in talk(c, "시발"))
check("일시 차단 중", "지금은 보낼 수 없습니다" in talk(c, "이제 보낼래"))
reset("server")
c = socket.create_connection(("127.0.0.1", SERVER_PORT))
check("길이 제한", "200자까지" in talk(c, "가" * 201))
check("없는 명령", "없는 명령" in talk(c, "/next"))
reset("server")

# --- kick
c = socket.create_connection(("127.0.0.1", SERVER_PORT))
talk(c, "안녕")
server.run_command(f"kick {next(iter(server.students))}")
check("kick", wait_until(lambda: not server.students))
again = socket.create_connection(("127.0.0.1", SERVER_PORT))
check("kick 뒤 재접속 막음", "막았습니다" in talk(again, "다시"))
reset("server")

# --- 교사가 클라이언트: 시점이 다른 학생을 계속 찾음
reset("client")
ports = [closed_port(), closed_port()]
real_scan_targets = server.scan_targets
server.scan_targets = lambda: [("127.0.0.1", p) for p in ports]
server.scan_once()
check("client: 꺼진 서버는 그냥 넘어감", wait_until(lambda: not server.active_targets) and not server.students)
late = socket.create_server(("127.0.0.1", ports[0]))
server.scan_once()
conn, _ = late.accept()
conn.settimeout(3)
check("client: 늦게 켠 서버에 접속, 먼저 인사", conn.recv(1024).decode() == "안녕하세요?")
check("client: 답하면 LLM 답장", "반가워요!" in talk(conn, "안녕하세요 선생님"))
late.settimeout(0.5)
server.scan_once()
try:
    late.accept()
    check("client: 접속 중에는 다시 걸지 않음", False)
except TimeoutError:
    check("client: 접속 중에는 다시 걸지 않음", True)
conn.close()
check("client: 학생이 끝내면 정리", wait_until(lambda: not server.students and not server.active_targets))
late.settimeout(3)
server.scan_once()
conn, _ = late.accept()
check("client: 학생이 서버를 다시 켜면 다시 접속", conn.recv(1024).decode() == "안녕하세요?")
conn.close()
late.close()
wait_until(lambda: not server.active_targets)
reset("client")

server.scan_targets = real_scan_targets
own = server.local_ip()
targets = server.scan_targets()
check("범위: 교사와 같은 대역의 끝자리만", all(host.rsplit(".", 1)[0] == own.rsplit(".", 1)[0] and port == 6000 for host, port in targets)
      and sorted(int(host.rsplit(".", 1)[1]) for host, _ in targets if host != own) == [n for n in (101, 102, 103) if f"{own.rsplit('.', 1)[0]}.{n}" != own])

# --- 랜덤
reset("random")
closed = socket.create_connection(("127.0.0.1", SERVER_PORT))
check("random: 내 서버가 꺼져 있으면 안내", "내 서버에 연결할 수 없습니다" in talk(closed, "안녕"))
a, b, d = FakeStudent(), FakeStudent(), FakeStudent()
check("random: 접속", students_ready(3))
check("random: Enter 전에는 안내만", "매칭을 시작하면" in a.say("누구 없어요") and not b.heard and not d.heard)
server.run_command("")
check("random: 홀수도 모두 이어짐", wait_until(lambda: all(s.target and s.caller for s in server.students.values())))
check("random: 자기 자신과 안 이어짐", all(s.target is not s and s.caller is not s for s in server.students.values()))
by_port = {x.port: x for x in (a, b, d)}
target = by_port[next(s for s in server.students.values() if s.port == a.port).target.port]
a.client.sendall("반가워\n".encode())
check("random: 내 클라이언트 -> 상대 서버", target.heard_text("반가워"))
check("random: IP가 보이지 않음", not any(line and "127.0.0.1" in line for line in target.heard))
target.answer("나도 반가워")
a.client.settimeout(3)
check("random: 상대 서버 -> 내 클라이언트", "나도 반가워" in a.client.recv(1024).decode())
check("random: 차단", "괴롭힘" in a.say("너 진짜 못생겼어") and not target.heard_text("못생겼"))
check("random: 차단된 쪽은 다시 말할 차례", "개인정보" in a.say("010-1234-5678"))
others = [x for x in (a, b, d) if x is not target and x is not a]
report_pair = next(s for s in server.students.values() if s.port == a.port)
check("random: 신고", "신고가 접수" in a.say("/신고"))
check("random: 신고한 쌍 기록", frozenset((("127.0.0.1", a.port), ("127.0.0.1", target.port))) in server.reported_pairs)
wait_until(lambda: False, 0.2)
now = next(s for s in server.students.values() if s.port == a.port)
check("random: 신고한 상대와 다시 안 이어짐", now.target is None or now.target.port != target.port)
d2 = next(x for x in others)
d2.client.close()
check("random: 나가면 그 학생만 정리", wait_until(lambda: len(server.students) == 2))
check("random: 나간 학생의 서버 창도 닫힘", wait_until(lambda: None in d2.heard))
reset("random")

group = [FakeStudent() for _ in range(31)]
students_ready(31)
server.run_command("")
links = list(server.students.values())
check("31명 모두 이어짐", all(s.target and s.caller and s.target.caller is s and s.target is not s for s in links))
left = group[0]
left.client.close()
check("한 명이 나가면 남은 학생끼리 다시 이어짐",
      wait_until(lambda: len(server.students) == 30 and all(s.target and s.caller for s in server.students.values()), 3))
reset("random")

# --- 기록
server.log_file.flush()
entries = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
message = next(e for e in entries if e.get("text") == "반가워")
check("기록: 시간, IP, 내용", all(key in message for key in ("time", "ip", "partner_ip", "text")))
check("기록: 차단 원문 포함", any(e.get("blocked") == "개인정보" and "010" in e["text"] for e in entries))
check("기록: 매칭, 신고, 답장", {"match", "report", "reply"} <= {e["event"] for e in entries})


# --- 해설지 코드를 실제 프로세스로 실행
def code_cells(name):
    notebook = json.loads((ANSWER_DIR / name).read_text(encoding="utf-8"))
    cells = ["".join(c["source"]) for c in notebook["cells"] if c["cell_type"] == "code"]
    check(f"{name} 코드 칸이 파일로 저장됨", all(c.startswith("%%writefile ") for c in cells))
    return [c.split("\n", 1)[1] for c in cells]  # 터미널에서 실행하는 내용은 첫 줄 뒤입니다.


def start_program(code, port):
    code = code.replace("6000", str(port)).replace("선생님IP", "127.0.0.1").replace(", 5050)", f", {SERVER_PORT})")
    return subprocess.Popen([sys.executable, "-u", "-c", code], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True)


if ANSWER_DIR.exists():
    server_code = code_cells("random-chat-activity-server.ipynb")
    client_code = code_cells("random-chat-activity-client.ipynb")
    check("서버 코드 칸 2개, 클라이언트 3개", len(server_code) == 2 and len(client_code) == 3)
    check("단계 3은 주소만 다름", client_code[2].replace('"선생님IP", 5050', '"127.0.0.1", 6000') == client_code[1])

    port = closed_port()
    receiver = start_program(server_code[0], port)
    time.sleep(0.5)
    sender = start_program(client_code[0], port)
    sender.wait(timeout=5)
    output = receiver.communicate(timeout=5)[0]
    check("1-1", "클라이언트: 안녕하세요" in output and "연결됨" in output, output.strip().replace("\n", " / ")[:80])

    # 1-2: 번갈아 대화하고, 서버가 /끝을 해도 양쪽이 끝납니다.
    port = closed_port()
    receiver = start_program(server_code[1], port)
    time.sleep(0.5)
    sender = start_program(client_code[1], port)
    receiver.stdin.write("서버 말\n/끝\n")
    receiver.stdin.flush()
    sender.stdin.write("첫째\n둘째\n")
    sender.stdin.flush()
    server_output = receiver.communicate(timeout=5)[0]
    client_output = sender.communicate(timeout=5)[0]
    check("1-2 서버 창", "클라이언트: 첫째" in server_output and "클라이언트: 둘째" in server_output and receiver.returncode == 0)
    check("1-2 클라이언트 창", "서버: 서버 말" in client_output and sender.returncode == 0)

    # 1-2: 클라이언트가 /끝을 해도 양쪽이 끝납니다.
    port = closed_port()
    receiver = start_program(server_code[1], port)
    time.sleep(0.5)
    sender = start_program(client_code[1], port)
    sender.communicate("/끝\n", timeout=5)
    check("1-2 /끝: 서버도 끝남", "연결이 끊겼습니다" in receiver.communicate(timeout=5)[0] and receiver.returncode == 0)

    # 단계 2: 학생 서버 코드로 교사 클라이언트와 대화
    reset("client")
    port = closed_port()
    server.scan_targets = lambda: [("127.0.0.1", port)]
    receiver = start_program(server_code[1], port)
    time.sleep(0.5)
    server.scan_once()
    receiver.stdin.write("안녕하세요 선생님\n/끝\n")
    receiver.stdin.flush()
    output = receiver.communicate(timeout=5)[0]
    check("단계 2: 교사가 먼저 인사", "클라이언트: 안녕하세요?" in output)
    check("단계 2: 답장을 받음", "클라이언트: 반가워요!" in output, output.replace("\n", " / ")[:120])
    server.scan_targets = real_scan_targets
    wait_until(lambda: not server.active_targets)

    # 단계 3: 학생 클라이언트 코드로 교사 서버와 대화
    reset("server")
    sender = start_program(client_code[2], closed_port())
    output = sender.communicate("안녕\n/끝\n", timeout=5)[0]
    check("단계 3: 답장을 받음", "서버: 반가워요!" in output, output.replace("\n", " / ")[:120])

# --- 활동지
for side in ("server", "client"):
    student = json.loads((ROOT / f"random-chat-activity-{side}.ipynb").read_text(encoding="utf-8"))
    code = ["".join(c["source"]) for c in student["cells"] if c["cell_type"] == "code"]
    markdown = "\n".join("".join(c["source"]) for c in student["cells"] if c["cell_type"] == "markdown")
    check(f"{side} 활동지 코드 칸에 저장 줄만 있음", code and all(c.startswith("%%writefile ") and len(c.strip().splitlines()) == 1 for c in code), f"{len(code)}칸")
    check(f"{side} 활동지에 코드가 보이지 않음", "```python" not in markdown)
    check(f"{side} 활동지에 교사용 내용 없음", "[교사]" not in markdown)
    if ANSWER_DIR.exists():
        teacher = json.loads((ANSWER_DIR / f"random-chat-activity-{side}.ipynb").read_text(encoding="utf-8"))
        answers = ["".join(c["source"]) for c in teacher["cells"] if c["cell_type"] == "code"]
        check(f"{side} 활동지에 해설 코드 없음", not any(a in markdown for a in answers))
server_sheet = json.loads((ROOT / "random-chat-activity-server.ipynb").read_text(encoding="utf-8"))
sheet_text = "\n".join("".join(c["source"]) for c in server_sheet["cells"])
check("활동지에 IP와 포트 설명", "집 주소" in sheet_text and "문 번호" in sheet_text)

# --- setup은 config.json만 만들고, 예전 파일에 남은 키는 지웁니다.
import contextlib
import io

with tempfile.TemporaryDirectory() as folder:
    server.CONFIG_PATH = Path(folder) / "config.json"
    with contextlib.redirect_stdout(io.StringIO()):
        server.setup()
        server.setup()
    example = json.loads(server.EXAMPLE_PATH.read_text(encoding="utf-8"))
    check("setup: 예시 그대로 복사", json.loads(server.CONFIG_PATH.read_text(encoding="utf-8")) == example)
    check("예시: 키 없음, IP 101~130", "api_key" not in example and (example["student_ip_start"], example["student_ip_end"]) == (101, 130))
    server.CONFIG_PATH.write_text(json.dumps({"api_key": "sk-old", "port": 9}), encoding="utf-8")
    loaded = server.load_config()
    check("예전 키 삭제", loaded["port"] == 9 and "api_key" not in loaded and "sk-old" not in server.CONFIG_PATH.read_text(encoding="utf-8"))

print("\n실패:", failed if failed else "없음")
sys.exit(1 if failed else 0)
