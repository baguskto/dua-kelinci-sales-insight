// Capture-only motion layer for the README GIFs and the Pages videos. Injected by motion.py into a
// running dashboard; the app itself ships no entrance animation (DESIGN.md: MOTION 1).
// Every animation is created paused; window.__seek(ms) sets the time, so each frame is deterministic.
(function () {
  const EASE_OUT = "cubic-bezier(.22,.61,.36,1)";
  const EASE_IO = "cubic-bezier(.65,0,.35,1)";
  const anims = [];
  const add = (el, frames, opts) => { const a = el.animate(frames, Object.assign({ fill: "both" }, opts)); a.pause(); anims.push(a); };
  const cards = [...document.querySelectorAll(".page .card")];
  const head = document.querySelector(".hd");
  const foot = document.querySelector(".foot");

  function stagger() {
    // Cards fade in and rise 8px, 90 ms apart; hold; everything fades out; loop.
    const total = 5200;
    const end = 4500;
    [head, ...cards, foot].forEach((el, i) => {
      const start = i === 0 ? 0 : 120 + (i - 1) * 90;
      add(el, [
        { opacity: 0, transform: "translateY(8px)", offset: 0 },
        { opacity: 0, transform: "translateY(8px)", offset: start / total, easing: EASE_OUT },
        { opacity: 1, transform: "translateY(0)", offset: (start + 420) / total },
        { opacity: 1, transform: "translateY(0)", offset: end / total, easing: EASE_IO },
        { opacity: 0, transform: "translateY(0)", offset: (end + 350) / total },
        { opacity: 0, transform: "translateY(0)", offset: 1 },
      ], { duration: total, easing: "linear" });
    });
    return total;
  }

  function isometric() {
    // The dashboard lies flat as an isometric plane, stands up into a tilted view, then the four
    // cards that tell the story lift off the plane; hold; settle back; loop.
    const total = 6400;
    document.documentElement.classList.add("iso");
    const page = document.querySelector(".page");
    const flat = "translate(0, -9%) scale(.64) rotateX(60deg) rotateZ(-45deg)";
    const tilt = "translate(0, -8%) scale(.7) rotateX(40deg) rotateZ(-26deg)";
    add(page, [
      { transform: flat, offset: 0 },
      { transform: flat, offset: 300 / total, easing: EASE_IO },
      { transform: tilt, offset: 1500 / total },
      { transform: tilt, offset: 5200 / total, easing: EASE_IO },
      { transform: flat, offset: 6200 / total },
      { transform: flat, offset: 1 },
    ], { duration: total, easing: "linear" });
    const keyCards = [".c-ex", ".c-wf", ".c-top", ".c-map"].map((s) => document.querySelector(s));
    keyCards.forEach((el, i) => {
      const s = 1600 + i * 160;
      const down = { transform: "translateZ(0)", boxShadow: "0 0 0 rgba(24,24,27,0)" };
      const up = { transform: "translateZ(56px)", boxShadow: "0 26px 40px -10px rgba(24,24,27,.28)" };
      add(el, [
        Object.assign({ offset: 0 }, down),
        Object.assign({ offset: s / total, easing: EASE_OUT }, down),
        Object.assign({ offset: (s + 520) / total }, up),
        Object.assign({ offset: 4900 / total, easing: EASE_IO }, up),
        Object.assign({ offset: 5400 / total }, down),
        Object.assign({ offset: 1 }, down),
      ], { duration: total, easing: "linear" });
    });
    return total;
  }

  window.__setup = (mode) => (mode === "isometric-lift" ? isometric() : stagger());
  window.__seek = (ms) => anims.forEach((a) => { a.currentTime = ms; });
})();
