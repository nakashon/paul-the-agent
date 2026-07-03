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
    { num: s.total_points, cls: "gold", lbl: "Points scored", dec: 0 },
    { num: s.outcome_accuracy * 100, cls: "g", lbl: "Outcome accuracy", dec: 1, suf: "%" },
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
  const eff = Math.round(s.efficiency * 100);
  const cards = [
    {
      big: `${s.total_points}<span style="font-size:1.2rem;color:var(--faint)">/${s.max_points}</span>`,
      cap: "Points captured",
      sub: `${eff}% of maximum available points`,
      bar: s.efficiency,
    },
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
  tr.appendChild(el("td", "team ta-r", p.home));
  tr.appendChild(
    el("td", "ta-c", `<span class="pick">${p.pred_home}–${p.pred_away}</span>`)
  );
  tr.appendChild(el("td", "team ta-l", p.away));

  if (p.status === "pending") {
    tr.appendChild(el("td", "ta-c", `<span class="badge b-pending">TBD</span>`));
    tr.appendChild(el("td", "ta-c pts", "—"));
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
    tr.appendChild(el("td", "ta-c pts", `+${p.points}`));
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
  if (!list.length) body.appendChild(el("tr", null, `<td colspan="6" style="text-align:center;color:var(--faint);padding:30px">No matches in this view.</td>`));
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
    info.appendChild(el("div", "pk", f.pick));
    info.appendChild(el("div", "mp", `Worth ${f.max_points} pts · ${f.status === "pending" ? "still live" : f.status}`));
    card.appendChild(info);
    wrap.appendChild(card);
  });
}

function renderRace(odds) {
  const wrap = document.getElementById("race");
  const max = odds[0]?.title || 1;
  odds.forEach((o) => {
    const row = el("div", "rrow");
    row.appendChild(el("div", "rteam", o.team));
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
  renderFilters(data.predictions);
  renderTable("all");
  renderFutures(data.futures);
  renderRace(data.odds);
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
