"""수업용 나이스 교육정보 API 중계 서버. 파이썬 표준 라이브러리만 사용합니다.

나이스 API와 같은 주소 형식으로 요청을 받으므로 학생은 실제 API를 쓰는 것과 같은 코드를 씁니다.

학생 코드 -> (이 서버: 수업용 키 확인, 학교 코드 채우기, 사용량 제한, 캐시, 실제 키로 교체) -> 나이스 API

설정: python3 server.py setup  (config.example.json으로 config.json을 만듦)
실행: python3 server.py start  (나이스 키와 학교를 묻고, 수업용 키를 만들어 서버를 엶. 키와 학교는 파일에 저장하지 않음)
"""
import getpass
import hmac
import json
import secrets
import shutil
import socket
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict, deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

CONFIG_PATH = Path(__file__).parent / "config.json"
EXAMPLE_PATH = Path(__file__).parent / "config.example.json"
NEIS_URL = "https://open.neis.go.kr/hub"
NEIS_TIMEOUT = 15
TOTAL_WAIT = 30  # 나이스 호출 순서를 기다리는 최대 시간(초)
MAX_CACHE = 5000
MAX_VALUE_CHARS = 100
SECRET_KEYS = ("neis_key", "atpt_code", "school_code", "school_name")  # 파일에 저장하지 않는 값
# 학교 코드를 자동으로 채우는 서비스: True, 채우지 않는 서비스(학교 검색): False
SERVICES = {"mealServiceDietInfo": True, "hisTimetable": True, "SchoolSchedule": True, "schoolInfo": False}
# 수업용 키를 만드는 단어. 말로 불러 주기 쉬운 것만 넣습니다.
KEY_WORDS = ("apple", "bread", "cloud", "green", "happy", "lemon", "lunch", "music", "ocean", "piano",
             "pizza", "river", "robot", "smile", "sunny", "tiger", "tulip", "water", "whale", "zebra")

config = {}
api_slots = None  # 동시에 나이스를 호출할 수 있는 자리 수. main에서 정합니다.
lock = threading.Lock()
recent_requests = defaultdict(deque)  # 학생 IP -> 최근 1분 요청 시각
cache = {}  # (서비스, 요청 항목) -> (저장 시각, 응답)
request_count = 0


class Busy(Exception):
    """기다려도 나이스를 호출하지 못한 경우입니다."""


def load_config():
    """기본값 위에 config.json을 얹습니다. 예전 파일에 남은 키는 지웁니다."""
    if not CONFIG_PATH.exists():
        sys.exit("설정이 없습니다. setup을 먼저 실행해 주세요.")
    saved = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    if any(name in saved for name in SECRET_KEYS):
        saved = {name: value for name, value in saved.items() if name not in SECRET_KEYS}
        CONFIG_PATH.write_text(json.dumps(saved, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {**json.loads(EXAMPLE_PATH.read_text(encoding="utf-8")), **saved}


def fetch_neis(service, params, neis_key):
    """나이스 API를 호출해 JSON을 돌려줍니다. 나이스는 오류도 200과 RESULT로 알려 줍니다."""
    query = {**params, "Type": "json"}
    if neis_key:
        query["KEY"] = neis_key
    url = f"{NEIS_URL}/{service}?{urllib.parse.urlencode(query)}"
    request = urllib.request.Request(url, headers={"User-Agent": "neis-api-classroom"})
    with urllib.request.urlopen(request, timeout=NEIS_TIMEOUT) as response:
        return json.load(response)


def result_code(data):
    """응답의 결과 코드를 찾습니다. 데이터가 있으면 head 안에, 없으면 맨 위에 있습니다."""
    if "RESULT" in data:
        return data["RESULT"].get("CODE", "")
    for value in data.values():
        for item in value[0].get("head", []) if isinstance(value, list) and value else []:
            if "RESULT" in item:
                return item["RESULT"].get("CODE", "")
    return ""


def cached_fetch(service, params):
    """같은 요청은 한 번만 나이스로 보냅니다. 학생들이 같은 날짜를 동시에 물어도 호출이 늘지 않습니다."""
    key = (service, tuple(sorted(params.items())))
    now = time.monotonic()
    with lock:
        saved = cache.get(key)
    if saved and now - saved[0] < config["cache_seconds"]:
        return saved[1], True

    if not api_slots.acquire(timeout=TOTAL_WAIT):
        raise Busy("순서를 기다리다 시간 초과")
    try:
        with lock:  # 기다리는 동안 다른 학생의 요청이 먼저 끝났을 수 있습니다.
            saved = cache.get(key)
        if saved and time.monotonic() - saved[0] < config["cache_seconds"]:
            return saved[1], True
        data = fetch_neis(service, params, config["neis_key"])
    finally:
        api_slots.release()

    if result_code(data) in ("INFO-000", "INFO-200"):  # 오류 응답은 저장하지 않습니다.
        with lock:
            if len(cache) >= MAX_CACHE:
                cache.clear()
            cache[key] = (time.monotonic(), data)
    return data, False


def check_limit(ip):
    """제한에 걸리면 안내 문구를, 아니면 None을 돌려줍니다."""
    global request_count
    now = time.monotonic()
    with lock:
        times = recent_requests[ip]
        while times and now - times[0] > 60:
            times.popleft()
        if len(times) >= config["limit_per_minute"]:
            return "요청이 너무 많습니다. 1분 뒤에 다시 해 보세요."
        times.append(now)
        request_count += 1
    return None


def build_params(service, query):
    """학생 요청에서 나이스로 보낼 항목을 만듭니다. 키와 형식은 서버가 정합니다."""
    params = {name: values[0][:MAX_VALUE_CHARS] for name, values in query.items()
              if name not in ("KEY", "Type")}
    if SERVICES[service]:
        params.setdefault("ATPT_OFCDC_SC_CODE", config["atpt_code"])
        params.setdefault("SD_SCHUL_CODE", config["school_code"])
    return params


def error_body(code, message):
    return {"RESULT": {"CODE": code, "MESSAGE": message}}  # 나이스 API의 오류 형식과 같습니다.


class Handler(BaseHTTPRequestHandler):
    def send_json(self, status, data):
        encoded = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format, *args):
        pass  # 기본 접속 기록 대신 log_request_result만 씁니다.

    def log_request_result(self, result):
        print(f"{time.strftime('%H:%M:%S')} {self.client_address[0]} {result}", flush=True)

    def reject(self, status, code, message):
        self.log_request_result(f"거절({status}): {message}")
        self.send_json(status, error_body(code, message))

    def do_GET(self):
        url = urllib.parse.urlsplit(self.path)
        if url.path == "/":
            self.send_json(200, {"status": "ok", "school": config["school_name"]})
            return

        service = url.path.removeprefix("/hub/")
        if not url.path.startswith("/hub/") or service not in SERVICES:
            self.reject(404, "ERROR-404", f"없는 주소입니다. 쓸 수 있는 서비스: {', '.join(SERVICES)}")
            return

        query = urllib.parse.parse_qs(url.query)
        key = query.get("KEY", [""])[0]
        if not hmac.compare_digest(key.encode(), config["student_key"].encode()):
            self.reject(401, "ERROR-290", "수업용 키가 맞지 않습니다. 선생님이 알려 준 키를 KEY에 넣어 주세요.")
            return

        limit_message = check_limit(self.client_address[0])
        if limit_message:
            self.reject(429, "ERROR-337", limit_message)
            return

        try:
            data, from_cache = cached_fetch(service, build_params(service, query))
        except Busy as error:
            self.log_request_result(f"혼잡: {error}")
            self.send_json(503, error_body("ERROR-500", "지금 사용자가 많아요. 잠시 뒤에 다시 해 보세요."))
            return
        except (OSError, ValueError) as error:  # 연결 실패, 시간 초과, 잘못된 응답
            self.log_request_result(f"연결 오류: {error}")
            self.send_json(502, error_body("ERROR-500", "나이스 서버에 연결하지 못했습니다. 선생님께 알려 주세요."))
            return

        code = result_code(data)
        if code not in ("INFO-000", "INFO-200"):  # 실제 키 문제 등은 교사가 볼 수 있게 남깁니다.
            self.log_request_result(f"나이스 오류 {code}: {service}")
        else:
            self.log_request_result(f"{service} {code}{' 캐시' if from_cache else ''}, 이번 수업 {request_count}회")
        self.send_json(200, data)


def ask(label):
    try:
        return input(label).strip()
    except EOFError:
        sys.exit("\n입력을 받지 못해 서버를 켜지 않았습니다.")


def ask_neis_key():
    """나이스 인증키를 입력받습니다. 키 없이도 쓸 수 있지만 응답이 5건으로 잘립니다."""
    while True:
        try:
            key = getpass.getpass("나이스 인증키 (Enter: 키 없이 사용, 입력 내용은 보이지 않습니다): ").strip()
        except EOFError:
            sys.exit("\n입력을 받지 못해 서버를 켜지 않았습니다.")
        if not key:
            print("키 없이 쓰면 응답이 5건으로 잘립니다. 시간표는 5교시까지만 나옵니다.")
            return ""
        try:
            data = fetch_neis("schoolInfo", {"pSize": "1", "SCHUL_NM": "고등학교"}, key)
        except (OSError, ValueError) as error:
            sys.exit(f"나이스에 연결하지 못했습니다. 인터넷 연결을 확인해 주세요.\n{error}")
        if result_code(data) == "INFO-000":
            return key
        print("인증키가 맞지 않습니다:", data.get("RESULT", {}).get("MESSAGE", ""))


def ask_school(loaded, neis_key):
    """학교 이름으로 검색해 학교를 고릅니다."""
    current = loaded["school_name"]
    while True:
        name = ask(f"학교 이름{f' (Enter: {current})' if current else ''}: ")
        if not name and current:
            return
        if not name:
            continue
        try:
            data = fetch_neis("schoolInfo", {"SCHUL_NM": name, "pSize": "20"}, neis_key)
        except (OSError, ValueError) as error:
            sys.exit(f"나이스에 연결하지 못했습니다. 인터넷 연결을 확인해 주세요.\n{error}")
        if "schoolInfo" not in data:
            print("찾지 못했습니다. 이름의 일부만 넣어 다시 해 보세요.")
            continue
        schools = data["schoolInfo"][1]["row"]
        for number, school in enumerate(schools, 1):
            print(f"  {number}. {school['SCHUL_NM']} ({school['ATPT_OFCDC_SC_NM']})")
        answer = ask("번호를 고르세요 (Enter: 다시 검색): ")
        if answer.isdigit() and 1 <= int(answer) <= len(schools):
            school = schools[int(answer) - 1]
            loaded.update(atpt_code=school["ATPT_OFCDC_SC_CODE"], school_code=school["SD_SCHUL_CODE"],
                          school_name=school["SCHUL_NM"])
            return


def setup():
    """config.example.json으로 config.json을 만듭니다. 이미 있으면 그대로 둡니다."""
    if CONFIG_PATH.exists():
        print(f"이미 있습니다: {CONFIG_PATH}")
    else:
        shutil.copyfile(EXAMPLE_PATH, CONFIG_PATH)
        print(f"만들었습니다: {CONFIG_PATH}")
    print("값을 바꾸려면 이 파일을 직접 고칩니다. 수업 때는 start를 실행하세요.")


def make_student_key():
    """말로 불러 주기 쉬운 수업용 키를 만듭니다. 예: lunch-tiger-piano"""
    return "-".join(secrets.choice(KEY_WORDS) for _ in range(3))


def local_ip():
    """학생들이 접속할 이 컴퓨터의 IP를 찾습니다. 실제로 데이터를 보내지는 않습니다."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        try:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
        except OSError:
            return "127.0.0.1"


def start():
    """수업용 키를 만들어 서버를 열고 접속 정보를 안내합니다."""
    global config, api_slots
    config = load_config()
    config["neis_key"] = ask_neis_key()
    config["school_name"] = ""
    ask_school(config, config["neis_key"])
    config["student_key"] = make_student_key()
    api_slots = threading.BoundedSemaphore(config["max_concurrent"])
    server = ThreadingHTTPServer(("0.0.0.0", config["port"]), Handler)

    print(f"학교: {config['school_name']}")
    print(f"제한: 학생당 분당 {config['limit_per_minute']}회, 동시 호출 {config['max_concurrent']}개, "
          f"같은 요청 재사용 {config['cache_seconds']}초")
    if not config["neis_key"]:
        print("주의: 나이스 인증키가 없어 응답이 5건으로 잘립니다. 시간표는 5교시까지만 나옵니다.")
    print()
    print("학생들에게 알려 줄 내용")
    print(f"  접속 주소 (BASE_URL): http://{local_ip()}:{config['port']}")
    print(f"  수업용 키 (KEY):      {config['student_key']}")
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
