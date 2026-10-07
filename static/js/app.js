import * as api from "./api.js";

const $ = (id) => document.getElementById(id);

const STATUS_LABELS = { scheduled: "Scheduled", completed: "Completed", cancelled: "Cancelled" };
const HEALTH_INTERVAL_MS = 15000;
const REFRESH_INTERVAL_MS = 30000;
const TOAST_MS = 3500;
const CONFIRM_RESET_MS = 3000;

const VIEWS = {
  overview: { stats: true, form: true, list: true },
  book: { stats: false, form: true, list: false },
  list: { stats: false, form: false, list: true },
};

let state = { appointments: [], doctors: [], view: "overview", statusFilter: "", freshId: null, loadFailed: false };
const setState = (patch) => { state = { ...state, ...patch }; };

// ---------- Small helpers ----------
function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

const pad = (n) => String(n).padStart(2, "0");
const localISODate = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
const slotDate = (a) => new Date(`${a.date}T${a.time}:00`);
const byTime = (a, b) => slotDate(a) - slotDate(b);
const plural = (n, word) => `${n} ${word}${n === 1 ? "" : "s"}`;

function formatDay(a) {
  return slotDate(a).toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short" });
}
function formatTime(a) {
  return slotDate(a).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
}
const specialtyOf = (doctorName) => state.doctors.find((d) => d.name === doctorName)?.specialty ?? "";

let toastTimer;
function toast(text, type) {
  const node = $("toast");
  node.textContent = text;
  node.className = `toast show ${type}`;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => node.classList.remove("show"), TOAST_MS);
}

// ---------- Derived data ----------
function computeStats(list) {
  const todayISO = localISODate(new Date());
  const counts = { scheduled: 0, completed: 0, cancelled: 0 };
  const perDoctor = new Map();
  list.forEach((a) => {
    counts[a.status] += 1;
    if (a.status === "scheduled") perDoctor.set(a.doctor, (perDoctor.get(a.doctor) ?? 0) + 1);
  });
  const now = new Date();
  const scheduled = list.filter((a) => a.status === "scheduled");
  return {
    counts,
    total: list.length,
    today: scheduled.filter((a) => a.date === todayISO).length,
    next: scheduled.filter((a) => slotDate(a) >= now).sort(byTime)[0] ?? null,
    busiest: [...perDoctor].sort((x, y) => y[1] - x[1])[0] ?? null,
  };
}

function visibleAppointments() {
  const q = $("search").value.trim().toLowerCase();
  const doctor = $("filter-doctor").value;
  return state.appointments
    .filter((a) => !doctor || a.doctor === doctor)
    .filter((a) => !state.statusFilter || a.status === state.statusFilter)
    .filter((a) => !q || [a.patient, a.doctor, a.date, a.time, a.status].join(" ").toLowerCase().includes(q))
    .sort(byTime);
}

// ---------- Rendering: hero + stats ----------
function renderHero(stats) {
  const hour = new Date().getHours();
  const greeting = hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening";
  $("page-title").replaceChildren(document.createTextNode(`${greeting}, `), el("em", "", "front desk."));
  $("today-label").textContent = new Date().toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "long" });
  $("page-sub").textContent = state.loadFailed
    ? "We couldn't reach the server. Check the API status and try again."
    : `${plural(stats.today, "appointment")} today and ${stats.counts.scheduled} scheduled overall. Book a visit or manage the day below.`;
}

function renderStats(stats) {
  $("stat-scheduled").textContent = stats.counts.scheduled;
  $("stat-today").textContent = stats.today ? `${stats.today} of them today` : "Nothing booked for today";
  $("stat-total").textContent = stats.total;
  $("nav-count").textContent = stats.counts.scheduled;

  if (stats.next) {
    $("next-name").textContent = stats.next.patient;
    $("next-meta").replaceChildren(
      el("span", "meta-chip", stats.next.doctor),
      el("span", "meta-chip", formatDay(stats.next)),
      el("span", "meta-chip", formatTime(stats.next)),
    );
  } else {
    $("next-name").textContent = "No upcoming visits";
    $("next-meta").replaceChildren();
  }

  $("stat-busy").textContent = stats.busiest ? stats.busiest[0] : "–";
  $("stat-busy-note").textContent = stats.busiest
    ? `${plural(stats.busiest[1], "appointment")} scheduled`
    : "No bookings yet";

  Object.entries(stats.counts).forEach(([status, count], i) => {
    $(`lg-${status}`).textContent = count;
    const seg = $("status-bar").children[i];
    seg.style.flexGrow = count;
    seg.hidden = count === 0;
  });
}

// ---------- Rendering: filters + list ----------
function renderChips() {
  const counts = { "": state.appointments.length };
  state.appointments.forEach((a) => { counts[a.status] = (counts[a.status] ?? 0) + 1; });
  const entries = [["", "All"], ...Object.entries(STATUS_LABELS)];
  $("status-chips").replaceChildren(...entries.map(([value, label]) => {
    const btn = el("button", "chip-btn", label);
    btn.type = "button";
    btn.dataset.status = value;
    btn.setAttribute("aria-pressed", String(state.statusFilter === value));
    btn.appendChild(el("span", "", counts[value] ?? 0));
    return btn;
  }));
}

function actionButton(label, action, id, extraClass = "") {
  const btn = el("button", `act ${extraClass}`.trim(), label);
  btn.type = "button";
  btn.dataset.action = action;
  btn.dataset.id = id;
  return btn;
}

function renderRow(a) {
  const li = el("li", `appt${a.id === state.freshId ? " fresh" : ""}`);
  li.dataset.status = a.status;

  const day = slotDate(a);
  const leaf = el("div", "leaf");
  leaf.append(el("small", "", day.toLocaleDateString(undefined, { month: "short" })), el("b", "", day.getDate()));

  const who = el("div", "who");
  const specialty = specialtyOf(a.doctor);
  who.append(
    el("b", "", a.patient),
    el("span", "", specialty ? `${a.doctor} · ${specialty}` : a.doctor),
    el("span", "when", `${formatDay(a)} · ${formatTime(a)}`),
  );

  const actions = el("div", "row-actions");
  if (a.status === "scheduled") {
    actions.append(actionButton("Complete", "completed", a.id), actionButton("Cancel", "cancelled", a.id));
  } else {
    actions.append(actionButton("Reopen", "scheduled", a.id));
  }
  actions.append(actionButton("Delete", "delete", a.id, "danger"));

  li.append(leaf, who, el("span", `status ${a.status}`, STATUS_LABELS[a.status]), actions);
  return li;
}

function emptyState() {
  const li = el("li", "empty");
  const filtered = state.appointments.length > 0;
  li.append(
    el("strong", "", filtered ? "No matching appointments" : "No appointments yet"),
    document.createTextNode(filtered ? "Try a different search or filter." : "Book the first visit using the form."),
  );
  return li;
}

function renderList() {
  const rows = visibleAppointments();
  $("appointments").replaceChildren(...(rows.length ? rows.map(renderRow) : [emptyState()]));
  $("list-sub").textContent = `Showing ${rows.length} of ${plural(state.appointments.length, "appointment")}.`;
  setState({ freshId: null });
}

function renderAll() {
  const stats = computeStats(state.appointments);
  renderHero(stats);
  renderStats(stats);
  renderChips();
  renderList();
}

// ---------- Doctors ----------
function renderDoctors() {
  $("doctor-picker").replaceChildren(...state.doctors.map((doctor, i) => {
    const label = el("label", "doctor-option");
    const input = el("input");
    Object.assign(input, { type: "radio", name: "doctor", value: doctor.name, required: true });
    if (i === 0) input.setAttribute("checked", "");
    const card = el("span");
    card.append(el("b", "", doctor.name), el("small", "", doctor.specialty));
    label.append(input, card);
    return label;
  }));

  $("filter-doctor").replaceChildren(
    new Option("All doctors", ""),
    ...state.doctors.map((d) => new Option(d.name, d.name)),
  );
}

// ---------- Data loading ----------
let refreshSeq = 0;
async function refresh({ quiet = false } = {}) {
  const seq = ++refreshSeq;
  try {
    const appointments = await api.listAppointments();
    if (seq !== refreshSeq) return; // a newer refresh superseded this response
    setState({ appointments, loadFailed: false });
  } catch (err) {
    if (seq !== refreshSeq) return;
    setState({ loadFailed: true });
    if (!quiet) toast("Could not load appointments.", "error");
  }
  renderAll();
}

async function init() {
  try {
    setState({ doctors: await api.listDoctors() });
  } catch (err) {
    toast("Could not load the doctor list.", "error");
  }
  renderDoctors();
  await refresh();
}

// ---------- Booking form ----------
function readForm() {
  return {
    patient: $("patient").value.trim(),
    doctor: document.querySelector('input[name="doctor"]:checked')?.value ?? "",
    date: $("date").value,
    time: $("time").value,
  };
}

async function submitBooking(event) {
  event.preventDefault();
  const button = $("submit-btn");
  const errorBox = $("form-error");
  const appointment = readForm();
  errorBox.textContent = "";

  if (Object.values(appointment).some((value) => !value)) {
    errorBox.textContent = "Please fill in the patient name, doctor, date and time.";
    return;
  }

  button.disabled = true;
  try {
    const created = await api.bookAppointment(appointment);
    setState({ freshId: created.id });
    toast(`Booked ${created.patient} with ${created.doctor}.`, "success");
    event.target.reset();
    await refresh();
  } catch (err) {
    errorBox.textContent = err.message;
    toast(err.message, "error");
  } finally {
    button.disabled = false;
  }
}

// ---------- Row actions (event delegation) ----------
function armDeleteConfirmation(button) {
  button.dataset.armed = "true";
  button.textContent = "Sure?";
  setTimeout(() => {
    if (!button.isConnected) return;
    delete button.dataset.armed;
    button.textContent = "Delete";
  }, CONFIRM_RESET_MS);
}

async function handleRowAction(event) {
  const button = event.target.closest("button[data-action]");
  if (!button) return;
  const { action, id } = button.dataset;

  if (action === "delete" && !button.dataset.armed) {
    armDeleteConfirmation(button);
    return;
  }

  button.disabled = true;
  try {
    if (action === "delete") {
      await api.removeAppointment(id);
      toast("Appointment deleted.", "success");
    } else {
      await api.setStatus(id, action);
      toast(`Marked as ${STATUS_LABELS[action].toLowerCase()}.`, "success");
    }
    await refresh();
  } catch (err) {
    button.disabled = false;
    toast(err.message, "error");
  }
}

// ---------- Navigation, theme, health ----------
function showView(name) {
  const view = VIEWS[name];
  setState({ view: name });
  document.querySelectorAll(".nav button").forEach((b) => {
    if (b.dataset.view === name) b.setAttribute("aria-current", "page");
    else b.removeAttribute("aria-current");
  });
  $("stats").hidden = !view.stats;
  $("book-panel").hidden = !view.form;
  $("list-panel").hidden = !view.list;
  $("workspace").className = `workspace${view.form && !view.list ? " only-form" : ""}${view.list && !view.form ? " only-list" : ""}`;
}

function syncThemeButton() {
  const dark = document.documentElement.dataset.theme === "dark";
  $("theme-toggle").setAttribute("aria-label", dark ? "Switch to light theme" : "Switch to dark theme");
}

function toggleTheme() {
  const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
  document.documentElement.dataset.theme = next;
  try { localStorage.setItem("medibook-theme", next); } catch (err) { /* storage blocked */ }
  syncThemeButton();
}

async function pollHealth() {
  const { up, ms } = await api.checkHealth();
  $("api-pill").dataset.state = up ? "up" : "down";
  $("api-label").textContent = up ? "API operational" : "API down";
  $("api-ms").textContent = up ? `${ms} ms` : "";
}

function bindEvents() {
  document.querySelectorAll(".nav button").forEach((b) => b.addEventListener("click", () => showView(b.dataset.view)));
  $("booking-form").addEventListener("submit", submitBooking);
  $("booking-form").addEventListener("reset", () => { $("form-error").textContent = ""; });
  $("appointments").addEventListener("click", handleRowAction);
  $("search").addEventListener("input", renderList);
  $("filter-doctor").addEventListener("change", renderList);
  $("status-chips").addEventListener("click", (event) => {
    const chip = event.target.closest("button[data-status]");
    if (!chip) return;
    setState({ statusFilter: chip.dataset.status });
    renderChips();
    renderList();
  });
  $("theme-toggle").addEventListener("click", toggleTheme);
}

$("date").min = localISODate(new Date());
syncThemeButton();
bindEvents();
init();
pollHealth();
setInterval(pollHealth, HEALTH_INTERVAL_MS);
setInterval(() => refresh({ quiet: true }), REFRESH_INTERVAL_MS);
