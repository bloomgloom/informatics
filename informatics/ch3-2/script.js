const slides = Array.from(document.querySelectorAll(".slide"));
const prevButton = document.querySelector(".nav-prev");
const nextButton = document.querySelector(".nav-next");
const currentSlide = document.querySelector("#currentSlide");
const totalSlides = document.querySelector("#totalSlides");
const dots = document.querySelector(".dots");
const deck = document.querySelector(".deck");

const DESIGN_WIDTH = 1920;
const DESIGN_HEIGHT = 1080;

function fitDeckToViewport() {
  const scale = Math.min(
    window.innerWidth / DESIGN_WIDTH,
    window.innerHeight / DESIGN_HEIGHT,
  );

  deck.style.setProperty("--deck-scale", String(scale));
}

window.addEventListener("resize", fitDeckToViewport);
fitDeckToViewport();

let activeIndex = 0;

slides.forEach((_, index) => {
  const dot = document.createElement("button");
  dot.className = "dot";
  dot.type = "button";
  dot.setAttribute("aria-label", `${index + 1}번 슬라이드로 이동`);
  dot.addEventListener("click", () => showSlide(index));
  dots.append(dot);
});

const dotButtons = Array.from(document.querySelectorAll(".dot"));
totalSlides.textContent = String(slides.length);

function showSlide(index) {
  activeIndex = (index + slides.length) % slides.length;
  slides.forEach((slide, slideIndex) => slide.classList.toggle("active", slideIndex === activeIndex));
  dotButtons.forEach((dot, dotIndex) => dot.classList.toggle("active", dotIndex === activeIndex));
  currentSlide.textContent = String(activeIndex + 1);
  const url = new URL(window.location.href);
  url.searchParams.set("slide", String(activeIndex + 1));
  window.history.replaceState(null, "", url);
}

function syncScrollPosition(source, target) {
  const sourceMax = source.scrollHeight - source.clientHeight;
  const targetMax = target.scrollHeight - target.clientHeight;
  const ratio = sourceMax <= 0 ? 0 : source.scrollTop / sourceMax;
  target.scrollTop = targetMax <= 0 ? 0 : ratio * targetMax;
}

function syncScrollPair(first, second) {
  if (!first || !second) return;

  let syncing = false;
  const sync = (source, target) => {
    if (syncing) return;
    syncing = true;
    syncScrollPosition(source, target);
    requestAnimationFrame(() => {
      syncing = false;
    });
  };

  first.addEventListener("scroll", () => sync(first, second), { passive: true });
  second.addEventListener("scroll", () => sync(second, first), { passive: true });
}

function scrollPairToBottom(first, second) {
  requestAnimationFrame(() => {
    first.scrollTop = first.scrollHeight;
    second.scrollTop = second.scrollHeight;
  });
}

function updateVisibleProblemRows(rows, explanations, activeRow, historyList, explainList) {
  rows.forEach((row, rowIndex) => row.classList.toggle("hidden-step", rowIndex > activeRow));
  explanations.forEach((explanation, rowIndex) => explanation.classList.toggle("hidden-step", rowIndex > activeRow));

  const panels = [historyList, explainList];
  panels.forEach((panel) => {
    Array.from(panel.querySelectorAll(".history-group, .explain-group")).forEach((group) => {
      const rowItems = Array.from(group.querySelectorAll(".history-line, .explain-row"));
      group.classList.toggle("hidden-step", rowItems.length > 0 && rowItems.every((item) => item.classList.contains("hidden-step")));
    });
  });

  scrollPairToBottom(historyList, explainList);
}

prevButton.addEventListener("click", () => showSlide(activeIndex - 1));
nextButton.addEventListener("click", () => showSlide(activeIndex + 1));

document.addEventListener("keydown", (event) => {
  if (event.target.matches("input, textarea")) return;
  if (event.key === "ArrowRight" || event.key === " ") showSlide(activeIndex + 1);
  if (event.key === "ArrowLeft") showSlide(activeIndex - 1);
});

const requestedSlide = Number(new URLSearchParams(window.location.search).get("slide"));
showSlide(Number.isInteger(requestedSlide) && requestedSlide > 0 ? requestedSlide - 1 : 0);

function parseValues(value) {
  return value
    .trim()
    .split(/\s+/)
    .map((item) => Number(item.trim()))
    .filter((item) => Number.isFinite(item));
}

function renderArray(container, values, state = {}) {
  const max = Math.max(...values, 1);
  container.innerHTML = values
    .map((value, index) => {
      const classes = ["array-item"];
      if (state.compare?.includes(index)) classes.push("compare");
      if (state.swap?.includes(index)) classes.push("swap");
      if (state.fixed?.includes(index)) classes.push("fixed");
      if (state.found === index) classes.push("found");
      if (state.range && !state.range.includes(index)) classes.push("out");
      if (state.range?.includes(index)) classes.push("range");
      const height = Math.max(42, Math.round((value / max) * 190));
      return `<div class="${classes.join(" ")}"><div class="bar" style="height:${height}px">${value}</div></div>`;
    })
    .join("");
}

function renderStepBoxes(step) {
  return step.values
    .map((value, index) => {
      const classes = ["step-cell"];
      if (step.compare?.includes(index)) classes.push("compare-cell");
      if (step.swap?.includes(index)) classes.push("swap-cell");
      if (step.fixed?.includes(index)) classes.push("fixed-cell");
      if (step.found === index) classes.push("found-cell");
      if (step.range && !step.range.includes(index)) classes.push("out-cell");
      if (step.range?.includes(index)) classes.push("range-cell");
      return `<span class="${classes.join(" ")}">${value}</span>`;
    })
    .join("");
}

function makeBubbleSteps(inputValues) {
  const values = [...inputValues];
  const steps = [{ values: [...values], label: "데이터", roundLabel: "데이터", text: `카드를 [${values.join(", ")}] 순서로 놓고 시작한다.` }];

  let round = 1;
  for (let end = values.length - 1; end > 0; end--) {
    for (let j = 0; j < end; j++) {
      const a = values[j];
      const b = values[j + 1];
      const shouldSwap = a > b;
      steps.push({
        values: [...values],
        label: "",
        roundLabel: `${round}단계`,
        compare: [j, j + 1],
        text: `${a}와 ${b}를 비교한다. ${shouldSwap ? "앞의 값이 더 크므로 두 수의 자리를 교환한다." : "앞의 값이 더 작으므로 교환하지 않는다."}`,
      });
      if (shouldSwap) {
        [values[j], values[j + 1]] = [values[j + 1], values[j]];
        steps.push({
          values: [...values],
          label: "",
          roundLabel: `${round}단계`,
          swap: [j, j + 1],
          text: `교환 후 [${values.join(", ")}]이 된다.`,
        });
      }
    }
    steps.push({
      values: [...values],
      label: "",
      roundLabel: `${round}단계`,
      fixed: [end],
      text: `${values[end]}이 오른쪽 끝 위치에 고정된다.`,
    });
    round += 1;
  }

  steps.push({
    values: [...values],
    label: "완료",
    roundLabel: "완료",
    fixed: values.map((_, index) => index),
    text: `[${values.join(", ")}] 순서로 정렬되어 실행을 종료한다.`,
  });
  return steps;
}

function makeSelectionSteps(inputValues) {
  const values = [...inputValues];
  const steps = [{ values: [...values], label: "데이터", roundLabel: "데이터", text: `카드를 [${values.join(", ")}] 순서로 놓고 시작한다.` }];

  let round = 1;
  for (let i = 0; i < values.length - 1; i++) {
    let min = i;
    steps.push({
      values: [...values],
      label: "",
      roundLabel: `${round}단계`,
      compare: [i],
      text: `${values[i]}을 기준 위치로 정하고 최솟값 후보로 둔다.`,
    });

    for (let j = i + 1; j < values.length; j++) {
      const isNewMin = values[j] < values[min];
      steps.push({
        values: [...values],
        label: "",
        roundLabel: `${round}단계`,
        compare: [min, j],
        text: `최솟값 후보 ${values[min]}와 ${values[j]}를 비교한다. ${isNewMin ? `${values[j]}가 더 작으므로 최솟값 후보를 바꾼다.` : "현재 최솟값 후보를 유지한다."}`,
      });
      if (isNewMin) min = j;
    }

    [values[i], values[min]] = [values[min], values[i]];
    steps.push({
      values: [...values],
      label: "",
      roundLabel: `${round}단계`,
      swap: [i, min],
      fixed: [i],
      text: `찾은 최솟값을 기준 위치와 교환하여 [${values.join(", ")}]이 된다.`,
    });
    round += 1;
  }

  steps.push({
    values: [...values],
    label: "완료",
    roundLabel: "완료",
    fixed: values.map((_, index) => index),
    text: `[${values.join(", ")}] 순서로 정렬되어 실행을 종료한다.`,
  });
  return steps;
}

function makeLinearSteps(values, target) {
  const steps = [{ values, label: "데이터", roundLabel: "데이터", text: `${target}을 찾기 위해 첫 번째 값부터 차례대로 비교한다.` }];

  for (let i = 0; i < values.length; i++) {
    const found = values[i] === target;
    steps.push({
      values,
      label: `${i + 1}단계`,
      roundLabel: `${i + 1}단계`,
      compare: [i],
      found: found ? i : undefined,
      text: `${values[i]}와 ${target}을 비교한다. ${found ? "같으므로 탐색을 종료한다." : "같지 않으므로 다음 값으로 이동한다."}`,
    });
    if (found) break;
  }

  return steps;
}

function makeBinarySteps(values, target) {
  const steps = [{ values, label: "데이터", roundLabel: "데이터", text: `정렬된 데이터에서 ${target}을 찾기 위해 가운데 값을 확인한다.` }];
  let left = 0;
  let right = values.length - 1;

  while (left <= right) {
    const mid = Math.floor((left + right) / 2);
    const range = Array.from({ length: right - left + 1 }, (_, index) => left + index);

    if (values[mid] === target) {
      steps.push({
        values,
        label: `${steps.length}단계`,
        roundLabel: `${steps.length}단계`,
        range,
        compare: [mid],
        found: mid,
        text: `중앙값 ${values[mid]}이 ${target}과 같으므로 탐색을 종료한다.`,
      });
      break;
    }

    const goRight = target > values[mid];
    steps.push({
      values,
      label: `${steps.length}단계`,
      roundLabel: `${steps.length}단계`,
      range,
      compare: [mid],
      direction: goRight ? "right" : "left",
      text: `${target}은 중앙값 ${values[mid]}보다 ${goRight ? "크므로 오른쪽" : "작으므로 왼쪽"}에 있는 데이터들을 탐색한다.`,
    });

    if (goRight) left = mid + 1;
    else right = mid - 1;
  }

  return steps;
}

function makeSteps(type, values, target) {
  if (type === "bubble") return makeBubbleSteps(values);
  if (type === "selection") return makeSelectionSteps(values);
  if (type === "linear") return makeLinearSteps(values, target);
  return makeBinarySteps(values, target);
}

function groupSteps(visibleSteps, activeIndex) {
  const groups = [];
  visibleSteps.forEach((step, index) => {
    const label = step.roundLabel || step.label;
    const last = groups[groups.length - 1];
    if (!last || last.label !== label) {
      groups.push({ label, active: false, items: [] });
    }
    const group = groups[groups.length - 1];
    group.active = group.active || index === activeIndex;
    group.items.push({ step, active: index === activeIndex });
  });
  return groups;
}

document.querySelectorAll(".sim-layout").forEach((simulation) => {
  const type = simulation.dataset.sim;
  const defaultValues = simulation.dataset.values;
  const defaultTarget = simulation.dataset.target || "";
  simulation.innerHTML = `
    <article class="sim-panel">
      <div class="control-row">
        <input class="values-input" value="${defaultValues}" aria-label="데이터 값" />
        ${type === "linear" || type === "binary" ? `<input class="target-input" value="${defaultTarget}" aria-label="찾을 값" />` : ""}
        <button class="ghost-btn reset-btn" type="button">적용</button>
      </div>
      <div class="array-view"></div>
      <button class="primary-btn next-step" type="button">다음 단계</button>
    </article>
    <article class="history-panel">
      <h2>단계</h2>
      <div class="history-list"></div>
    </article>
    <article class="explain-panel">
      <h2>설명</h2>
      <div class="explain-list"></div>
    </article>
  `;

  const valueInput = simulation.querySelector(".values-input");
  const targetInput = simulation.querySelector(".target-input");
  const arrayView = simulation.querySelector(".array-view");
  const historyList = simulation.querySelector(".history-list");
  const explainList = simulation.querySelector(".explain-list");
  let steps = [];
  let stepIndex = 0;

  syncScrollPair(historyList, explainList);

  function setup() {
    const values = parseValues(valueInput.value);
    const target = targetInput ? Number(targetInput.value) : undefined;
    steps = makeSteps(type, values, target);
    stepIndex = 0;
    render();
  }

  function render() {
    const step = steps[stepIndex];
    const visibleSteps = steps.slice(0, stepIndex + 1);
    const groups = groupSteps(visibleSteps, stepIndex);
    renderArray(arrayView, step.values, step);

    historyList.innerHTML = groups
      .map(
        (group) => `
          <div class="history-group ${group.active ? "active" : ""}">
            <span class="round-label">${group.label}</span>
            <div class="group-lines">
              ${group.items
                .map(
                  ({ step: item, active }) => `
                    <div class="history-line ${active ? "active" : ""}">
                      <div class="step-boxes">${renderStepBoxes(item)}</div>
                    </div>
                  `,
                )
                .join("")}
            </div>
          </div>
        `,
      )
      .join("");

    explainList.innerHTML = groups
      .map(
        (group) => `
          <div class="explain-group ${group.active ? "active" : ""}">
            <span class="round-label">${group.label}</span>
            <div class="group-lines">
              ${group.items
                .map(({ step: item, active }) => `<div class="explain-row ${active ? "active" : ""}">${hideAnswerText(item.text)}</div>`)
                .join("")}
            </div>
          </div>
        `,
      )
      .join("");

    historyList.scrollTop = historyList.scrollHeight;
    explainList.scrollTop = explainList.scrollHeight;
  }

  simulation.querySelector(".reset-btn").addEventListener("click", setup);
  simulation.querySelector(".next-step").addEventListener("click", () => {
    stepIndex = Math.min(stepIndex + 1, steps.length - 1);
    render();
  });
  setup();
});

function renderProblemCells(step) {
  return step.values
    .map((value, index) => {
      const classes = ["problem-cell"];
      if (step.compare?.includes(index)) classes.push("compare-cell");
      if (step.swap?.includes(index)) classes.push("swap-cell");
      if (step.fixed?.includes(index)) classes.push("fixed-cell");
      if (step.found === index) classes.push("found-cell");
      if (step.range && !step.range.includes(index)) classes.push("out-cell");
      if (step.range?.includes(index)) classes.push("range-cell");
      return `<input class="${classes.join(" ")}" inputmode="numeric" data-answer="${value}" aria-label="숫자 입력" />`;
    })
    .join("");
}

function renderBinaryChoiceCells(step, stepIndex) {
  const correctIndex = step.compare?.[0] ?? -1;
  return step.values
    .map((value, index) => {
      const classes = ["binary-choice"];
      if (step.range && !step.range.includes(index)) classes.push("out-cell");
      if (step.range?.includes(index)) classes.push("range-cell");
      const side = index < correctIndex ? "left" : index > correctIndex ? "right" : "center";
      return `<button class="${classes.join(" ")}" type="button" data-step="${stepIndex}" data-index="${index}" data-correct="${correctIndex}" data-side="${side}">${value}</button>`;
    })
    .join("");
}

function renderBinaryExplainRow(step) {
  const centerText = step.found === undefined ? "선택한 중앙값을 찾을 값과 비교한다." : "선택한 중앙값이 찾을 값과 같으면 탐색을 종료한다.";
  return `
    <div class="explain-row binary-explain-row">
      <div class="binary-center-note hidden-explain">${centerText}</div>
      <div class="binary-direction-note hidden-explain">${hideAnswerText(step.text)}</div>
    </div>
  `;
}

function makeBubbleProblemActions(inputValues) {
  return makeBubbleSteps(inputValues)
    .slice(1)
    .map((step) => {
      if (step.compare && !step.swap && !step.fixed) {
        return {
          ...step,
          kind: "pair",
          prompt: "비교할 두 값을 선택하세요.",
          correctStart: Math.min(...step.compare),
          text: "현재 배열에서 서로 이웃한 두 값을 비교 대상으로 선택한다.",
        };
      }

      return {
        ...step,
        kind: "input",
        prompt: "배열 상태를 입력하세요.",
      };
    });
}

function renderBubbleChoiceCells(action, rowIndex) {
  return action.values
    .map((value, index) => `<button class="bubble-choice" type="button" data-bubble-row="${rowIndex}" data-index="${index}" data-correct-start="${action.correctStart}">${value}</button>`)
    .join("");
}

function makeSelectionProblemActions(inputValues) {
  const values = [...inputValues];
  const actions = [];
  let round = 1;

  for (let i = 0; i < values.length - 1; i++) {
    let min = i;
    actions.push({
      kind: "click",
      values: [...values],
      roundLabel: `${round}단계`,
      prompt: "기준값을 선택하세요.",
      correctIndex: i,
      text: "이번 단계의 기준 위치를 확인한다.",
    });

    for (let j = i + 1; j < values.length; j++) {
      actions.push({
        kind: "click",
        values: [...values],
        roundLabel: `${round}단계`,
        prompt: "비교할 값을 선택하세요.",
        correctIndex: j,
        text: "기준 위치 오른쪽에서 비교할 값을 선택한다.",
      });

      const nextMin = values[j] < values[min] ? j : min;
      actions.push({
        kind: "click",
        values: [...values],
        roundLabel: `${round}단계`,
        prompt: "최솟값을 선택하세요.",
        correctIndex: nextMin,
        text: "현재까지 확인한 값 중 가장 작은 값을 최솟값 후보로 선택한다.",
      });
      min = nextMin;
    }

    [values[i], values[min]] = [values[min], values[i]];
    actions.push({
      kind: "input",
      values: [...values],
      roundLabel: `${round}단계`,
      prompt: "교환 후 배열을 입력하세요.",
      swap: [i, min],
      fixed: [i],
      text: "찾은 최솟값을 기준 위치와 교환한 배열 상태를 입력한다.",
    });
    round += 1;
  }

  return actions;
}

function renderSelectionChoiceCells(action, rowIndex) {
  return action.values
    .map((value, index) => `<button class="selection-choice" type="button" data-selection-row="${rowIndex}" data-index="${index}" data-correct="${action.correctIndex}">${value}</button>`)
    .join("");
}

function hideAnswerText(text) {
  return text
    .replace(/교환 후 \[[^\]]+\]이 된다\./g, "교환 후 배열 상태를 가운데 칸에 입력한다.")
    .replace(/찾은 최솟값을 기준 위치와 교환하여 \[[^\]]+\]이 된다\./g, "찾은 최솟값을 기준 위치와 교환한 배열 상태를 입력한다.")
    .replace(/\[[^\]]+\] 순서로 정렬되어 실행을 종료한다\./g, "정렬된 배열 상태를 입력하고 실행을 종료한다.");
}

document.querySelectorAll(".problem-layout").forEach((problem) => {
  const type = problem.dataset.problem;
  const values = parseValues(problem.dataset.values);
  const target = problem.dataset.target ? Number(problem.dataset.target) : undefined;
  const steps = makeSteps(type, values, target);
  const isBinaryProblem = type === "binary";
  const isBubbleProblem = type === "bubble";
  const isSelectionProblem = type === "selection";
  const answerSteps = isSelectionProblem ? makeSelectionProblemActions(values) : isBubbleProblem ? makeBubbleProblemActions(values) : steps.slice(1);
  const groups = groupSteps(answerSteps, answerSteps.length - 1);
  const graphState = type === "binary" ? { range: values.map((_, index) => index) } : {};
  let sortRowIndex = 0;
  let sortExplainIndex = 0;
  let bubbleRowIndex = 0;
  let selectionRowIndex = 0;

  problem.innerHTML = `
    <article class="problem-card problem-source">
      <h2>${problem.dataset.title}</h2>
      <p class="data-line">데이터: ${values.join(", ")}${target !== undefined ? ` / 찾을 값: ${target}` : ""}</p>
      <div class="array-view"></div>
      <p class="practice-feedback" aria-live="polite"></p>
    </article>
    <article class="history-panel">
      <h2>단계</h2>
      <div class="history-list ${isBinaryProblem ? "binary-click-list" : ""} ${isBubbleProblem ? "bubble-click-list" : ""} ${isSelectionProblem ? "selection-click-list" : ""}">
        ${groups
          .map((group, groupIndex) => {
            const locked = isBinaryProblem && groupIndex > 0;
            return `
              <div class="history-group ${locked ? "locked" : ""}" data-binary-step="${groupIndex}">
                <span class="round-label">${group.label}</span>
                <div class="group-lines">
                  ${group.items
                    .map(({ step }) =>
                      isBinaryProblem
                        ? `
                        <div class="history-line binary-choice-row ${groupIndex === 0 ? "active" : ""}" data-binary-row="${groupIndex}" data-has-direction="${step.direction ? "true" : "false"}" data-correct-direction="${step.direction || ""}">
                          <p class="task-prompt">기준값을 선택하세요.</p>
                          <div class="step-boxes">${renderBinaryChoiceCells(step, groupIndex)}</div>
                        </div>
                      `
                        : isBubbleProblem
                          ? `
                        <div class="history-line bubble-task-row ${bubbleRowIndex === 0 ? "active" : "locked"} ${step.kind === "input" ? "bubble-input-row" : "bubble-pair-row"}" data-bubble-row="${bubbleRowIndex++}">
                          <p class="task-prompt">${step.prompt}</p>
                          <div class="step-boxes">${step.kind === "input" ? renderProblemCells(step) : renderBubbleChoiceCells(step, bubbleRowIndex - 1)}</div>
                        </div>
                      `
                        : isSelectionProblem
                          ? `
                        <div class="history-line selection-task-row ${selectionRowIndex === 0 ? "active" : "locked"} ${step.kind === "input" ? "selection-input-row" : "selection-click-row"}" data-selection-row="${selectionRowIndex++}">
                          <p class="task-prompt">${step.prompt}</p>
                          <div class="step-boxes">${step.kind === "input" ? renderProblemCells(step) : renderSelectionChoiceCells(step, selectionRowIndex - 1)}</div>
                        </div>
                      `
                        : `
                        <div class="history-line sort-answer-row ${sortRowIndex === 0 ? "active" : "locked"}" data-sort-row="${sortRowIndex++}">
                          <div class="step-boxes">${renderProblemCells(step)}</div>
                        </div>
                      `,
                    )
                    .join("")}
                </div>
              </div>
            `;
          })
          .join("")}
      </div>
    </article>
    <article class="explain-panel">
      <h2>설명</h2>
      <div class="explain-list ${isBinaryProblem ? "binary-explain-list" : isSelectionProblem ? "selection-explain-list" : "sort-explain-list"}">
        ${groups
          .map((group, groupIndex) => {
            const locked = isBinaryProblem && groupIndex > 0;
            return `
              <div class="explain-group ${isBinaryProblem ? "hidden-explain" : ""} ${locked ? "locked" : ""}" data-binary-explain="${groupIndex}">
                <span class="round-label">${group.label}</span>
                <div class="group-lines">
                  ${group.items
                    .map(({ step }) => {
                      const rowIndex = sortExplainIndex++;
                      return isBinaryProblem
                        ? renderBinaryExplainRow(step)
                        : `<div class="explain-row hidden-explain" data-sort-explain="${rowIndex}" data-bubble-explain="${rowIndex}" data-selection-explain="${rowIndex}">${hideAnswerText(step.text)}</div>`;
                    })
                    .join("")}
                </div>
              </div>
            `;
          })
          .join("")}
      </div>
    </article>
  `;

  renderArray(problem.querySelector(".array-view"), values, graphState);
});

document.querySelectorAll(".problem-layout[data-problem='bubble']").forEach((problem) => {
  let activeRow = 0;
  const rows = Array.from(problem.querySelectorAll(".bubble-task-row"));
  const explanations = Array.from(problem.querySelectorAll(".explain-row[data-bubble-explain]"));
  const feedback = problem.querySelector(".practice-feedback");
  const historyList = problem.querySelector(".history-list");
  const explainList = problem.querySelector(".explain-list");

  function setActiveRow(index) {
    activeRow = index;
    rows.forEach((row, rowIndex) => {
      row.classList.toggle("active", rowIndex === activeRow);
      row.classList.toggle("locked", rowIndex > activeRow);
      row.querySelectorAll("input").forEach((input) => {
        input.disabled = rowIndex > activeRow || row.classList.contains("correct-row");
      });
    });
    updateVisibleProblemRows(rows, explanations, activeRow, historyList, explainList);
  }

  function completeRow(row, rowIndex) {
    row.classList.add("correct-row");
    row.classList.remove("wrong-row");
    explanations[rowIndex].classList.remove("hidden-explain");
    syncScrollPosition(historyList, explainList);
    scrollPairToBottom(historyList, explainList);
    feedback.textContent = rowIndex === rows.length - 1 ? "모두 맞았습니다." : "맞았습니다. 다음 행을 풀어 보세요.";
    if (rowIndex < rows.length - 1) setActiveRow(rowIndex + 1);
  }

  function getBubblePairStart(button, row) {
    const choices = Array.from(row.querySelectorAll(".bubble-choice"));
    const index = Number(button.dataset.index);
    return Math.min(index, choices.length - 2);
  }

  function markBubblePair(row, pairStart, className) {
    row.querySelectorAll(".bubble-choice").forEach((choice) => {
      const index = Number(choice.dataset.index);
      choice.classList.toggle(className, index === pairStart || index === pairStart + 1);
    });
  }

  historyList.addEventListener("pointerover", (event) => {
    const button = event.target.closest(".bubble-choice");
    if (!button) return;

    const row = button.closest(".bubble-task-row");
    const rowIndex = Number(row.dataset.bubbleRow);
    if (rowIndex !== activeRow) return;

    row.querySelectorAll(".bubble-choice").forEach((choice) => choice.classList.remove("pair-preview"));
    markBubblePair(row, getBubblePairStart(button, row), "pair-preview");
  });

  historyList.addEventListener("pointerout", (event) => {
    const row = event.target.closest(".bubble-task-row");
    if (!row) return;
    row.querySelectorAll(".bubble-choice").forEach((choice) => choice.classList.remove("pair-preview"));
  });

  historyList.addEventListener("click", (event) => {
    const button = event.target.closest(".bubble-choice");
    if (!button) return;

    const row = button.closest(".bubble-task-row");
    const rowIndex = Number(row.dataset.bubbleRow);
    if (rowIndex !== activeRow) return;

    const pairStart = getBubblePairStart(button, row);
    const isCorrect = pairStart === Number(button.dataset.correctStart);
    row.querySelectorAll(".bubble-choice").forEach((choice) => choice.classList.remove("wrong-choice", "correct-choice", "pair-preview"));

    if (isCorrect) {
      markBubblePair(row, pairStart, "correct-choice");
      completeRow(row, rowIndex);
    } else {
      markBubblePair(row, pairStart, "wrong-choice");
      row.classList.add("wrong-row");
      explanations[rowIndex].classList.remove("hidden-explain");
      syncScrollPosition(historyList, explainList);
      scrollPairToBottom(historyList, explainList);
      feedback.textContent = "다시 확인하세요.";
    }
  });

  rows.forEach((row, rowIndex) => {
    const inputs = Array.from(row.querySelectorAll("input[data-answer]"));
    inputs.forEach((input) => {
      input.addEventListener("input", () => {
        row.classList.remove("wrong-row");
        feedback.textContent = "";
        if (rowIndex !== activeRow || inputs.some((item) => item.value.trim() === "")) return;

        const isCorrect = inputs.every((item) => normalizeNumericAnswer(item.value) === normalizeNumericAnswer(item.dataset.answer));
        explanations[rowIndex].classList.remove("hidden-explain");
        syncScrollPosition(historyList, explainList);

        if (isCorrect) {
          completeRow(row, rowIndex);
        } else {
          row.classList.add("wrong-row");
          scrollPairToBottom(historyList, explainList);
          feedback.textContent = "다시 확인하세요.";
        }
      });
    });
  });

  setActiveRow(0);
});

document.querySelectorAll(".selection-click-list").forEach((list) => {
  let activeRow = 0;
  const problem = list.closest(".problem-layout");
  const rows = Array.from(problem.querySelectorAll(".selection-task-row"));
  const explanations = Array.from(problem.querySelectorAll(".explain-row[data-selection-explain]"));
  const feedback = problem.querySelector(".practice-feedback");
  const historyList = problem.querySelector(".history-list");
  const explainList = problem.querySelector(".explain-list");

  function setActiveRow(index) {
    activeRow = index;
    rows.forEach((row, rowIndex) => {
      row.classList.toggle("active", rowIndex === activeRow);
      row.classList.toggle("locked", rowIndex > activeRow);
      row.querySelectorAll("input").forEach((input) => {
        input.disabled = rowIndex > activeRow || row.classList.contains("correct-row");
      });
    });
    updateVisibleProblemRows(rows, explanations, activeRow, historyList, explainList);
  }

  function completeRow(row, rowIndex) {
    row.classList.add("correct-row");
    row.classList.remove("wrong-row");
    explanations[rowIndex].classList.remove("hidden-explain");
    syncScrollPosition(historyList, explainList);
    scrollPairToBottom(historyList, explainList);
    feedback.textContent = rowIndex === rows.length - 1 ? "모두 맞았습니다." : "맞았습니다. 다음 행을 풀어 보세요.";
    if (rowIndex < rows.length - 1) setActiveRow(rowIndex + 1);
  }

  list.addEventListener("click", (event) => {
    const button = event.target.closest(".selection-choice");
    if (!button) return;

    const rowIndex = Number(button.dataset.selectionRow);
    if (rowIndex !== activeRow) return;

    const row = button.closest(".selection-task-row");
    row.querySelectorAll(".selection-choice").forEach((choice) => choice.classList.remove("wrong-choice"));

    if (button.dataset.index === button.dataset.correct) {
      button.classList.add("correct-choice");
      completeRow(row, rowIndex);
    } else {
      button.classList.add("wrong-choice");
      row.classList.add("wrong-row");
      feedback.textContent = "다시 확인하세요.";
      explanations[rowIndex].classList.remove("hidden-explain");
      syncScrollPosition(historyList, explainList);
      scrollPairToBottom(historyList, explainList);
    }
  });

  rows.forEach((row, rowIndex) => {
    const inputs = Array.from(row.querySelectorAll("input[data-answer]"));
    inputs.forEach((input) => {
      input.addEventListener("input", () => {
        row.classList.remove("wrong-row");
        feedback.textContent = "";
        if (rowIndex !== activeRow || inputs.some((item) => item.value.trim() === "")) return;

        const isCorrect = inputs.every((item) => normalizeNumericAnswer(item.value) === normalizeNumericAnswer(item.dataset.answer));
        explanations[rowIndex].classList.remove("hidden-explain");
        syncScrollPosition(list, explainList);

        if (isCorrect) {
          completeRow(row, rowIndex);
        } else {
          row.classList.add("wrong-row");
          scrollPairToBottom(historyList, explainList);
          feedback.textContent = "다시 확인하세요.";
        }
      });
    });
  });

  setActiveRow(0);
});

document.querySelectorAll(".binary-click-list").forEach((list) => {
  let activeStep = 0;
  let activePhase = "center";
  const problem = list.closest(".problem-layout");
  const rows = Array.from(problem.querySelectorAll(".binary-choice-row"));
  const groups = Array.from(problem.querySelectorAll(".history-group[data-binary-step]"));
  const explanations = Array.from(problem.querySelectorAll(".explain-group[data-binary-explain]"));
  const centerNotes = Array.from(problem.querySelectorAll(".binary-center-note"));
  const directionNotes = Array.from(problem.querySelectorAll(".binary-direction-note"));
  const explainList = problem.querySelector(".explain-list");
  const feedback = problem.querySelector(".practice-feedback");

  function setActiveStep(nextStep) {
    activeStep = nextStep;
    activePhase = "center";
    rows.forEach((row, index) => row.classList.toggle("active", index === activeStep));
    groups.forEach((group, index) => group.classList.toggle("locked", index > activeStep));
    const activeRow = rows[activeStep];
    if (activeRow) activeRow.querySelector(".task-prompt").textContent = "기준값을 선택하세요.";
  }

  list.addEventListener("click", (event) => {
    const button = event.target.closest(".binary-choice");
    if (!button) return;

    const step = Number(button.dataset.step);
    if (step !== activeStep || activePhase !== "center") return;
    if (button.classList.contains("out-cell")) {
      feedback.textContent = "현재 탐색 범위 안에서 선택하세요.";
      return;
    }

    const row = button.closest(".binary-choice-row");
    row.querySelectorAll(".binary-choice").forEach((choice) => choice.classList.remove("wrong-choice"));
    explanations[step].classList.remove("hidden-explain");
    centerNotes[step].classList.remove("hidden-explain");
    syncScrollPosition(list, explainList);

    if (button.dataset.index === button.dataset.correct) {
      button.classList.add("correct-choice");
      row.classList.add("mid-selected");
      feedback.textContent = "맞았습니다. 탐색할 숫자 묶음을 선택하세요.";
      if (row.dataset.hasDirection === "true") {
        activePhase = "direction";
        row.querySelector(".task-prompt").textContent = "탐색값과 중앙값을 비교하여 다음 탐색 범위를 선택하세요.";
      } else {
        directionNotes[step].classList.remove("hidden-explain");
        syncScrollPosition(list, explainList);
        row.classList.add("solved");
        feedback.textContent = activeStep === rows.length - 1 ? "모두 맞았습니다." : "맞았습니다. 다음 단계를 풀어 보세요.";
        if (activeStep < rows.length - 1) setActiveStep(activeStep + 1);
      }
    } else {
      button.classList.add("wrong-choice");
      feedback.textContent = "가운데값을 다시 확인하세요.";
    }
  });

  list.addEventListener("click", (event) => {
    const button = event.target.closest(".binary-choice");
    if (!button) return;

    const step = Number(button.dataset.step);
    if (step !== activeStep || activePhase !== "direction") return;
    if (button.classList.contains("out-cell")) {
      feedback.textContent = "현재 탐색 범위 안에서 선택하세요.";
      return;
    }

    const row = button.closest(".binary-choice-row");
    const selectedDirection = button.dataset.side;
    if (selectedDirection === "center") {
      feedback.textContent = "탐색값과 중앙값을 비교하여 다음 탐색 범위를 선택하세요.";
      return;
    }

    row.classList.remove("chosen-left", "chosen-right", "wrong-side-left", "wrong-side-right");
    explanations[step].classList.remove("hidden-explain");
    directionNotes[step].classList.remove("hidden-explain");
    syncScrollPosition(list, explainList);

    if (selectedDirection === row.dataset.correctDirection) {
      row.classList.add(`chosen-${selectedDirection}`);
      row.classList.add("solved");
      feedback.textContent = activeStep === rows.length - 1 ? "모두 맞았습니다." : "맞았습니다. 다음 단계를 풀어 보세요.";
      if (activeStep < rows.length - 1) setActiveStep(activeStep + 1);
    } else {
      row.classList.add(`wrong-side-${selectedDirection}`);
      feedback.textContent = "설명을 보고 방향을 다시 선택하세요.";
    }
  });

  list.addEventListener("pointerover", (event) => {
    const button = event.target.closest(".binary-choice");
    if (!button || Number(button.dataset.step) !== activeStep || activePhase !== "direction") return;
    if (button.classList.contains("out-cell")) return;
    const row = button.closest(".binary-choice-row");
    row.classList.toggle("preview-left", button.dataset.side === "left");
    row.classList.toggle("preview-right", button.dataset.side === "right");
  });

  list.addEventListener("pointerout", (event) => {
    const button = event.target.closest(".binary-choice");
    if (!button) return;
    const row = button.closest(".binary-choice-row");
    row.classList.remove("preview-left", "preview-right");
  });

  setActiveStep(0);
});

function normalizeNumericAnswer(value) {
  return value.trim().replace(/,/g, " ").replace(/\s+/g, " ");
}

document.querySelectorAll(".check-practice").forEach((button) => {
  button.addEventListener("click", () => {
    const card = button.closest(".practice-card, .binary-card, .problem-layout");
    const inputs = Array.from(card.querySelectorAll("input[data-answer]"));
    const isCorrect = inputs.every((input) => normalizeNumericAnswer(input.value) === normalizeNumericAnswer(input.dataset.answer));
    card.classList.toggle("correct", isCorrect);
    card.classList.toggle("incorrect", !isCorrect);
    card.querySelector(".practice-feedback").textContent = isCorrect ? "모두 맞았습니다." : "다시 확인하세요.";
  });
});
