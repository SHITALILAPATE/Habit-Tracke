const QUOTES = [
  "Small steps every day.",
  "Discipline equals freedom.",
  "You don't have to be extreme, just consistent.",
  "Tiny changes, remarkable results.",
  "Motivation gets you started. Habit keeps you going.",
  "We are what we repeatedly do.",
  "Win the morning, win the day.",
  "Progress, not perfection.",
];

const $ = (s) => document.querySelector(s);
const habitList = $("#habitList");
const progressFill = $("#progressFill");
const progressText = $("#progressText");
const doneCount = $("#doneCount");
const totalCount = $("#totalCount");
const bestStreak = $("#bestStreak");
const emptyHint = $("#emptyHint");

let lastProgress = 0;

function setTheme(t) {
  document.documentElement.setAttribute("data-theme", t);
  localStorage.setItem("theme", t);
}
setTheme(localStorage.getItem("theme") || "dark");
$("#themeToggle").addEventListener("click", () => {
  const cur = document.documentElement.getAttribute("data-theme");
  setTheme(cur === "dark" ? "light" : "dark");
});

$("#quoteText").textContent = `"${QUOTES[Math.floor(Math.random() * QUOTES.length)]}"`;

async function api(url, opts = {}) {
  const res = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...opts,
  });
  if (res.status === 401) { window.location.href = "/login"; return; }
  return res.json();
}

function playDing() {
  const a = $("#dingSound");
  try { a.currentTime = 0; a.volume = 0.4; a.play().catch(() => {}); } catch (e) {}
}

function fireConfetti() {
  if (!window.confetti) return;
  const end = Date.now() + 800;
  (function frame() {
    confetti({ particleCount: 4, angle: 60, spread: 70, origin: { x: 0 }, colors: ["#22c55e", "#16a34a", "#a7f3d0"] });
    confetti({ particleCount: 4, angle: 120, spread: 70, origin: { x: 1 }, colors: ["#22c55e", "#16a34a", "#a7f3d0"] });
    if (Date.now() < end) requestAnimationFrame(frame);
  })();
}

function renderHabit(h) {
  const li = document.createElement("li");
  li.className = "habit-card" + (h.completed_today ? " done" : "");
  li.dataset.id = h.id;
  li.innerHTML = `
    <div class="head">
      <span class="emoji">${h.emoji || "🌱"}</span>
      <span class="name"></span>
      <button class="delete" title="Delete">✕</button>
    </div>
    <div class="meta">
      <span class="streak">🔥 <span class="cs">${h.current_streak}</span> day streak</span>
      <span>Best: ${h.best_streak}</span>
    </div>
    <button class="toggle">${h.completed_today ? "✓ Completed today" : "Mark as done"}</button>
  `;
  li.querySelector(".name").textContent = h.name;
  li.querySelector(".delete").addEventListener("click", () => deleteHabit(h.id));
  li.querySelector(".toggle").addEventListener("click", () => toggleHabit(h.id));
  return li;
}

function updateStats(stats, habits) {
  doneCount.textContent = stats.completed_today;
  totalCount.textContent = stats.total;
  progressFill.style.width = stats.progress + "%";
  progressText.textContent = stats.progress + "%";
  bestStreak.textContent = habits.reduce((m, h) => Math.max(m, h.best_streak), 0);
  emptyHint.hidden = stats.total > 0;

  if (stats.total > 0 && stats.progress === 100 && lastProgress < 100) {
    fireConfetti();
  }
  lastProgress = stats.progress;
}

async function loadHabits() {
  const data = await api("/api/habits");
  if (!data) return;
  habitList.innerHTML = "";
  data.habits.forEach((h) => habitList.appendChild(renderHabit(h)));
  updateStats(data.stats, data.habits);
}

async function toggleHabit(id) {
  const data = await api(`/api/habits/${id}/toggle`, { method: "POST" });
  if (!data) return;
  if (data.completed_today) playDing();
  await loadHabits();
}

async function deleteHabit(id) {
  if (!confirm("Delete this habit?")) return;
  await api(`/api/habits/${id}`, { method: "DELETE" });
  await loadHabits();
}

$("#habitForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const name = $("#nameInput").value.trim();
  const emoji = $("#emojiInput").value.trim() || "🌱";
  if (!name) return;
  const res = await api("/api/habits", { method: "POST", body: JSON.stringify({ name, emoji }) });
  if (res && res.id) {
    $("#nameInput").value = "";
    $("#emojiInput").value = "";
    await loadHabits();
  }
});

loadHabits();
