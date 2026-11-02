"""수업용 Claude API 중계 서버. 파이썬 표준 라이브러리만 사용합니다.

Anthropic API와 같은 형식으로 요청을 받으므로 학생은 anthropic 라이브러리를 그대로 쓰고,
환경 변수 ANTHROPIC_BASE_URL과 ANTHROPIC_API_KEY만 이 서버의 주소와 수업용 키로 설정합니다.

학생 코드 -> (이 서버: 수업용 키 확인, 모델 제한, 사용량 제한, 실제 키로 교체) -> Claude API

설정: python3 server.py setup  (config.example.json으로 config.json을 만듦)
실행: python3 server.py start  (API 키를 묻고, 수업용 키를 받아 서버를 엶. API 키는 파일에 저장하지 않음)
"""
import getpass
import hmac
import json
import random
import re
import secrets
import shutil
import socket
import sys
import threading
import time
import urllib.error
import urllib.request
from collections import defaultdict, deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

CONFIG_PATH = Path(__file__).parent / "config.json"
EXAMPLE_PATH = Path(__file__).parent / "config.example.json"
API_URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"
API_TIMEOUT = 60
TOTAL_WAIT = 100  # 줄 서기와 재시도를 합쳐 요청 하나가 기다리는 최대 시간(초)
MIN_CALL_TIME = 15  # 남은 시간이 이보다 짧으면 끝나지 못할 호출(비용 발생)을 보내지 않습니다.
MAX_ATTEMPTS = 5
RETRY_STATUS = (429, 529)  # 사용 한도 초과, API 과부하
MAX_BODY_BYTES = 1_000_000
SECRET_KEYS = ("api_key",)  # 파일에 저장하지 않는 값
ALLOWED_FIELDS = {"model", "max_tokens", "messages", "system",
                  "temperature", "top_p", "stop_sequences"}

config = {}
api_slots = None  # 동시에 API를 호출할 수 있는 자리 수. main에서 정합니다.
lock = threading.Lock()
recent_requests = defaultdict(deque)  # 학생 IP -> 최근 1분 요청 시각
# 아래 두 횟수는 서버를 켤 때마다 0부터 다시 셉니다. 즉 수업당 제한입니다.
student_counts = defaultdict(int)  # 학생 IP -> 이번 수업 요청 수
class_count = 0


class BadRequest(Exception):
    pass


class Busy(Exception):
    """기다려도 API를 호출하지 못한 경우입니다."""


def ask_api_key():
    """실제 API 키를 입력받습니다."""
    while True:
        try:
            key = getpass.getpass("Claude API 키 (입력 내용은 보이지 않습니다): ").strip()
        except EOFError:
            sys.exit("\n입력을 받지 못해 서버를 켜지 않았습니다.")
        if key.startswith("sk-"):
            return key
        print("올바른 키가 아닙니다. 키는 sk-로 시작합니다.")


def load_config():
    """기본값 위에 config.json을 얹습니다. 예전 파일에 남은 키는 지웁니다."""
    if not CONFIG_PATH.exists():
        sys.exit("설정이 없습니다. setup을 먼저 실행해 주세요.")
    saved = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if any(name in saved for name in SECRET_KEYS):
        saved = {name: value for name, value in saved.items() if name not in SECRET_KEYS}
        CONFIG_PATH.write_text(json.dumps(saved, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {**json.loads(EXAMPLE_PATH.read_text(encoding="utf-8")), **saved}


def is_text_blocks(value):
    return (isinstance(value, list) and value
            and all(isinstance(block, dict) and block.get("type") == "text"
                    and isinstance(block.get("text"), str) for block in value))


def text_length(value):
    return len(value) if isinstance(value, str) else sum(len(block["text"]) for block in value)


def parse_request(body):
    """학생 요청을 확인해 API로 보낼 내용을 돌려줍니다."""
    if not isinstance(body, dict):
        raise BadRequest("요청은 JSON 객체여야 합니다.")

    unsupported = sorted(set(body) - ALLOWED_FIELDS)
    if unsupported:
        raise BadRequest(f"수업에서 지원하지 않는 항목입니다: {', '.join(unsupported)}")

    if "model" not in body:
        raise BadRequest("model 항목이 필요합니다.")
    if body["model"] != config["model"]:
        raise BadRequest(f"수업에서는 {config['model']} 모델만 지원합니다. (요청한 모델: {body['model']})")

    max_tokens = body.get("max_tokens")
    if not isinstance(max_tokens, int) or isinstance(max_tokens, bool) or max_tokens < 1:
        raise BadRequest("max_tokens 항목에 1 이상의 정수가 필요합니다.")

    messages = body.get("messages")
    if not isinstance(messages, list) or not messages:
        raise BadRequest("messages 항목에 비어 있지 않은 목록이 필요합니다.")
    for item in messages:
        if not isinstance(item, dict) or item.get("role") not in ("user", "assistant"):
            raise BadRequest("메시지의 role은 user 또는 assistant여야 합니다.")
        content = item.get("content")
        if not (isinstance(content, str) and content.strip()) and not is_text_blocks(content):
            raise BadRequest("메시지의 content에 글자가 필요합니다. 이미지 등은 지원하지 않습니다.")

    system = body.get("system")
    if system is not None and not isinstance(system, str) and not is_text_blocks(system):
        raise BadRequest("system은 글자여야 합니다.")

    total = sum(text_length(item["content"]) for item in messages) + text_length(system or "")
    if total > config["max_input_chars"]:
        raise BadRequest(f"입력이 너무 깁니다. ({total}자, 최대 {config['max_input_chars']}자)")

    # 출력 길이는 설정값을 넘지 않게 줄입니다.
    return {**body, "max_tokens": min(max_tokens, config["max_tokens"])}


def check_limit(ip):
    """제한에 걸리면 안내 문구를, 아니면 None을 돌려줍니다."""
    global class_count
    now = time.monotonic()
    with lock:
        if class_count >= config["limit_per_class"]:
            return "이번 수업의 전체 사용량을 모두 썼습니다. 선생님께 알려 주세요."
        if student_counts[ip] >= config["limit_per_student"]:
            return "이번 수업에서 쓸 수 있는 횟수를 다 썼습니다. 선생님께 알려 주세요."

        times = recent_requests[ip]
        while times and now - times[0] > 60:
            times.popleft()
        if len(times) >= config["limit_per_minute"]:
            return "요청이 너무 많습니다. 1분 뒤에 다시 해 보세요."

        times.append(now)
        student_counts[ip] += 1
        class_count += 1
    return None


def retry_delay(error, attempt):
    """API가 알려 준 시간을 따르고, 없으면 점점 길게 기다립니다."""
    try:
        return float(error.headers.get("retry-after"))
    except (TypeError, ValueError):
        return 2 ** (attempt + 1) + random.uniform(0, 1)


def call_claude(payload):
    # 생각 기능을 끌 수 있는 모델은 끕니다. 토큰을 아끼고 답이 잘리는 일을 줄입니다. (Sonnet 5.5 등은 400 오류)
    if "haiku" in payload["model"]:
        payload = {**payload, "thinking": {"type": "disabled"}}
    request = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "content-type": "application/json",
            "x-api-key": config["api_key"],
            "anthropic-version": API_VERSION,
        },
    )
    deadline = time.monotonic() + TOTAL_WAIT
    if not api_slots.acquire(timeout=TOTAL_WAIT):
        raise Busy("순서를 기다리다 시간 초과")
    # 재시도를 기다리는 동안에도 자리를 잡고 있어, 한도에 걸리면 전체 호출이 함께 느려집니다.
    try:
        for attempt in range(MAX_ATTEMPTS):
            remaining = deadline - time.monotonic()
            if remaining < MIN_CALL_TIME:
                raise Busy("남은 시간 부족")
            try:
                with urllib.request.urlopen(request, timeout=min(API_TIMEOUT, remaining)) as response:
                    return json.load(response)
            except urllib.error.HTTPError as error:
                if error.code not in RETRY_STATUS:
                    raise
                delay = retry_delay(error, attempt)
                error.close()
                if attempt == MAX_ATTEMPTS - 1 or time.monotonic() + delay >= deadline:
                    raise Busy(f"API {error.code}, 재시도 {attempt}회 후 포기")
                time.sleep(delay)
    finally:
        api_slots.release()


def make_student_key():
    """Claude에게 짧은 영어 문장을 받아 수업용 키로 만듭니다. 예: i-am-a-teacher"""
    prompt = ("학생들에게 말로 불러 줄 수업용 암호를 만들어 줘. 쉬운 영어 단어 3~5개로 된 짧은 문장 하나를 "
              "소문자로 쓰고, 띄어쓰기 대신 -를 써. 예: i-am-a-teacher "
              f"이번에는 {secrets.choice('abcdefghilmnoprstw')}로 시작하는 단어를 넣어 줘. 문장만 답해.")
    for _ in range(3):
        result = call_claude({"model": config["model"], "max_tokens": 30,
                              "messages": [{"role": "user", "content": prompt}]})
        text = "".join(block.get("text", "") for block in result.get("content", []))
        key = re.sub(r"[^a-z]+", "-", text.lower()).strip("-")
        if re.fullmatch(r"[a-z]+(-[a-z]+){2,5}", key):
            return key
    raise ValueError("수업용 키로 쓸 문장을 받지 못했습니다.")


def api_error_message(error):
    """setup과 start에서 API 호출이 실패한 이유를 교사에게 설명합니다."""
    if isinstance(error, Busy):
        return "Claude API가 바쁩니다. 잠시 뒤에 다시 실행해 주세요."
    if isinstance(error, urllib.error.HTTPError):
        if error.code == 401:
            return "API 키가 맞지 않습니다. 키를 확인하고 다시 실행해 주세요."
        detail = error.read().decode("utf-8", "replace")[:300]
        return f"Claude API 오류입니다({error.code}). 모델 이름과 계정 크레딧을 확인해 주세요.\n{detail}"
    return f"Claude API에 연결하지 못했습니다. 인터넷 연결을 확인해 주세요.\n{error}"


def setup():
    """config.example.json으로 config.json을 만듭니다. 이미 있으면 그대로 둡니다."""
    if CONFIG_PATH.exists():
        print(f"이미 있습니다: {CONFIG_PATH}")
    else:
        shutil.copyfile(EXAMPLE_PATH, CONFIG_PATH)
        print(f"만들었습니다: {CONFIG_PATH}")
    print("값을 바꾸려면 이 파일을 직접 고칩니다. 수업 때는 start를 실행하세요.")


class Handler(BaseHTTPRequestHandler):
    def send_json(self, status, data):
        encoded = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def send_error_json(self, status, error_type, message):
        # Anthropic API의 오류 형식과 같습니다.
        self.log_chat(f"거절({status}): {message}")
        self.send_json(status, {"type": "error", "error": {"type": error_type, "message": message}})

    def log_message(self, format, *args):
        pass  # 기본 접속 기록 대신 log_chat만 씁니다.

    def log_chat(self, result):
        # 학생이 쓴 내용은 기록하지 않습니다.
        print(f"{time.strftime('%H:%M:%S')} {self.client_address[0]} {result}", flush=True)

    def check_key(self):
        # anthropic 라이브러리 버전에 따라 키를 보내는 헤더가 다릅니다.
        key = self.headers.get("x-api-key") or self.headers.get("Authorization", "").removeprefix("Bearer ")
        if hmac.compare_digest(key.encode(), config["student_key"].encode()):
            return True
        self.send_error_json(401, "authentication_error", "API 키가 맞지 않습니다. 선생님이 알려 준 키를 넣어 주세요.")
        return False

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/":
            self.send_json(200, {"status": "ok"})
        elif path == "/v1/models":
            if self.check_key():
                model = {"type": "model", "id": config["model"], "display_name": config["model"],
                         "created_at": "2026-01-01T00:00:00Z"}
                self.send_json(200, {"data": [model], "has_more": False,
                                     "first_id": model["id"], "last_id": model["id"]})
        else:
            self.send_error_json(404, "not_found_error", "없는 주소입니다.")

    def do_POST(self):
        self.close_connection = True  # 읽지 않은 본문이 남아 있을 수 있어 요청마다 연결을 닫습니다.
        if self.path.split("?")[0] != "/v1/messages":
            self.send_error_json(404, "not_found_error", "없는 주소입니다.")
            return
        if not self.check_key():
            return

        try:
            length = int(self.headers.get("Content-Length", 0))
            if not 0 < length <= MAX_BODY_BYTES:
                raise BadRequest("요청 내용이 없거나 너무 큽니다.")
            payload = parse_request(json.loads(self.rfile.read(length)))
        except BadRequest as error:
            self.send_error_json(400, "invalid_request_error", str(error))
            return
        except ValueError:
            self.send_error_json(400, "invalid_request_error", "요청을 JSON으로 읽을 수 없습니다.")
            return

        limit_message = check_limit(self.client_address[0])
        if limit_message:
            self.send_error_json(429, "rate_limit_error", limit_message)
            return

        try:
            result = call_claude(payload)
        except Busy as error:
            self.log_chat(f"혼잡: {error}")
            self.send_error_json(529, "overloaded_error", "지금 사용자가 많아요. 잠시 뒤에 다시 해 보세요.")
            return
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", "replace")
            if error.code == 400:  # 학생 요청 문제이므로 API의 안내를 그대로 전달합니다.
                self.log_chat(f"API 400: {detail[:300]}")
                try:
                    self.send_json(400, json.loads(detail))
                except ValueError:
                    self.send_error_json(400, "invalid_request_error", "요청 내용을 확인해 주세요.")
                return
            # 그 밖의 API 오류 본문은 학생에게 넘기지 않고 교사 화면에만 표시합니다.
            self.log_chat(f"API 오류 {error.code}: {detail[:300]}")
            self.send_error_json(502, "api_error", f"AI 서버 오류입니다({error.code}). 선생님께 알려 주세요.")
            return
        except (OSError, ValueError) as error:  # 연결 실패, 시간 초과, 잘못된 응답
            self.log_chat(f"연결 오류: {error}")
            self.send_error_json(502, "api_error", "AI 서버에 연결하지 못했습니다. 선생님께 알려 주세요.")
            return

        usage = result.get("usage", {})
        self.log_chat(f"성공: 입력 {usage.get('input_tokens', 0)} / 출력 {usage.get('output_tokens', 0)} 토큰, "
                      f"이번 수업 {class_count}회")
        # 생각 블록을 빼서 어느 모델에서든 content[0].text가 답이 되게 합니다.
        result["content"] = [block for block in result.get("content", [])
                             if block.get("type") not in ("thinking", "redacted_thinking")]
        self.send_json(200, result)


def local_ip():
    """학생들이 접속할 이 컴퓨터의 IP를 찾습니다. 실제로 데이터를 보내지는 않습니다."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        try:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
        except OSError:
            return "127.0.0.1"


def start():
    """수업용 키를 받아 서버를 열고 접속 정보를 안내합니다."""
    global config, api_slots
    config = load_config()
    config["api_key"] = ask_api_key()
    api_slots = threading.BoundedSemaphore(config["max_concurrent"])
    server = ThreadingHTTPServer(("0.0.0.0", config["port"]), Handler)

    print("Claude에게 수업용 키를 받는 중입니다...", flush=True)
    try:
        config["student_key"] = make_student_key()
    except (Busy, OSError, ValueError) as error:
        sys.exit(api_error_message(error))

    print(f"\n제한: 이번 수업 학생당 {config['limit_per_student']}회, 전체 {config['limit_per_class']}회, "
          f"학생당 분당 {config['limit_per_minute']}회, 동시 호출 {config['max_concurrent']}개, 최대 출력 {config['max_tokens']} 토큰")
    print()
    print("학생들에게 알려 줄 내용")
    print(f"  접속 주소 (ANTHROPIC_BASE_URL): http://{local_ip()}:{config['port']}")
    print(f"  수업용 키 (ANTHROPIC_API_KEY):  {config['student_key']}")
    print(f"  모델:                           {config['model']}")
    print()
    print("끄려면 Ctrl+C", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n서버를 끕니다.")


def main():
    commands = {"setup": setup, "start": start}
    if len(sys.argv) != 2 or sys.argv[1] not in commands:
        sys.exit("사용법: python3 server.py setup 또는 python3 server.py start")
    commands[sys.argv[1]]()


if __name__ == "__main__":
    main()
