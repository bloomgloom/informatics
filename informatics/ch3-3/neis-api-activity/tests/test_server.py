"""가짜 나이스 API를 띄워 놓고 서버와 해설지 코드를 시험합니다. 인터넷이 필요 없습니다."""
import contextlib
import io
import json
import sys
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parent.parent
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT))
import requests
import server

# 해설지는 비공개 저장소에 있습니다. 없으면 해설지 시험을 건너뜁니다.
ANSWER_KEY = ROOT.parents[3] / "informatics-private/informatics/ch3-3/neis-api-activity/neis-api-activity.ipynb"
REAL_KEY = "real-neis-secret"
STUDENT_KEY = "lunch-tiger-piano"
calls = []
mu = threading.Lock()
failing = {"on": False}


def head(name, rows):
    return {name: [{"head": [{"list_total_count": len(rows)}, {"RESULT": {"CODE": "INFO-000", "MESSAGE": "정상"}}]},
                   {"row": rows}]}


def answer(service, query):
    if service == "mealServiceDietInfo":
        if query.get("MLSV_YMD") == "20261101":
            return {"RESULT": {"CODE": "INFO-200", "MESSAGE": "해당하는 데이터가 없습니다."}}
        return head(service, [{"SCHUL_NM": "시험고", "MLSV_YMD": query.get("MLSV_YMD"), "CAL_INFO": "674.4 Kcal",
                               "DDISH_NM": "쌀밥 <br/>미역국 (5.6.18)<br/>돈까스1.2.5.<br/>배추김치9."}])
    if service == "hisTimetable":
        return head(service, [{"PERIO": "1", "ITRT_CNTNT": "체육"}, {"PERIO": "2", "ITRT_CNTNT": "정보"}])
    if service == "SchoolSchedule":
        return head(service, [{"AA_YMD": "20261119", "EVENT_NM": "대학수학능력시험"}])
    return head(service, [{"SCHUL_NM": "시험고"}])


class Mock(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        url = urlsplit(self.path)
        query = {name: values[0] for name, values in parse_qs(url.query).items()}
        with mu:
            calls.append(query)
        if failing["on"]:
            self.send_response(500)
            self.end_headers()
            return
        body = json.dumps(answer(url.path.split("/")[-1], query), ensure_ascii=False).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def start(handler):
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd.server_address[1]


def reset():
    calls.clear()
    server.cache.clear()
    server.recent_requests.clear()
    failing["on"] = False


def solution_cells():
    """인터넷이 필요한 Open-Meteo 예시를 뺀 해설지 코드입니다."""
    nb = json.loads(ANSWER_KEY.read_text(encoding="utf-8"))
    for cell in nb["cells"]:
        source = "".join(cell["source"])
        if cell["cell_type"] == "code" and "open-meteo" not in source:
            yield source


def main():
    server.NEIS_URL = f"http://127.0.0.1:{start(Mock)}/hub"
    server.config = {"neis_key": REAL_KEY, "atpt_code": "B10", "school_code": "1234567", "school_name": "시험고",
                     "port": 0, "limit_per_minute": 120, "max_concurrent": 2, "cache_seconds": 600,
                     "student_key": STUDENT_KEY}
    server.api_slots = threading.BoundedSemaphore(2)
    base = f"http://127.0.0.1:{start(server.Handler)}"
    meal = base + "/hub/mealServiceDietInfo"
    quiet = io.StringIO()

    def get(url, **params):
        with contextlib.redirect_stdout(quiet):
            return requests.get(url, params=params)

    assert get(base).json() == {"status": "ok", "school": "시험고"}

    # 수업용 키가 맞아야 하고, 나이스에는 실제 키와 학교 코드가 갑니다.
    reset()
    response = get(meal, KEY="wrong", MLSV_YMD="20261102")
    assert response.status_code == 401 and response.json()["RESULT"]["CODE"] == "ERROR-290" and not calls
    assert get(meal, MLSV_YMD="20261102").status_code == 401 and not calls
    response = get(meal, KEY=STUDENT_KEY, Type="xml", MLSV_YMD="20261102")
    assert response.status_code == 200 and "mealServiceDietInfo" in response.json()
    assert calls[0]["KEY"] == REAL_KEY and calls[0]["Type"] == "json"
    assert calls[0]["ATPT_OFCDC_SC_CODE"] == "B10" and calls[0]["SD_SCHUL_CODE"] == "1234567"
    assert REAL_KEY not in response.text

    # 다른 학교를 직접 지정할 수 있고, 학교 검색에는 학교 코드를 채우지 않습니다.
    reset()
    get(meal, KEY=STUDENT_KEY, SD_SCHUL_CODE="7654321")
    assert calls[0]["SD_SCHUL_CODE"] == "7654321"
    get(base + "/hub/schoolInfo", KEY=STUDENT_KEY, SCHUL_NM="시험")
    assert "SD_SCHUL_CODE" not in calls[1]

    # 없는 서비스와 주소는 나이스로 보내지 않습니다.
    reset()
    assert get(base + "/hub/secret", KEY=STUDENT_KEY).status_code == 404
    assert get(base + "/hub/../etc", KEY=STUDENT_KEY).status_code == 404
    assert get(base + "/other", KEY=STUDENT_KEY).status_code == 404 and not calls

    # 같은 요청은 동시에 와도 나이스로 한 번만 갑니다. '데이터 없음'도 저장합니다.
    reset()
    with ThreadPoolExecutor(20) as pool:
        results = list(pool.map(lambda _: requests.get(meal, params={"KEY": STUDENT_KEY, "MLSV_YMD": "20261102"}), range(20)))
    assert all(r.status_code == 200 for r in results) and len(calls) <= 2
    reset()
    for _ in range(3):
        assert get(meal, KEY=STUDENT_KEY, MLSV_YMD="20261101").json()["RESULT"]["CODE"] == "INFO-200"
    assert len(calls) == 1

    # 나이스 오류는 저장하지 않고, 복구되면 다시 호출합니다.
    reset()
    failing["on"] = True
    response = get(meal, KEY=STUDENT_KEY, MLSV_YMD="20261102")
    assert response.status_code == 502 and response.json()["RESULT"]["CODE"] == "ERROR-500"
    failing["on"] = False
    assert get(meal, KEY=STUDENT_KEY, MLSV_YMD="20261102").status_code == 200

    # 분당 제한
    reset()
    server.config["limit_per_minute"] = 3
    statuses = [get(meal, KEY=STUDENT_KEY, MLSV_YMD="20261102").status_code for _ in range(4)]
    assert statuses == [200, 200, 200, 429]
    server.config["limit_per_minute"] = 120

    if ANSWER_KEY.exists():
        # 해설지 코드를 위에서부터 끝까지 실행합니다.
        reset()
        namespace = {}
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            for source in solution_cells():
                source = source.replace("http://선생님IP:8000", base).replace("수업용키", STUDENT_KEY)
                exec(source, namespace)
        assert namespace["clean_menu"]("쌀밥 <br/>미역국 (5.6.18)<br/>돈까스1.2.5.<br/>배추김치9.") == ["쌀밥", "미역국", "돈까스", "배추김치"]
        assert namespace["has_food"](["치즈돈까스"], "돈까스") is True and namespace["has_food"](["쌀밥"], "치킨") is False
        assert namespace["get_calories"]("674.4 Kcal") == 674.4
        assert namespace["next_day"]("20261231") == "20270101"
        assert namespace["get_meal"]("20261101") is None
        assert namespace["next_food"]("돈까스", "20261101") == "20261102"
        assert namespace["next_food"]("치킨", "20261102", days=3) is None
        assert "20261101 급식이 없습니다." in output.getvalue()

    # 활동지에는 따라 칠 코드가 보이지 않습니다.
    student = json.loads((ROOT / "neis-api-activity.ipynb").read_text(encoding="utf-8"))
    code = ["".join(c["source"]) for c in student["cells"] if c["cell_type"] == "code"]
    assert "pip" in code[0] and all(not c.strip() or c.startswith("# 여기에") for c in code[1:])
    markdown = "\n".join("".join(c["source"]) for c in student["cells"] if c["cell_type"] == "markdown")
    if ANSWER_KEY.exists():
        assert not any(source in markdown for source in solution_cells())
    assert "def get_meal" not in markdown and "[교사]" not in markdown

    # setup은 config.json만 만들고, 예전 파일에 남은 키와 학교는 지웁니다.
    with tempfile.TemporaryDirectory() as folder:
        server.CONFIG_PATH = Path(folder) / "config.json"
        with contextlib.redirect_stdout(quiet):
            server.setup()
            server.setup()
        example = json.loads(server.EXAMPLE_PATH.read_text(encoding="utf-8"))
        assert json.loads(server.CONFIG_PATH.read_text(encoding="utf-8")) == example
        assert not set(server.SECRET_KEYS) & set(example)
        server.CONFIG_PATH.write_text(json.dumps({"neis_key": "secret", "school_code": "1", "port": 9}), encoding="utf-8")
        loaded = server.load_config()
        assert loaded["port"] == 9 and "neis_key" not in loaded and "secret" not in server.CONFIG_PATH.read_text(encoding="utf-8")

    print("모든 시험 통과")


if __name__ == "__main__":
    main()
