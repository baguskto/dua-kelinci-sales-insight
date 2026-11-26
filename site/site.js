// Respect reduced motion: keep the poster, do not play the videos.
if (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
  document.querySelectorAll("video").forEach((v) => { v.removeAttribute("autoplay"); v.pause(); v.controls = true; });
}
