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

  slides.forEach((slide, slideIndex) => {
    slide.classList.toggle("active", slideIndex === activeIndex);
  });

  dotButtons.forEach((dot, dotIndex) => {
    dot.classList.toggle("active", dotIndex === activeIndex);
  });

  currentSlide.textContent = String(activeIndex + 1);
}

function nextSlide() {
  showSlide(activeIndex + 1);
}

function prevSlide() {
  showSlide(activeIndex - 1);
}

prevButton.addEventListener("click", prevSlide);
nextButton.addEventListener("click", nextSlide);

document.addEventListener("keydown", (event) => {
  if (event.target.matches("input, textarea")) {
    return;
  }

  if (event.key === "ArrowRight" || event.key === " ") {
    nextSlide();
  }

  if (event.key === "ArrowLeft") {
    prevSlide();
  }
});

const requestedSlide = Number(new URLSearchParams(window.location.search).get("slide"));
showSlide(Number.isInteger(requestedSlide) && requestedSlide > 0 ? requestedSlide - 1 : 0);

document.querySelectorAll(".simulation-layout").forEach((simulation) => {
  const steps = Array.from(simulation.querySelectorAll(".sim-steps li"));
  const prev = simulation.querySelector('[data-action="prev"]');
  const next = simulation.querySelector('[data-action="next"]');
  let stepIndex = 0;

  function renderStep() {
    simulation.dataset.step = String(stepIndex + 1);
    steps.forEach((step, index) => {
      step.classList.toggle("active", index === stepIndex);
    });
  }

  prev.addEventListener("click", () => {
    stepIndex = Math.max(0, stepIndex - 1);
    renderStep();
  });

  next.addEventListener("click", () => {
    stepIndex = Math.min(steps.length - 1, stepIndex + 1);
    renderStep();
  });

  renderStep();
});

function normalizeAnswer(value) {
  return value
    .trim()
    .toUpperCase()
    .replace(/\s*,\s*/g, ",")
    .replace(/\(\s*/g, "(")
    .replace(/\s*\)/g, ")")
    .replace(/\s+/g, "");
}

document.querySelectorAll(".quiz-layout").forEach((quiz) => {
  const button = quiz.querySelector(".check-quiz");
  const inputs = Array.from(quiz.querySelectorAll("input[data-answer]"));

  button.addEventListener("click", () => {
    inputs.forEach((input) => {
      const card = input.closest(".quiz-card");
      const feedback = card.querySelector(".quiz-feedback");
      const expected = normalizeAnswer(input.dataset.answer);
      const actual = normalizeAnswer(input.value);
      const isCorrect = actual === expected;

      card.classList.toggle("correct", isCorrect);
      card.classList.toggle("incorrect", !isCorrect);
      feedback.textContent = isCorrect ? "정답" : "다시 확인";
    });
  });
});
