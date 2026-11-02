# 교실판 튜링 테스트

교사용 컴퓨터 한 대에서 서버를 실행하고, 같은 네트워크의 학생 기기가 브라우저로 참여하는 턴제 튜링 테스트입니다. 서버는 macOS와 Windows에서 실행할 수 있습니다. 모든 학생은 자기 게임의 질문자이면서 다른 학생 게임의 사람 증인입니다. 따라서 질문 단계와 답변 단계 모두 전원이 함께 활동합니다.

## 처음 설치

필요한 것은 **Python 3.11 이상**뿐입니다. GitHub에서 프로젝트를 내려받은 다음 터미널에서 실행하세요.

```bash
chmod +x setup.sh start.sh start-mock.sh
./setup.sh
```

`setup.sh`가 `.venv` 가상환경을 만들고 필요한 패키지를 자동 설치합니다. 이후 실제 수업 서버는 다음처럼 실행합니다.

```bash
./start.sh
```

실행하면 터미널에 교사 관리 화면(`/admin`), 프로젝터 현황판(`/board`), 학생 접속 주소가 표시됩니다.

### Windows에서 설치·실행

Python 3.11 이상을 설치할 때 설치 화면의 **Add Python to PATH**를 선택하세요. 프로젝트 폴더를 압축 해제한 뒤 `setup.bat`을 더블클릭하거나 명령 프롬프트에서 실행합니다.

```bat
setup.bat
start.bat
```

Windows Defender 방화벽 창이 나타나면 **개인 네트워크**의 Python 통신을 허용하세요. 교사 PC 주소는 명령 프롬프트에서 `ipconfig`를 실행하고 현재 네트워크 어댑터의 IPv4 주소를 확인하면 됩니다.

브라우저에서 교사 관리 화면 `http://127.0.0.1:9000/admin`, 프로젝터 현황판 `http://127.0.0.1:9000/board`를 엽니다. 서버를 켤 때 터미널에서 Claude API 키를 입력하고 교사 화면 비밀번호를 정합니다. 둘 다 파일에 저장되지 않아 켤 때마다 입력합니다. 교사 관리 화면에서 그 비밀번호로 들어가 게임을 시작하세요. 학생은 페이지를 여는 것만으로 참가하지 않으며 반드시 `참여하기`를 눌러야 합니다. API 키는 서버 메모리에만 있으며 서버를 재시작하면 다시 입력해야 합니다.

## 수업 전 설정

`setup`이 `config/seats.example.csv`, `config/roster_names.example.txt`로 `local/seats.csv`, `local/roster_names.txt`를 만듭니다. 이 두 파일은 git에서 제외됩니다.

1. `local/seats.csv`의 IP, 좌석 행·열과 책상 짝을 나타내는 `pair`를 실제 컴퓨터실에 맞게 수정합니다.
2. 교사 화면과 현황판은 서버를 켠 컴퓨터에서 `http://127.0.0.1:포트`로 엽니다. 다른 기기에서 열 때만 `config/settings.yaml`의 `teacher_ips`에 그 기기의 IP를 추가합니다.
3. 필요하면 `local/roster_names.txt`에 학생 이름을 한 줄에 하나씩 넣습니다. 이름이 메시지에 포함되면 신원 노출로 차단됩니다.
4. `config/settings.yaml`의 `model`이 사용 중인 Anthropic 계정에서 제공되는 Claude Haiku 모델 ID인지 확인합니다. 기획서 기본값 `claude-haiku-5-5`를 그대로 넣어 두었습니다.
5. 운영체제의 방화벽이 묻는 경우 Python의 로컬 네트워크 통신을 허용합니다.
6. `start.sh` 또는 `start.bat`이 터미널에 표시한 학생 접속 주소를 안내합니다.

학교 Wi-Fi가 기기 간 통신을 막는 경우가 있으므로 수업 전에 학생 기기 한 대에서 접속을 꼭 시험하세요. 대화는 좌석 번호와 함께 JSONL 로그에 기록되고, 운영 모드에서는 메시지가 Anthropic API에 전달될 수 있다는 점도 학생에게 미리 안내해야 합니다.

## 로컬 Ollama 데모

`mock` 실행 파일은 고정된 가짜 답을 만드는 모드가 아니라, Claude 대신 로컬 [Ollama](https://ollama.com/)의 OpenAI 호환 Chat Completions API를 사용하는 데모 모드입니다.

1. `ollama pull gemma4:e4b`로 모델을 내려받고 Ollama를 시작합니다. 기본 OpenAI 호환 API 주소는 `http://localhost:11434/v1`입니다.
2. 필요하면 `config/settings.yaml`의 `ollama_base_url`과 `ollama_model`을 수정합니다. `ollama_model`이 비어 있으면 `/v1/models`의 첫 모델을 선택합니다.
3. 아래 명령으로 데모 서버를 실행합니다. 앱은 `9000` 포트를 사용합니다.

```bash
./start-mock.sh
```

Windows용 `start-mock.bat`도 같은 연결 방식을 사용합니다. Ollama에 API 키를 설정했다면 서버를 켤 때 입력하고, 기본 로컬 서버를 사용한다면 Enter를 칩니다.

개발 모드에서는 `http://127.0.0.1:9000/?seat=1`처럼 쿼리로 좌석을 바꿔 볼 수 있습니다. 다른 터미널에서 자동 시뮬레이터도 실행할 수 있습니다.

```bash
.venv/bin/python scripts/simulate.py --students 30 --url http://127.0.0.1:9000 --token 정한비밀번호
```

실제 운영용 `./start.sh`에는 개발 좌석 우회가 켜지지 않습니다.

## 운영 화면

- `/` — 학생 화면. IP로 좌석을 식별하고 참여 버튼을 누른 뒤 단계별 활동을 표시합니다.
- `/admin` — 교사 전용. 참여 좌석·제출·경고·두 게임의 대화·API 사용량 확인, 진행, 퇴장, CSV 내보내기.
- `/board` — 프로젝터용. 게임 중에는 개인 정보 없이 현재 단계와 진행률만 표시합니다.

로그는 `logs/session-날짜시각.jsonl`에 쌓입니다. CSV는 관리 화면에서 내려받을 수 있습니다. 로그에는 차단된 원문도 포함되므로 수업 후 보관 정책에 맞춰 안전하게 삭제하거나 보관하세요.

## 테스트

```bash
.venv/bin/pytest -q
```

30명·31명 순환 매칭, 2명 상호 매칭, 단계별 정보 보호, 동시 공개, AI 대타, 질문·답변별 2단계 필터 처리, Claude와 Ollama 요청 형식을 검사합니다.

