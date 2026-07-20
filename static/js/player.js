const audioEl = document.getElementById("audioEl");
const playPauseBtn = document.getElementById("playPauseBtn");
const iconPlay = document.getElementById("iconPlay");
const iconPause = document.getElementById("iconPause");
const seekBar = document.getElementById("seekBar");
const curTimeEl = document.getElementById("curTime");
const durTimeEl = document.getElementById("durTime");
const playerTitle = document.getElementById("playerTitle");
const playerArtist = document.getElementById("playerArtist");
const playerCover = document.getElementById("playerCover");

let currentSongId = null;
let playCounted = false;

function fmtTime(sec) {
  if (!isFinite(sec) || sec < 0) sec = 0;
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60).toString().padStart(2, "0");
  return `${m}:${s}`;
}

function playTrack(el) {
  const src = el.dataset.src;
  const title = el.dataset.title;
  const artist = el.dataset.artist;
  const cover = el.dataset.cover || "";
  const id = el.dataset.id;

  if (currentSongId === id && !audioEl.paused) {
    audioEl.pause();
    return;
  }
  if (currentSongId === id && audioEl.paused && audioEl.src.endsWith(src)) {
    audioEl.play();
    return;
  }

  currentSongId = id;
  playCounted = false;
  audioEl.src = src;
  playerTitle.textContent = title;
  playerArtist.textContent = artist;
  playerCover.style.backgroundImage = cover ? `url(${cover})` : "none";
  audioEl.play();
}

playPauseBtn.addEventListener("click", () => {
  if (!audioEl.src) return;
  if (audioEl.paused) audioEl.play();
  else audioEl.pause();
});

audioEl.addEventListener("play", () => {
  iconPlay.style.display = "none";
  iconPause.style.display = "block";
});
audioEl.addEventListener("pause", () => {
  iconPlay.style.display = "block";
  iconPause.style.display = "none";
});
audioEl.addEventListener("timeupdate", () => {
  if (audioEl.duration) {
    seekBar.value = (audioEl.currentTime / audioEl.duration) * 100;
    curTimeEl.textContent = fmtTime(audioEl.currentTime);
    durTimeEl.textContent = fmtTime(audioEl.duration);
  }
  if (!playCounted && audioEl.currentTime > 3 && currentSongId) {
    playCounted = true;
    fetch(`/song/${currentSongId}/play`, { method: "POST" });
  }
});
seekBar.addEventListener("input", () => {
  if (audioEl.duration) {
    audioEl.currentTime = (seekBar.value / 100) * audioEl.duration;
  }
});

document.addEventListener("click", (e) => {
  const trigger = e.target.closest(".play-trigger");
  if (trigger) {
    e.preventDefault();
    playTrack(trigger);
  }

  const pp = e.target.closest(".playlist-picker-toggle");
  if (pp) {
    e.preventDefault();
    const wrap = pp.closest(".playlist-picker");
    document.querySelectorAll(".playlist-picker.open").forEach(o => { if (o !== wrap) o.classList.remove("open"); });
    wrap.classList.toggle("open");
  } else if (!e.target.closest(".playlist-picker-menu")) {
    document.querySelectorAll(".playlist-picker.open").forEach(o => o.classList.remove("open"));
  }

  const likeBtn = e.target.closest(".like-btn");
  if (likeBtn) {
    e.preventDefault();
    const songId = likeBtn.dataset.id;
    fetch(`/song/${songId}/like`, { method: "POST" })
      .then(r => {
        if (r.status === 302 || r.redirected) { window.location.href = "/login"; return null; }
        return r.json();
      })
      .then(data => {
        if (!data) return;
        likeBtn.classList.toggle("liked", data.liked);
        const countEl = likeBtn.querySelector(".like-count");
        if (countEl) countEl.textContent = data.count;
      });
  }
});
