const pct = (x) => (x * 100).toFixed(1) + "%";
const el = (tag, cls, html) => {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (html != null) n.innerHTML = html;
  return n;
};

function animateCount(node, target, opts = {}) {
  const { decimals = 0, suffix = "", duration = 1100 } = opts;
  const start = performance.now();
  function frame(now) {
    const t = Math.min((now - start) / duration, 1);
    const eased = 1 - Math.pow(1 - t, 3);
    node.textContent = (target * eased).toFixed(decimals) + suffix;
    if (t < 1) requestAnimationFrame(frame);
    else node.textContent = target.toFixed(decimals) + suffix;
  }
  requestAnimationFrame(frame);
}

function renderHero(s) {
  const wrap = document.getElementById("heroStats");
  const items = [
    { num: s.outcome_accuracy * 100, cls: "gold", lbl: "Outcome accuracy", dec: 1, suf: "%" },
    { num: s.exact_rate * 100, cls: "g", lbl: "Exact scoreline rate", dec: 1, suf: "%" },
    { num: s.exact, cls: "b", lbl: "Exact scorelines", dec: 0 },
    { num: s.matches_scored, cls: "p", lbl: "Matches graded", dec: 0 },
  ];
  items.forEach((it) => {
    const card = el("div", "hstat");
    const num = el("div", `num ${it.cls}`, "0");
    card.appendChild(num);
    card.appendChild(el("div", "lbl", it.lbl));
    wrap.appendChild(card);
    animateCount(num, it.num, { decimals: it.dec, suffix: it.suf || "" });
  });
}

function renderScoreCards(s) {
  const wrap = document.getElementById("scoreCards");
  const cards = [
    {
      big: pct(s.outcome_accuracy),
      cap: "Correct outcomes",
      sub: `${s.exact + s.direction_only} of ${s.matches_scored} results called right`,
      bar: s.outcome_accuracy,
    },
    {
      big: pct(s.exact_rate),
      cap: "Exact scorelines",
      sub: `${s.exact} perfect predictions on the nose`,
      bar: s.exact_rate,
    },
    {
      big: `${s.exact}<span style="font-size:1.2rem;color:var(--faint)"> / ${s.miss}</span>`,
      cap: "Bullseyes vs misses",
      sub: `${s.direction_only} right on the outcome only`,
      bar: s.matches_scored ? (s.exact + s.direction_only) / s.matches_scored : 0,
    },
    {
      big: `${s.pending}`,
      cap: "Awaiting kickoff",
      sub: `${s.futures_open} futures bets still open`,
      bar: null,
    },
  ];
  cards.forEach((c) => {
    const card = el("div", "card");
    card.appendChild(el("div", "big", c.big));
    card.appendChild(el("div", "cap", c.cap));
    card.appendChild(el("div", "sub", c.sub));
    if (c.bar != null) {
      const bar = el("div", "bar");
      const span = el("span");
      span.style.width = "0%";
      bar.appendChild(span);
      card.appendChild(bar);
      setTimeout(() => (span.style.width = pct(c.bar)), 200);
    }
    wrap.appendChild(card);
  });
}

const HIT_LABEL = { exact: "Exact", dir: "Outcome", miss: "Miss", pending: "Pending" };

function predRow(p) {
  const tr = el("tr");
  tr.appendChild(el("td", "rnd", p.round));
  tr.appendChild(el("td", "team ta-r", `${p.home} <span class="flag">${p.home_flag}</span>`));
  tr.appendChild(
    el("td", "ta-c", `<span class="pick">${p.pred_home}–${p.pred_away}</span>`)
  );
  tr.appendChild(el("td", "team ta-l", `<span class="flag">${p.away_flag}</span> ${p.away}`));

  if (p.status === "pending") {
    tr.appendChild(el("td", "ta-c", `<span class="badge b-pending">TBD</span>`));
  } else {
    const cls = p.hit;
    tr.appendChild(
      el(
        "td",
        "ta-c",
        `<span class="score">${p.actual_home}–${p.actual_away}</span>
         <div class="badge b-${cls}" style="margin-top:5px">${HIT_LABEL[cls]}</div>`
      )
    );
  }
  return tr;
}

let ALL_PREDS = [];
function renderTable(filter) {
  const body = document.getElementById("predBody");
  body.innerHTML = "";
  const list = ALL_PREDS.filter((p) => {
    if (filter === "all") return true;
    if (filter === "exact") return p.hit === "exact";
    if (filter === "pending") return p.status === "pending";
    return p.stage === filter;
  });
  list.forEach((p) => body.appendChild(predRow(p)));
  if (!list.length) body.appendChild(el("tr", null, `<td colspan="5" style="text-align:center;color:var(--faint);padding:30px">No matches in this view.</td>`));
}

function renderFilters(preds) {
  const wrap = document.getElementById("filters");
  const stages = [...new Set(preds.map((p) => p.stage))];
  const stageLabel = { group: "Group", r32: "Round of 32", r16: "Round of 16", qf: "Quarters", sf: "Semis", final: "Final" };
  const defs = [
    { key: "all", label: "All" },
    ...stages.map((s) => ({ key: s, label: stageLabel[s] || s })),
    { key: "exact", label: "★ Exact hits" },
    { key: "pending", label: "Upcoming" },
  ];
  defs.forEach((d, i) => {
    const chip = el("button", "chip" + (i === 0 ? " active" : ""), d.label);
    chip.onclick = () => {
      wrap.querySelectorAll(".chip").forEach((c) => c.classList.remove("active"));
      chip.classList.add("active");
      renderTable(d.key);
    };
    wrap.appendChild(chip);
  });
}

function renderFutures(futures) {
  const wrap = document.getElementById("futures");
  const icons = { champion: "🏆", golden_boot: "⚽" };
  futures.forEach((f) => {
    const card = el("div", "future");
    card.appendChild(el("div", "ic", icons[f.kind] || "◆"));
    const info = el("div");
    info.appendChild(el("div", "lbl", f.label));
    info.appendChild(el("div", "pk", `<span class="flag">${f.flag}</span> ${f.pick}`));
    info.appendChild(el("div", "mp", f.status === "pending" ? "Locked at kickoff · still live" : f.status));
    card.appendChild(info);
    wrap.appendChild(card);
  });
}

function renderRace(odds) {
  const wrap = document.getElementById("race");
  const max = odds[0]?.title || 1;
  odds.forEach((o) => {
    const row = el("div", "rrow");
    row.appendChild(el("div", "rteam", `<span class="flag">${o.flag}</span> ${o.team}`));
    const bar = el("div", "rbar");
    const span = el("span");
    span.style.width = "0%";
    bar.appendChild(span);
    row.appendChild(bar);
    row.appendChild(el("div", "rpct", pct(o.title)));
    wrap.appendChild(row);
    setTimeout(() => (span.style.width = (o.title / max) * 100 + "%"), 250);
  });
}

function renderTrend(timeline) {
  const host = document.getElementById("trendChart");
  if (!timeline || timeline.length === 0) return;
  const W = 720, H = 300, padX = 46, padY = 34;
  const n = timeline.length;
  const xs = (i) => padX + (i * (W - 2 * padX)) / Math.max(n - 1, 1);
  const ys = (v) => H - padY - v * (H - 2 * padY);
  const line = (key) =>
    timeline.map((t, i) => `${i ? "L" : "M"}${xs(i).toFixed(1)},${ys(t[key]).toFixed(1)}`).join(" ");
  const area = `${line("cum_accuracy")} L${xs(n - 1)},${H - padY} L${xs(0)},${H - padY} Z`;

  const grid = [0, 0.25, 0.5, 0.75, 1]
    .map((g) => `<line x1="${padX}" y1="${ys(g)}" x2="${W - padX}" y2="${ys(g)}" class="grid"/>
      <text x="${padX - 10}" y="${ys(g) + 4}" class="axis" text-anchor="end">${g * 100}%</text>`)
    .join("");
  const xlabels = timeline
    .map((t, i) => `<text x="${xs(i)}" y="${H - 8}" class="axis" text-anchor="middle">${t.round.replace("Group · ", "")}</text>`)
    .join("");
  const dots = (key, cls) =>
    timeline.map((t, i) => `<circle cx="${xs(i)}" cy="${ys(t[key])}" r="4.5" class="${cls}"/>
      <text x="${xs(i)}" y="${ys(t[key]) - 12}" class="pt-lbl" text-anchor="middle">${(t[key] * 100).toFixed(0)}%</text>`).join("");

  host.innerHTML = `
    <svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="xMidYMid meet" role="img" aria-label="Accuracy over time">
      <defs>
        <linearGradient id="fillCum" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="var(--grad-1)" stop-opacity="0.35"/>
          <stop offset="100%" stop-color="var(--grad-1)" stop-opacity="0"/>
        </linearGradient>
      </defs>
      ${grid}
      <path d="${area}" fill="url(#fillCum)" stroke="none"/>
      <path d="${line("cum_accuracy")}" class="l-eff" fill="none"/>
      <path d="${line("accuracy")}" class="l-acc" fill="none"/>
      ${dots("accuracy", "d-acc")}
      ${xlabels}
    </svg>`;
}

const METHODS = [
  { ic: "📊", name: "Elo backbone", body: "Opponent-adjusted team strength on the eloratings.net scale. Goal difference scales the K-factor, so a 4–0 moves more than a 1–0, while beating a minnow you were 95% to beat barely registers. Ratings stay venue-neutral; hosts get a separate boost." },
  { ic: "🔥", name: "Confederation-adjusted form", body: "Recent goals for and against, but discounted when they're piled up against weaker confederations — so a 7–1 over a minnow doesn't fool the model into overrating the winner." },
  { ic: "⚡", name: "Momentum", body: "A short-lived psychological bonus carried into the next match. Biggest after a surprise win and for average teams riding belief; softened for wounded giants who regroup." },
  { ic: "💹", name: "Market blend", body: "When available, bookmaker 1X2 and over/under implied probabilities — the single strongest public signal — are blended in with high weight." },
  { ic: "🎯", name: "Dixon–Coles matrix", body: "The blended expected goals feed a Dixon–Coles scoreline matrix, whose ρ correction fixes the low-score and draw probabilities that a naive Poisson gets wrong." },
  { ic: "⚖️", name: "Shrinkage calibration", body: "After each matchday the model compares predicted vs. actual goals and nudges its scoring level — with shrinkage so a handful of early games can't cause overfitting." },
  { ic: "🎲", name: "Monte Carlo simulation", body: "The whole tournament is simulated 20,000 times through the calibrated model to produce live title, final, semi and advancement odds — consistent with every match pick." },
  { ic: "🔒", name: "Locked, then graded", body: "Every pick is written to the database before kickoff and never edited. Results are joined back in and each pick is graded exact / correct outcome / miss. No hindsight." },
];

function renderMethods() {
  const wrap = document.getElementById("methods");
  METHODS.forEach((m) => {
    const card = el("div", "method");
    card.appendChild(el("div", "m-ic", m.ic));
    card.appendChild(el("div", "m-name", m.name));
    card.appendChild(el("div", "m-body", m.body));
    wrap.appendChild(card);
  });
}

function setupReveal() {
  const obs = new IntersectionObserver(
    (entries) => entries.forEach((e) => e.isIntersecting && e.target.classList.add("in")),
    { threshold: 0.08 }
  );
  document.querySelectorAll(".section").forEach((s) => {
    s.classList.add("reveal");
    obs.observe(s);
  });
}

async function main() {
  const data = await fetch("data.json?" + Date.now()).then((r) => r.json());
  ALL_PREDS = data.predictions;

  renderHero(data.summary);
  renderScoreCards(data.summary);
  renderTrend(data.timeline);
  renderFilters(data.predictions);
  renderTable("all");
  renderFutures(data.futures);
  renderRace(data.odds);
  renderMethods();
  setupReveal();

  const when = new Date(data.generated_at).toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
  document.getElementById("updated").textContent = "Last updated " + when;
  document.getElementById("footUpdated").textContent = "Updated " + when;
}

main().catch((e) => {
  document.getElementById("heroStats").innerHTML =
    `<div class="hstat"><div class="num p">!</div><div class="lbl">Could not load data.json</div></div>`;
  console.error(e);
});
