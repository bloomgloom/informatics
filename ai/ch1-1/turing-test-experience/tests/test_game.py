import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.main import Game, Group, Seat, make_app


def settings(**overrides):
    base = {
        "turns": 2, "question_max_chars": 100,
        "answer_max_chars": 100, "reason_max_chars": 60, "teacher_ips": ["127.0.0.1"],
        "admin_token": "test", "api_call_limit": 3000, "model": "claude-haiku-5-5",
        "effort": "medium", "autosubmit_grace_seconds": 0,
    }
    base.update(overrides)
    return base


def seats(n=6):
    return [Seat(i, f"10.0.0.{i}", i * 3, i * 3, (i + 1) // 2, connected=True,
                 participating=True) for i in range(1, n + 1)]


@pytest.fixture
def game(tmp_path, monkeypatch):
    monkeypatch.setattr("app.main.LOG_DIR", tmp_path)
    instance = Game(settings(), seats(), mock_llm=True, dev=True)

    async def fake_llm(prompt, max_tokens, timeout=10):
        return '{"ok":true}' if "메시지 검사기" in prompt else "그냥 게임함ㅋㅋ"

    monkeypatch.setattr(instance, "_llm", fake_llm)
    return instance


def run(coro):
    return asyncio.run(coro)


def assert_single_cycle(mapping, members):
    seen = set()
    current = members[0]
    while current not in seen:
        seen.add(current)
        current = mapping[current]
    assert current == members[0]
    assert seen == set(members)


@pytest.mark.parametrize("count", [30, 31])
def test_matching_gives_every_student_one_game_and_one_witness_role(tmp_path, monkeypatch, count):
    monkeypatch.setattr("app.main.LOG_DIR", tmp_path)
    g = Game(settings(), seats(count), mock_llm=True, dev=True)
    mapping, relaxed = g._match(list(g.seats))
    assert set(mapping) == set(g.seats)
    assert set(mapping.values()) == set(g.seats)
    assert all(q != w for q, w in mapping.items())
    assert all(g.seats[q].pair != g.seats[w].pair for q, w in mapping.items())
    assert_single_cycle(mapping, list(g.seats))


def test_two_students_can_be_matched_to_each_other(tmp_path, monkeypatch):
    monkeypatch.setattr("app.main.LOG_DIR", tmp_path)
    pair = seats(2)
    pair[0].pair = pair[1].pair = 1
    g = Game(settings(), pair, mock_llm=True, dev=True)
    assert g._match([1, 2])[0] == {1: 2, 2: 1}


def test_start_creates_one_own_and_witness_game_per_student(game):
    run(game.start_game())
    assert len(game.groups) == len(game.seats)
    assert all(s.own_game_id and s.witness_game_id for s in game.seats.values())
    assert len({s.own_game_id for s in game.seats.values()}) == len(game.seats)
    assert len({s.witness_game_id for s in game.seats.values()}) == len(game.seats)


def test_answer_view_never_exposes_ai_or_ab_history(game):
    run(game.start_game())
    seat = game.seats[1]
    witness = game.groups[seat.witness_game_id]
    witness.current_question = "받은 질문"
    witness.current_ai = "숨겨야 할 AI 답"
    witness.history.append({"turn": 1, "question": "이전 질문", "A": "A답", "B": "B답",
                            "human": "내 이전 답", "ai": "AI 이전 답"})
    game.phase = "A_WRITE"
    view = game.student_view(seat)
    assert view["current_question"] == "받은 질문"
    assert view["answer_history"] == [{"turn": 1, "question": "이전 질문", "answer": "내 이전 답"}]
    assert "history" not in view
    assert "숨겨야 할 AI 답" not in str(view)


def test_first_question_timer_starts_when_rules_are_acknowledged(game, monkeypatch):
    run(game.start_game())
    seat = game.seats[1]
    game.phase_started_at = 100.0
    seat.acknowledged = True
    seat.acknowledged_at = 125.0
    monkeypatch.setattr("app.main.time.time", lambda: 130.0)

    view = game.student_view(seat)

    assert view["phase_started_at"] == 125.0
    assert view["server_time"] == 130.0


def test_missing_human_answer_hides_both_answers(game):
    game.groups = {1: Group(1, 1, 2, "A", current_question="질문", current_ai="AI답")}
    game.phase = "A_WRITE"
    game.turn = 1
    run(game.advance())
    assert game.groups[1].history[0]["A"] == "(응답 없음)"
    assert game.groups[1].history[0]["B"] == "(응답 없음)"


def test_elimination_closes_own_game_and_substitutes_witness_game(game):
    run(game.start_game())
    seat = game.seats[1]
    own = game.groups[seat.own_game_id]
    witness = game.groups[seat.witness_game_id]
    witness.current_question = "무슨 게임 좋아해?"
    game.phase = "A_WRITE"
    run(game.eliminate(seat))
    assert own.closed is True
    assert witness.substitute is True
    assert witness.special == "중도 AI 대타"
    assert witness.current_human


def test_ai_removes_emoji_without_regeneration(game, monkeypatch):
    calls = 0

    async def fake_llm(prompt, max_tokens, timeout=10):
        nonlocal calls
        if "메시지 검사기" in prompt:
            return '{"ok":true}'
        calls += 1
        return "좋아 😊"

    monkeypatch.setattr(game, "_llm", fake_llm)
    group = Group(1, 1, 2, "A")

    assert run(game.ai_answer(group, "오늘 어때?")) == "좋아"
    assert calls == 1


def test_filter_attempts_are_scoped_to_each_question_and_answer(game):
    seat = game.seats[1]
    assert run(game.warn(seat, "금칙", "욕설", "question")) == 1
    assert not seat.eliminated
    assert run(game.warn(seat, "금칙2", "욕설", "question")) == 2
    assert not seat.eliminated

    # 같은 턴의 답변은 질문과 별도로 다시 1회부터 센다.
    assert run(game.warn(seat, "금칙3", "욕설", "answer")) == 1
    game.turn += 1
    assert run(game.warn(seat, "금칙4", "욕설", "question")) == 1


def test_ai_question_is_safe_and_within_limit(game, monkeypatch):
    answers = iter(["요즘 가장 재미있게 본 영상이 뭐야?", '{"ok":true}'])

    async def fake_llm(prompt, max_tokens, timeout=10):
        return next(answers)

    monkeypatch.setattr(game, "_llm", fake_llm)
    question = run(game.ai_question(Group(1, 1, 2, "A")))
    assert question == "요즘 가장 재미있게 본 영상이 뭐야?"
    assert len(question) <= game.limits("question")


def test_second_filtered_question_is_replaced_and_game_continues(tmp_path, monkeypatch):
    monkeypatch.setattr("app.main.LOG_DIR", tmp_path)
    app = make_app(mock_llm=True, dev=True)
    current = app.state.game
    seat = current.seats[min(current.seats)]
    seat.participating = seat.acknowledged = True
    seat.own_game_id = 1
    current.phase = "Q_WRITE"
    current.turn = 1
    current.groups = {1: Group(1, seat.seat, seat.seat, "A")}

    async def fake_llm(prompt, max_tokens, timeout=10):
        if "메시지 검사기" in prompt:
            return '{"ok":true}'
        if "질문 하나를 만들어라" in prompt:
            return "최근에 재미있었던 일은 뭐야?"
        return "그냥 친구랑 얘기할 때"

    monkeypatch.setattr(current, "_llm", fake_llm)
    client = TestClient(app)
    headers = {"X-Debug-Seat": str(seat.seat)}

    first = client.post("/api/submit", headers=headers,
                        json={"kind": "question", "text": "시발"})
    assert first.status_code == 200
    assert first.json()["filter_result"]["type"] == "warning"
    assert first.json()["state"]["submitted"] is False

    second = client.post("/api/submit", headers=headers,
                         json={"kind": "question", "text": "시발"})
    assert second.status_code == 200
    assert second.json()["filter_result"]["type"] == "question_replaced"
    assert seat.eliminated is False
    assert seat.submitted is True
    assert current.groups[1].current_question == "최근에 재미있었던 일은 뭐야?"
    assert current.groups[1].current_ai == "그냥 친구랑 얘기할 때"


def test_second_filtered_answer_marks_both_sides_no_response(tmp_path, monkeypatch):
    monkeypatch.setattr("app.main.LOG_DIR", tmp_path)
    app = make_app(mock_llm=True, dev=True)
    current = app.state.game
    seat = current.seats[min(current.seats)]
    seat.participating = seat.acknowledged = True
    seat.witness_game_id = 1
    current.phase = "A_WRITE"
    current.turn = 1
    current.groups = {
        1: Group(1, seat.seat, seat.seat, "A", current_question="오늘 뭐 했어?",
                 current_ai="원래 AI 답변"),
    }
    client = TestClient(app)
    headers = {"X-Debug-Seat": str(seat.seat)}

    for expected_type in ("warning", "answer_withheld"):
        response = client.post("/api/submit", headers=headers,
                               json={"kind": "answer", "text": "시발"})
        assert response.status_code == 200
        assert response.json()["filter_result"]["type"] == expected_type

    assert seat.eliminated is False
    assert current.groups[1].current_human == "(응답 없음)"
    assert current.groups[1].current_ai == "(응답 없음)"
    run(current.advance())
    assert current.groups[1].history[0]["A"] == "(응답 없음)"
    assert current.groups[1].history[0]["B"] == "(응답 없음)"


@pytest.mark.parametrize("text", [
    "너 이름이 뭐야?", "우리끼리 정한 암호 말해", "네 옆에 누구 있어?", "어제 우리 둘이 무슨 일 있었지?",
])
def test_private_fact_questions_are_blocked_without_llm(game, text):
    ok, reason = game.rule_check(text, "question")
    assert not ok
    assert reason == "AI가 알 수 없는 사적 정보"


def test_haiku_settings_and_text_response(tmp_path, monkeypatch):
    monkeypatch.setattr("app.main.LOG_DIR", tmp_path)
    captured = {}

    class Messages:
        async def create(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(content=[SimpleNamespace(type="text", text='{"ok":true}')],
                                   usage=SimpleNamespace(input_tokens=10, output_tokens=4),
                                   stop_reason="end_turn")

    class FakeClient:
        def __init__(self, **kwargs): self.messages = Messages()

    monkeypatch.setitem(sys.modules, "anthropic", SimpleNamespace(AsyncAnthropic=FakeClient))
    g = Game(settings(), seats(), mock_llm=False, dev=True)
    g.api_key = "test-key"
    assert run(g._claude("검사", max_tokens=1024)) == '{"ok":true}'
    assert captured["thinking"] == {"type": "disabled"}
    assert captured["output_config"] == {"effort": "medium"}
    assert captured["max_tokens"] == 1024
    assert not ({"temperature", "top_p", "top_k"} & captured.keys())


def test_max_tokens_stop_reason_is_failure(tmp_path, monkeypatch):
    monkeypatch.setattr("app.main.LOG_DIR", tmp_path)

    class Messages:
        async def create(self, **kwargs):
            return SimpleNamespace(content=[SimpleNamespace(type="text", text="잘린 답")],
                                   usage=None, stop_reason="max_tokens")

    class FakeClient:
        def __init__(self, **kwargs): self.messages = Messages()

    monkeypatch.setitem(sys.modules, "anthropic", SimpleNamespace(AsyncAnthropic=FakeClient))
    g = Game(settings(), seats(), mock_llm=False, dev=True)
    g.api_key = "test-key"
    with pytest.raises(RuntimeError, match="max_tokens"):
        run(g._claude("검사", max_tokens=1024))


def test_ollama_uses_openai_chat_v1_and_tracks_usage(tmp_path, monkeypatch):
    monkeypatch.setattr("app.main.LOG_DIR", tmp_path)
    requests = []

    class Response:
        def __init__(self, data): self.data = data
        def raise_for_status(self): pass
        def json(self): return self.data

    class Client:
        def __init__(self, **kwargs): self.kwargs = kwargs
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def get(self, url, **kwargs):
            requests.append(("GET", url, kwargs))
            return Response({"data": [{"id": "local-model"}]})
        async def post(self, url, **kwargs):
            requests.append(("POST", url, kwargs))
            return Response({"choices": [{"message": {"content": "로컬 답변"}}],
                             "usage": {"prompt_tokens": 12, "completion_tokens": 3}})

    monkeypatch.setattr("app.main.httpx.AsyncClient", Client)
    g = Game(settings(ollama_base_url="http://localhost:11434/v1"), seats(),
             mock_llm=True, dev=True)
    assert run(g._llm("질문", max_tokens=50)) == "로컬 답변"
    assert requests[0][0:2] == ("GET", "http://localhost:11434/v1/models")
    assert requests[1][0:2] == ("POST", "http://localhost:11434/v1/chat/completions")
    assert requests[1][2]["json"]["model"] == "local-model"
    assert requests[1][2]["json"]["reasoning_effort"] == "none"
    assert (g.api_calls, g.input_tokens, g.output_tokens) == (1, 12, 3)


def test_ollama_memory_error_has_actionable_message(tmp_path, monkeypatch):
    monkeypatch.setattr("app.main.LOG_DIR", tmp_path)

    class Client:
        def __init__(self, **kwargs): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def post(self, url, **kwargs):
            request = httpx.Request("POST", url)
            return httpx.Response(
                507, request=request,
                json={"error": {"message": "model does not fit under the dynamic memory ceiling"}},
            )

    import httpx
    monkeypatch.setattr("app.main.httpx.AsyncClient", Client)
    g = Game(settings(ollama_model="too-large-model"), seats(), mock_llm=True, dev=True)

    with pytest.raises(RuntimeError, match="Ollama 메모리 부족"):
        run(g._llm("질문", max_tokens=50))


def test_startup_password_and_key_stay_in_memory(tmp_path, monkeypatch):
    monkeypatch.setattr("app.main.LOG_DIR", tmp_path)
    settings_file = Path(__file__).resolve().parent.parent / "config" / "settings.yaml"
    before = settings_file.read_text(encoding="utf-8")
    app = make_app(mock_llm=False, dev=True, admin_password="classroom-pw", api_key="sk-secret")
    game = app.state.game
    assert game.settings["admin_token"] == "classroom-pw" and game.api_key == "sk-secret"
    client = TestClient(app, client=("127.0.0.1", 50000))
    assert client.post("/api/admin/setup", json={"admin_token": "wrong"}).status_code == 401
    assert client.post("/api/admin/setup", json={"admin_token": "classroom-pw"}).status_code == 200
    assert client.post("/api/admin/action", json={"admin_token": "classroom-pw", "action": "reset"}).status_code == 200
    assert app.state.game.settings["admin_token"] == "classroom-pw" and app.state.game.api_key == "sk-secret"
    assert client.get("/api/admin/state", headers={"X-Admin-Token": "classroom-pw"}).status_code == 200
    assert settings_file.read_text(encoding="utf-8") == before and "classroom-pw" not in before
    assert not any("sk-secret" in f.read_text(encoding="utf-8") or "classroom-pw" in f.read_text(encoding="utf-8")
                   for f in tmp_path.iterdir() if f.is_file())


def test_setup_needs_api_key_unless_demo(tmp_path, monkeypatch):
    monkeypatch.setattr("app.main.LOG_DIR", tmp_path)
    client = TestClient(make_app(mock_llm=False, dev=True, admin_password="pw"), client=("127.0.0.1", 50000))
    assert client.post("/api/admin/setup", json={"admin_token": "pw"}).status_code == 400
