/*
 * 인공지능 기초 수업 슬라이드 — 공통 내비게이션
 * 기준: ai/DESIGN_GUIDE.md (ch2-2/script.js와 동작 동일)
 *
 * - 1920×1080 캔버스를 화면 크기에 맞춰 축소
 * - 좌우 가장자리 버튼, 하단 점, 키보드(→·Space 다음, ← 이전)
 * - 주소의 ?slide=3 으로 해당 슬라이드 열기
 *
 * 필요한 마크업: .deck > .slide, .nav-prev, .nav-next, .dots, #currentSlide, #totalSlides
 */
(function () {
  "use strict";

  const DESIGN_WIDTH = 1920;
  const DESIGN_HEIGHT = 1080;

  function init() {
    const deck = document.querySelector(".deck");
    const slides = Array.from(document.querySelectorAll(".slide"));
    if (!deck || slides.length === 0) return;

    const prevButton = document.querySelector(".nav-prev");
    const nextButton = document.querySelector(".nav-next");
    const currentSlide = document.querySelector("#currentSlide");
    const totalSlides = document.querySelector("#totalSlides");
    const dots = document.querySelector(".dots");

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
    const dotButtons = [];

    if (dots) {
      slides.forEach((_, index) => {
        const dot = document.createElement("button");
        dot.className = "dot";
        dot.type = "button";
        dot.setAttribute("aria-label", `${index + 1}번 슬라이드로 이동`);
        dot.addEventListener("click", () => showSlide(index));
        dots.append(dot);
        dotButtons.push(dot);
      });
    }

    if (totalSlides) totalSlides.textContent = String(slides.length);

    function showSlide(index) {
      activeIndex = (index + slides.length) % slides.length;

      slides.forEach((slide, slideIndex) => {
        slide.classList.toggle("active", slideIndex === activeIndex);
      });

      dotButtons.forEach((dot, dotIndex) => {
        dot.classList.toggle("active", dotIndex === activeIndex);
      });

      if (currentSlide) currentSlide.textContent = String(activeIndex + 1);

      const url = new URL(window.location.href);
      url.searchParams.set("slide", String(activeIndex + 1));
      window.history.replaceState(null, "", url);
    }

    function nextSlide() {
      showSlide(activeIndex + 1);
    }

    function prevSlide() {
      showSlide(activeIndex - 1);
    }

    if (prevButton) prevButton.addEventListener("click", prevSlide);
    if (nextButton) nextButton.addEventListener("click", nextSlide);

    document.addEventListener("keydown", (event) => {
      if (event.target.matches("input, textarea, select, [contenteditable]")) return;
      if (event.key === "ArrowRight" || event.key === " ") {
        event.preventDefault();
        nextSlide();
      }
      if (event.key === "ArrowLeft") prevSlide();
    });

    const requested = Number(new URLSearchParams(window.location.search).get("slide"));
    showSlide(Number.isInteger(requested) && requested > 0 ? requested - 1 : 0);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
