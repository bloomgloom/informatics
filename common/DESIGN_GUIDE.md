# 인공지능 기초 수업 슬라이드 — 디자인 가이드

> `ai/ch2-1`, `ai/ch2-2`, `ai/ch2-3` 슬라이드에서 **실제로 적용되고 있는 값**을 추출해 정리한 공통 양식입니다.
> 새 단원(예: `ch1-1`)을 만들 때 이 문서를 그대로 따르면 기존 단원과 같은 모양이 나옵니다.
> 이 규칙을 그대로 구현한 공통 파일이 **`ai/common/slides.css`**, **`ai/common/slides.js`** 이고, 모든 컴포넌트의 사용 예는 **`ai/common/example.html`** 에 있습니다.
> (값의 출처: `ch2-2/styles.css`의 "최종 공통 화면 기준" 이후 규칙 + `ch2-3` 컴포넌트. ch2-3을 공통 파일로 바꿔 렌더링해 원본과 화면이 같은 것을 확인함)

---

## 0. 가장 중요한 원칙 — 스타일을 새로 쓰지 말고 재사용한다

디자인이 매번 달라지는 가장 큰 원인은 **CSS를 처음부터 다시 쓰기 때문**입니다.
공통 스타일과 스크립트를 그대로 불러오고, 단원 고유 배치만 작은 `styles.css`에 추가합니다.

```html
<link rel="stylesheet" href="../common/slides.css" />   <!-- 공통 기준: 단원에서 수정 금지 (글꼴도 여기서 불러옴) -->
<link rel="stylesheet" href="styles.css" />             <!-- 이 단원의 배치만 -->
...
<script src="../common/slides.js"></script>             <!-- 공통 내비게이션 -->
```

- 새로 만드는 단원은 `../ch2-2/styles.css`가 아니라 **`../common/`** 을 불러온다. (ch2-2 파일에는 ch2-2 전용 규칙이 섞여 있어서, ch2-2를 고치면 다른 단원까지 바뀔 수 있음)

- 단원 `styles.css`에는 **배치(grid, 비율, 높이)만** 쓴다.
- 색·글자 크기·테두리·모서리·번호 배지는 단원 CSS에서 **다시 정의하지 않는다.** 필요한 값은 아래 토큰(`var(--...)`)만 사용한다.
- 새 컴포넌트가 필요하면 5장의 컴포넌트 규격을 조합해서 만든다.

### 공통 클래스 한눈에 보기

| 분류 | 클래스 |
|---|---|
| 헤더 | `slide-header`, `unit`, `page-ref`, `subtitle` |
| 카드 | `panel` + `data-tone`, `section-heading`, `section-number` |
| 카드 안 | `soft-box`(연한 영역), `white-box`(흰 상자), `chips`(칩 묶음), `label`(30px 보조 글자) |
| 그림 | `textbook-example`(카드 안 그림+캡션), `card-diagram`, `figure-box`(연한 배경 그림 칸), `comparison-figure`(슬라이드 전체 그림) |
| 띠·목록 | `definition-strip`, `role-row`, `variable-list`(+`align-top`) |
| 표·코드 | `slide-table`(+머리글 `is-green`), `code-chip` |
| 배치 | `grid-2`, `grid-3`, `grid-4`, `two-column`, `concept-points`, `application-grid`, `fill`(남은 높이 채우기) |

---

## 1. 캔버스

| 항목 | 값 |
|---|---|
| 슬라이드 크기 | **1920 × 1080px** 고정, 화면 크기에 맞춰 `--deck-scale`로 축소(스크립트가 처리) |
| 슬라이드 안쪽 여백 | `52px` (사방) |
| 영역 사이 세로 간격 | `16px` (`.slide.active { gap }`) |
| 슬라이드 배경 | `--paper` (#ffffff) |
| 페이지(바깥) 배경 | `--page` (#f7fafc) |
| 덱 그림자 | `0 24px 70px rgba(36, 58, 96, 0.14)` |
| 상단 색 띠 | 높이 `12px`, `linear-gradient(90deg, blue, green, orange)` — `.slide::before`가 자동으로 그림 |
| 슬라이드 배치 | `display: flex; flex-direction: column` — 헤더 아래 본문 영역에 `flex: 1; min-height: 0` |

---

## 2. 색 토큰

모두 `ch2-2/styles.css`의 최종 `:root` 값입니다.

### 기본

| 토큰 | 값 | 용도 |
|---|---|---|
| `--ink` | `#172033` | 제목(h1) 및 기본 글자 |
| `--muted` | `#5c6b7d` | 부제목, 본문, 보조 설명 |
| `--line` | `#d7e0ea` | 카드 테두리, 구분선 |
| `--paper` | `#ffffff` | 슬라이드·카드 배경 |
| `--page` | `#f7fafc` | 덱 바깥 배경 |
| `--danger` / `--danger-soft` | `#c83449` / `#fff0f2` | 오류·주의 표시(드물게) |

### 3가지 톤 (영역 구분색)

| 톤 | 주색 `--tone` | 진한색 `--tone-dark` (제목·강조) | 보조색 `--tone-sub` (소제목) | 배지 `--tone-badge` (번호 원) | 연한 배경 `--tone-soft` (내부 영역) |
|---|---|---|---|---|---|
| blue | `#2563eb` | `#2563eb` | `#4f7fca` | `#eef5ff` | `#f6f8fb` |
| orange | `#f28c28` | `#c66b0d` | `#d98a3a` | `#fff4e8` | `#fbf8f6` |
| green | `#159957` | `#159957` | `#3fa873` | `#ecf9f2` | `#f6fbf8` |

- 톤은 HTML에서 `data-tone="blue|orange|green"`으로 지정하면 `--tone-*` 변수가 자동으로 설정된다.
- **순서는 항상 blue → orange → green.** 영역이 4개 이상이면 다시 blue부터 반복.
- 주황색 글자는 `--orange`(#f28c28)가 아니라 **`--tone-dark`(#c66b0d)** 를 쓴다(흰 배경에서 가독성).

---

## 3. 글꼴과 글자 위계

### 글꼴
- `"Nanum Gothic", "Apple SD Gothic Neo", "Noto Sans KR", sans-serif`
- **모든 글자 굵기 700** (제목·본문 구분을 굵기가 아닌 크기와 색으로 한다)
- 코드만 예외: `ui-monospace, SFMono-Regular, Menlo, monospace`

### 크기 위계 (교실 화면 기준, 최종 적용값)

| 단계 | 요소 | 크기 | 줄간격 | 색 |
|---|---|---|---|---|
| 슬라이드 번호 | `.unit` | **38px** | — | `--blue` |
| 교과서 쪽수 | `.page-ref` | **26px** | — | `--muted` |
| 페이지 제목 | `h1` | **82px** | 1 | `--ink` |
| 제목 밑 설명 | `.subtitle` | **36px** | 1.3 | `--muted`, 핵심어 `strong`은 `--blue` |
| 영역(칸) 제목 | `h2` | **64px** | 1.05 | `--tone-dark` |
| 영역 안 소제목 | `h3`, `dt` | **56px** | 1.08 | `--tone-sub` |
| 본문 | `p`, `dd`, 목록 | **36px** | 1.2 | `--muted`, 핵심어 `strong`은 `--tone-dark` |
| 사례·활용 예시 | 예시 문장 | **36px** | 1.2 | `--muted` (보조 라벨이 아니라 본문으로 취급) |
| 보조 라벨 | 그래프 축·범례, 그림 캡션, 칩 | **30px** | 1.15 | 문맥에 따라 `--muted` 또는 `--tone-dark` |
| 번호 배지 숫자 | `.section-number` | **24px** | 1 | `--tone-dark` |
| 하단 쪽 표시 | `.footer p` | 16px | — | `--muted` |

**규칙**
- 위 7개 크기(82 / 64 / 56 / 36 / 30 / 26·24 / 38) 외의 글자 크기는 만들지 않는다.
- 내용이 넘치면 **글자를 줄이지 말고 내용을 줄이거나 슬라이드를 나눈다.** (본문 36px 아래로 내리지 않음)
- 강조는 문장 전체가 아니라 **핵심 용어만** `<strong>`으로 한다.
- 밑줄, 기울임, 그림자 글자, 그라데이션 글자는 쓰지 않는다.

---

## 4. 슬라이드 헤더 (모든 슬라이드 공통)

```html
<div class="slide-header">
  <p class="unit">01</p><p class="page-ref">p.14</p>
  <h1>지능의 이해</h1>
  <p class="subtitle">지능은 새로운 상황을 이해하고 <strong>합리적인 판단과 해결 방법</strong>을 이끌어 내는 능력이다.</p>
</div>
```

| 요소 | 규칙 |
|---|---|
| `.unit` | 슬라이드 순번, **두 자리**(`01`, `02`…). 배경 없는 파란 글자 |
| `.page-ref` | 오른쪽 위 고정. 교과서 쪽수 `p.14`, 범위는 `p.18~19`. 2px `--line` 테두리, `#f6f8fb` 배경, 알약 모양(radius 999px), 안쪽 여백 `8px 16px` |
| `h1` | 그 슬라이드의 **최상위 개념 하나**. 짧은 명사구 |
| `.subtitle` | **한 문장**. 정의 또는 "~에 주목해 ~해 보자" 형식. 핵심어 1~2개만 `strong` |

---

## 5. 컴포넌트 규격

### 5.1 영역 카드 `.panel`
본문 영역의 기본 단위(칸).

| 속성 | 값 |
|---|---|
| 배경 | `#fff` |
| 테두리 | `2px solid var(--line)` |
| 상단 강조선 | `10px solid var(--tone)` |
| 모서리 | `8px` |
| 안쪽 여백 | `22px` |
| 그림자 | 없음 |

```html
<article class="panel" data-tone="blue">
  <header class="section-heading"><span class="section-number">01</span><h2>인식</h2></header>
  <p>이미지, 소리, 언어 등을 <strong>인식하고 이해</strong>하는 것</p>
</article>
```

### 5.2 영역 제목 `.section-heading` + 번호 배지 `.section-number`
- 번호 원: **54 × 54px**, 원형, 배경 `--tone-badge`, 글자 `--tone-dark` 24px
- 번호는 **제목 바로 왼쪽**, 같은 행. 간격 `12px`, 행 최소 높이 `64px`
- 카드 오른쪽 위 구석에 번호를 따로 띄우는(absolute) 방식은 쓰지 않는다.
- 번호는 카드 순서대로 `01`, `02`, `03`…

### 5.3 카드 안 내부 영역 (자료·예시·세부 항목)
- 배경 `--tone-soft`, 모서리 `8px`, 안쪽 여백 `16px`, **테두리 없음**
- 그 안에 들어가는 실제 그림이나 값 상자는 `#fff`로 다시 분리한다.
- 소제목(h3/dt)은 이 영역 위에 바로 놓고 `--tone-sub` 색을 쓴다(소제목용 흰 상자를 따로 만들지 않음).

### 5.4 교과서 그림
```html
<figure class="textbook-example">
  <img src="assets/textbook-human-intelligence.png" alt="그림 내용을 설명하는 문장" />
  <figcaption>인간의 지능</figcaption>
</figure>
```
- 카드 안: 배경 `--tone-soft`, 모서리 8px, `object-fit: contain`, 캡션 30px `--tone-dark` 가운데 정렬
- 슬라이드 전체를 차지하는 그림(`.comparison-figure`): 1px `--line` 테두리, 모서리 22px, 흰 배경, 그림자 `0 14px 34px rgba(36, 58, 96, .12)`, 최대 높이 약 710px
- 파일명은 `assets/textbook-<내용>.png`, 직접 그린 도식은 `assets/<내용>.svg`
- `alt`는 반드시 그림 내용을 한 문장으로 쓴다.

### 5.5 정의 띠 `.definition-strip` (슬라이드 하단 핵심 요약)
- 배경 `--blue-soft`, 모서리 **18px**, 안쪽 여백 `20px 30px`, 가운데 정렬, 항목 간격 34px
- 용어 `strong` 40px `--blue` + 설명 34px `--ink`
```html
<div class="definition-strip"><strong>인공지능</strong><span>인간의 지능적인 판단과 행위를 컴퓨터로 흉내 내어 구현한 것</span></div>
```

### 5.6 역할 줄 `.role-row` (구성 요소 나열)
- 흰 배경, 1px `--line` 테두리, 모서리 18px, 30px 글자, 항목 이름 `b`는 `--blue`
```html
<div class="role-row"><span><b>입력</b> 환경을 인식</span><span><b>판단</b> 상황을 판단</span><span><b>출력</b> 행동을 결정</span></div>
```

### 5.7 칩(태그)
- 알약 모양(radius 999px), 안쪽 여백 `10px 16px`, 배경 `--tone-soft`, 글자 `--tone-dark` 30px, 간격 12px
- 사례 이름처럼 **짧은 낱말 나열**에만 쓴다.

### 5.8 기호·용어 목록 `.variable-list`
- 각 줄: `64px | 1fr` 2열, 배경 `--blue-soft`, 모서리 8px, 여백 `14px 16px`
- 기호 `b` 40px `--blue` 가운데, 설명 30px `--muted`, 핵심어 `strong` `--blue`

### 5.9 표 (ch2-1 비교표 기준)
- 셀: 2px `--line` 선, 가운데 정렬, 여백 약 `12px 18px`, 글자 32px
- 머리글: 배경 `#eaf2ff`, 글자 `--blue` 35px, 아래 5px `#93b9f6` 선
- 첫 열(구분): 배경 `#f6f8fb`, 글자 `--muted`
- 대비시키는 두 번째 열 머리글은 `#e9f9f0` 배경 + `--green` 글자

### 5.10 코드 (ch2-1 기준)
- 배경 `#172033`, 글자 흰색, monospace, 모서리 7px, 여백 `9px 12px`
- 코드는 그 결과(흰 상자, 얇은 선) 바깥 위쪽에 둔다.

---

## 6. 배치 패턴

모든 본문 배치는 `flex: 1; min-height: 0; display: grid`로 헤더 아래 남은 공간을 채운다.

| 패턴 | 클래스 예 | 열 구성 | 간격 |
|---|---|---|---|
| 2칸 비교 | `.two-column` | `repeat(2, minmax(0, 1fr))` | 28px |
| 2칸 요점 | `.concept-points` | `repeat(2, minmax(0, 1fr))` | 22px |
| 3칸 (가장 흔함) | — | `repeat(3, minmax(0, 1fr))` 정확히 1:1:1 | 22px |
| 4칸 사례 | `.application-grid` | `repeat(4, minmax(0, 1fr))` | 22px |
| 그림 + 설명 | `.deep-learning-layout` | `1.6fr 1fr` | 28px |
| 그림 + 기호 목록 | `.perceptron-detail` | `minmax(0, 1.8fr) minmax(440px, .8fr)` | 22px |
| 주 영역 + 보조 영역 | — | `2fr 1fr` 또는 `1fr 2fr` | 22px |

**규칙**
- 같은 단계의 칸은 **같은 너비·간격·안쪽 여백**.
- 한 슬라이드의 칸은 많아야 4개. 그 이상이면 슬라이드를 나눈다.
- 장식보다 정보 위계가 우선. 아이콘·일러스트·배경 무늬를 추가하지 않는다.

---

## 7. 내비게이션 (공통 스크립트가 처리)

- 좌우 가장자리 50px 투명 버튼(`.nav-prev`, `.nav-next`), 화살표 30px, 평소 투명도 0.28 → 마우스 올리면 0.65
- 하단 가운데: 점(12px, 현재 슬라이드는 34px 너비 파란색) + `현재 / 전체`
- 키보드: `→`·`Space` 다음, `←` 이전
- 주소에 `?slide=3`을 붙이면 해당 슬라이드로 바로 열림

슬라이드 파일 끝에 항상 다음을 넣는다.

```html
</main>
<button class="nav-zone nav-prev" type="button" aria-label="이전 슬라이드"><span></span></button>
<button class="nav-zone nav-next" type="button" aria-label="다음 슬라이드"><span></span></button>
<div class="footer"><div class="dots" aria-label="슬라이드 위치"></div><p><span id="currentSlide">1</span> / <span id="totalSlides">1</span></p></div>
<script src="../common/slides.js"></script>
```

---

## 8. 전체 골격 템플릿

```html
<!doctype html>
<html lang="ko">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <meta name="theme-color" content="#eef0f8" />
    <title>단원 제목</title>
    <link rel="stylesheet" href="../common/slides.css" />
    <link rel="stylesheet" href="styles.css" />
  </head>
  <body>
    <main class="deck" aria-live="polite">
      <section class="slide active" data-slide="1">
        <div class="slide-header">
          <p class="unit">01</p><p class="page-ref">p.00</p>
          <h1>제목</h1>
          <p class="subtitle">한 문장 설명, <strong>핵심어</strong>만 강조</p>
        </div>
        <div class="grid-2 fill">
          <article class="panel" data-tone="blue">
            <header class="section-heading"><span class="section-number">01</span><h2>영역 제목</h2></header>
            <p>본문, <strong>핵심 용어</strong>만 강조</p>
          </article>
          <article class="panel" data-tone="orange">
            <header class="section-heading"><span class="section-number">02</span><h2>영역 제목</h2></header>
            <p>본문</p>
          </article>
        </div>
        <div class="definition-strip"><strong>핵심</strong><span>한 줄 요약</span></div>
      </section>
      <!-- 다음 슬라이드: class="slide" (active 없음), data-slide 번호 증가 -->
    </main>
    <!-- 7장의 내비게이션 블록 -->
  </body>
</html>
```

- 첫 슬라이드만 `class="slide active"`, 나머지는 `class="slide"`
- `data-slide`는 1부터 순서대로. 단원 CSS에서 특정 슬라이드만 조정할 때 `.slide[data-slide="3"] ...`으로 사용

---

## 9. 메인 페이지(`ai/index.html`) 단원 카드

새 단원을 만들면 메인 페이지에 같은 형식의 카드를 추가한다.

```html
<article class="chapter">
  <div class="chapter-main">
    <span class="number">1-1</span>
    <span class="title">
      <b>인공지능의 원리</b>
      <span>지능의 이해와 인공지능 시스템</span>
    </span>
    <a class="action" href="./ch1-1/">열기</a>
  </div>
  <!-- 실습 자료가 있을 때만 .resources 블록 추가 -->
</article>
```

- 메인 페이지는 슬라이드와 별도 스타일(단원 번호 보라색 `#7c3aed`, 카드 radius 12px)을 쓰므로 슬라이드 쪽 규칙과 섞지 않는다.

---

## 10. 단원 사이 차이 (참고)

추출 과정에서 확인한 불일치입니다. 새 단원은 **오른쪽 열(이 가이드의 기준)** 을 따른다.

| 항목 | 차이 | 이 가이드의 기준 |
|---|---|---|
| ch2-1 스타일 | ch2-1은 독자 스타일시트를 사용. 부제목 34px, 본문에 21~32px 등 작은 크기가 다수 남아 있음 | ch2-2 최종값(부제목 36px, 본문 36px) |
| h1 색 | `ch2-3/styles.css` 주석은 "82px, 파란색"이라고 적혀 있지만, 실제 적용값(ch2-2 최종 규칙)은 `--ink` | 실제 적용값 `--ink` |
| 4칸 h2 크기 | `ch2-3` 주석은 "좁은 칸은 48px"이지만 실제로는 공통 규칙 `64px !important`가 적용됨 | 64px. 4칸에서 제목이 넘치면 제목을 짧게 줄인다 |
| 모서리 | ch2-2 앞부분에 20px 모서리가 남아 있으나 최종 규칙에서 8px로 덮어씀 | 카드·내부 영역 8px, 띠 18px, 전체 그림 22px, 알약 999px |
| ch2-2 1행 주석 | `공통 기준: DESIGN_GUIDE.md`라고 되어 있으나 저장소에 해당 파일이 없음 | 이 문서를 그 파일로 사용 |
| 공통 파일 위치 | ch2-3은 `../ch2-2/` 파일을 불러옴 | 새 단원은 `../common/`. 기존 단원은 그대로 두어도 화면은 같음 |

> h1 색과 4칸 h2 크기는 의도와 실제가 다른 부분이라, 원하는 쪽으로 한 번 정해서 이 문서를 고쳐 두면 이후로는 흔들리지 않습니다.

---

## 11. 작성 체크리스트

- [ ] `../common/slides.css`와 `../common/slides.js`를 불러왔는가
- [ ] 단원 `styles.css`에 색·글자 크기·테두리를 새로 정의하지 않았는가
- [ ] 모든 슬라이드에 `unit`(두 자리) · `page-ref` · `h1` · `subtitle`이 있는가
- [ ] 글자 크기가 82 / 64 / 56 / 36 / 30 / 26 / 24 / 38 중 하나인가 (본문 36px 미만 없음)
- [ ] 영역 카드에 `data-tone`이 blue → orange → green 순서로 붙어 있는가
- [ ] 영역 번호가 54px 원으로 제목 바로 왼쪽에 있는가
- [ ] `strong` 강조가 핵심 용어에만 쓰였는가
- [ ] 한 슬라이드의 칸이 4개 이하이고, 같은 단계 칸의 크기·간격이 같은가
- [ ] 교과서 그림 파일명이 `textbook-*.png`이고 `alt`가 있는가
- [ ] 1920×1080에서 넘치거나 잘리는 글자가 없는가 (브라우저 확대/축소로 확인)
- [ ] 메인 페이지에 단원 카드를 추가했는가
