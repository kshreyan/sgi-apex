"use strict";

const state = { data: null, selected: null, reveal: false };
const $app = document.getElementById("app");

const fmt = {
  int: (x) => (x == null ? "—" : Math.round(x).toLocaleString("en-IN")),
  pct: (x, d = 0) => (x == null ? "—" : (100 * x).toFixed(d) + "%"),
  pp: (x) => (Math.abs(x) < 0.005 ? "±0" : (x > 0 ? "+" : "−") + Math.abs(100 * x).toFixed(0)) + " pts",
  inr: (x) => (x == null ? "—" : "₹" + Math.round(x).toLocaleString("en-IN")),
  date: (s) => new Date(s + "T00:00:00").toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" }),
};
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const chip = (cls, text) => `<span class="chip ${esc(cls)}">${esc(text ?? cls)}</span>`;
const byId = () => Object.fromEntries(state.data.programmes.map((p) => [p.programme_id, p]));
const optionLabel = (id, p) => (p.actions?.options.find((o) => o.id === id)?.label) || id;

// ---------- charts (inline SVG) ----------

function intervalStrip(p, width = 220) {
  const h = 26, pad = 4, x = (v) => pad + (v / p.intake) * (width - 2 * pad);
  const target = p.target_fill * p.intake;
  return `<svg width="${width}" height="${h}" role="img" aria-label="${esc(p.programme)} forecast ${fmt.int(p.q05)} to ${fmt.int(p.q95)} of ${p.intake}">
    <line class="axis" x1="${pad}" x2="${width - pad}" y1="${h / 2}" y2="${h / 2}"/>
    <rect x="${x(p.q05)}" y="${h / 2 - 6}" width="${Math.max(2, x(p.q95) - x(p.q05))}" height="12" rx="2" fill="var(--band-90)"/>
    <rect x="${x(p.q25)}" y="${h / 2 - 6}" width="${Math.max(2, x(p.q75) - x(p.q25))}" height="12" rx="2" fill="var(--band-50)"/>
    <line x1="${x(p.median)}" x2="${x(p.median)}" y1="${h / 2 - 8}" y2="${h / 2 + 8}" stroke="var(--ink)" stroke-width="2"/>
    <line x1="${x(target)}" x2="${x(target)}" y1="2" y2="${h - 2}" stroke="var(--red)" stroke-dasharray="2 2"/>
    <circle cx="${x(p.enrolled_to_date)}" cy="${h / 2}" r="3" fill="var(--surface)" stroke="var(--ink-2)"/>
  </svg>`;
}

function curveChart(p) {
  const curves = state.data.curves[p.programme_id];
  const W = 760, H = 280, L = 40, R = 44, T = 14, B = 30;
  const weeks = state.data.meta.cycle_weeks, asOf = state.data.meta.week, year = state.data.meta.year;
  const x = (w) => L + (w / weeks) * (W - L - R);
  const y = (v) => T + (1 - v / p.intake) * (H - T - B);
  const path = (arr, upTo = weeks) => arr.slice(0, upTo + 1).map((v, w) => `${w ? "L" : "M"}${x(w).toFixed(1)},${y(v).toFixed(1)}`).join("");
  let s = `<svg viewBox="0 0 ${W} ${H}" width="100%" style="max-height:340px" role="img" aria-label="Cumulative enrolment curve for ${esc(p.programme)}">`;
  [0, 0.25, 0.5, 0.75, 1].forEach((f) => {
    s += `<line class="axis" x1="${L}" x2="${W - R}" y1="${y(f * p.intake)}" y2="${y(f * p.intake)}"/>`;
    s += `<text x="${L - 6}" y="${y(f * p.intake) + 4}" text-anchor="end">${Math.round(f * p.intake)}</text>`;
  });
  [0, 5, 10, 15, 20, 26].forEach((w) => (s += `<text x="${x(w)}" y="${H - 10}" text-anchor="middle">wk ${w}</text>`));
  const tgt = p.target_fill * p.intake;
  s += `<line x1="${L}" x2="${W - R}" y1="${y(tgt)}" y2="${y(tgt)}" stroke="var(--red)" stroke-dasharray="4 3"/>`;
  s += `<text x="${W - R}" y="${y(tgt) - 4}" text-anchor="end" style="fill:var(--red)">target ${fmt.pct(p.target_fill)}</text>`;
  Object.keys(curves).filter((yr) => +yr < year).forEach((yr) => {
    const c = curves[yr];
    s += `<path d="${path(c)}" fill="none" stroke="var(--hist)" stroke-width="1.5"/>`;
    s += `<text x="${x(weeks) + 2}" y="${y(c[weeks]) + 3}" style="font-size:10px">${yr}</text>`;
  });
  // forecast fan at end of cycle, joined from today's value
  const cur = curves[year][asOf];
  const fan = (lo, hi, fill) => `<path d="M${x(asOf)},${y(cur)} L${x(weeks)},${y(hi)} L${x(weeks)},${y(lo)} Z" fill="${fill}" opacity="0.9"/>`;
  s += fan(p.q05, p.q95, "var(--band-90)") + fan(p.q25, p.q75, "var(--band-50)");
  s += `<line x1="${x(asOf)}" y1="${y(cur)}" x2="${x(weeks)}" y2="${y(p.median)}" stroke="var(--ink)" stroke-dasharray="3 3"/>`;
  if (state.reveal) s += `<path d="${path(curves[year])}" fill="none" stroke="var(--green)" stroke-width="2" stroke-dasharray="1 0"/>`
    + `<circle cx="${x(weeks)}" cy="${y(curves[year][weeks])}" r="4" fill="var(--green)"/>`;
  s += `<path d="${path(curves[year], asOf)}" fill="none" stroke="var(--accent)" stroke-width="2.5"/>`;
  s += `<line x1="${x(asOf)}" x2="${x(asOf)}" y1="${T}" y2="${H - B}" stroke="var(--ink-3)" stroke-dasharray="2 3"/>`;
  s += `<text x="${x(asOf) + 4}" y="${T + 10}">as of wk ${asOf}</text>`;
  return s + "</svg>";
}

function lineChart(series, { yLabel, yMax, xs, refLine }) {
  const W = 520, H = 250, L = 44, R = 110, T = 12, B = 28;
  const x = (v) => L + ((v - xs[0]) / (xs[xs.length - 1] - xs[0])) * (W - L - R);
  const y = (v) => T + (1 - v / yMax) * (H - T - B);
  let s = `<svg viewBox="0 0 ${W} ${H}" width="100%" role="img" aria-label="${esc(yLabel)}">`;
  for (let i = 0; i <= 4; i++) {
    const v = (yMax * i) / 4;
    s += `<line class="axis" x1="${L}" x2="${W - R}" y1="${y(v)}" y2="${y(v)}"/><text x="${L - 6}" y="${y(v) + 4}" text-anchor="end">${v.toFixed(yMax < 1.5 ? 2 : 0)}</text>`;
  }
  xs.forEach((w) => (s += `<text x="${x(w)}" y="${H - 8}" text-anchor="middle">wk ${w}</text>`));
  if (refLine != null) s += `<line x1="${L}" x2="${W - R}" y1="${y(refLine)}" y2="${y(refLine)}" stroke="var(--ink-3)" stroke-dasharray="4 3"/>`;
  series.forEach((sr) => {
    const d = sr.points.map(([a, b], i) => `${i ? "L" : "M"}${x(a)},${y(b)}`).join("");
    s += `<path d="${d}" fill="none" stroke="${sr.color}" stroke-width="${sr.bold ? 2.5 : 1.5}"/>`;
    sr.points.forEach(([a, b]) => (s += `<circle cx="${x(a)}" cy="${y(b)}" r="${sr.bold ? 3 : 2}" fill="${sr.color}"/>`));
  });
  // End labels, nudged apart vertically so lines that finish together stay readable.
  const labels = series.map((sr) => { const [la, lb] = sr.points[sr.points.length - 1]; return { sr, x: x(la) + 6, y: y(lb) + 4 }; })
    .sort((a, b) => a.y - b.y);
  labels.forEach((l, i) => { if (i && l.y - labels[i - 1].y < 12) l.y = labels[i - 1].y + 12; });
  labels.forEach(({ sr, x: lx, y: ly }) => (s += `<text x="${lx}" y="${ly}" style="fill:${sr.color};font-weight:${sr.bold ? 700 : 400}">${esc(sr.name)}</text>`));
  return s + `<text x="${L}" y="${T - 2}">${esc(yLabel)}</text></svg>`;
}

function reliabilityChart(bins) {
  const W = 300, H = 260, L = 40, R = 12, T = 12, B = 34;
  const x = (v) => L + v * (W - L - R), y = (v) => T + (1 - v) * (H - T - B);
  let s = `<svg viewBox="0 0 ${W} ${H}" width="100%" role="img" aria-label="Reliability diagram">`;
  [0, 0.5, 1].forEach((v) => (s += `<text x="${L - 6}" y="${y(v) + 4}" text-anchor="end">${v}</text><text x="${x(v)}" y="${H - 18}" text-anchor="middle">${v}</text>`));
  s += `<rect x="${L}" y="${T}" width="${W - L - R}" height="${H - T - B}" fill="none" class="axis" stroke="var(--line)"/>`;
  s += `<line x1="${x(0)}" y1="${y(0)}" x2="${x(1)}" y2="${y(1)}" stroke="var(--ink-3)" stroke-dasharray="4 3"/>`;
  s += `<path d="${bins.map((b, i) => `${i ? "L" : "M"}${x(b.mean_forecast)},${y(b.observed)}`).join("")}" fill="none" stroke="var(--accent)" stroke-width="2"/>`;
  bins.forEach((b) => (s += `<circle cx="${x(b.mean_forecast)}" cy="${y(b.observed)}" r="${3 + Math.sqrt(b.n) / 2}" fill="var(--accent)" opacity="0.8"><title>${b.bin}: forecast ${fmt.pct(b.mean_forecast)}, observed ${fmt.pct(b.observed)} (n=${b.n})</title></circle>`));
  s += `<text x="${(L + W - R) / 2}" y="${H - 4}" text-anchor="middle">forecast P(meet target)</text>`;
  return s + "</svg>";
}

// ---------- views ----------

function viewTower() {
  const d = state.data, m = d.meta, g = d.group["group:SGI"], ps = byId();
  const delta = m.admissions_health - m.admissions_health_prev;
  const sc = m.status_counts;
  const camp = Object.entries(d.group).filter(([k]) => k.startsWith("campus:"));
  let h = `<h2>What needs your attention</h2>
  <p class="lede">The ${m.year} admission cycle as of week ${m.week} of ${m.cycle_weeks} (${fmt.date(m.as_of)}). Only programmes whose seat-fill risk is both likely and material are listed. The other ${sc.GREEN || 0} are within normal range.</p>
  <div class="kpis">
    <div class="kpi"><div class="label">Admissions health · partial</div><div class="value">${m.admissions_health.toFixed(0)}<span class="muted" style="font-size:16px">/100</span></div><div class="sub">${delta >= 0 ? "▲" : "▼"} ${Math.abs(delta).toFixed(1)} vs last week · capacity-weighted chance of hitting each programme's target</div></div>
    <div class="kpi"><div class="label">Group enrolment forecast</div><div class="value">${fmt.int(g.median)}</div><div class="sub">of ${fmt.int(g.intake)} seats · 90% range ${fmt.int(g.q05)}–${fmt.int(g.q95)}</div></div>
    <div class="kpi"><div class="label">Chance group meets ${fmt.pct(g.target_fill)} fill</div><div class="value">${fmt.pct(g.p_meet_target)}</div><div class="sub">${camp.map(([k, v]) => `${k.split(":")[1]} ${fmt.pct(v.p_meet_target)}`).join(" · ")}</div></div>
    <div class="kpi"><div class="label">Exceptions</div><div class="value">${sc.RED || 0}<span style="font-size:14px"> ${chip("RED")}</span> ${sc.AMBER || 0}<span style="font-size:14px"> ${chip("AMBER")}</span></div><div class="sub">${sc.GREEN || 0} green · BLACK reserved for legal/safety/liquidity events</div></div>
  </div>
  <div class="cards">`;
  d.attention.forEach((pid) => (h += attentionCard(ps[pid])));
  h += `</div>
  <h2>Chairman daily brief</h2>
  <p class="lede">Generated by <code>sgi chairman-brief</code> from the same data as this page.</p>
  <div class="brief" id="brief">Loading…</div>`;
  $app.innerHTML = h;
  fetch("data/brief.txt", { cache: "no-cache" }).then((r) => (r.ok ? r.text() : "Brief not generated.")).then((t) => (document.getElementById("brief").textContent = t));
}

function attentionCard(p) {
  const a = p.actions, curves = state.data.curves[p.programme_id], m = state.data.meta;
  const lastYr = curves[m.year - 1];
  const rec = a.options.find((o) => o.id === a.recommended);
  const dec = state.data.decisions.find((x) => x.decision_id === `ADM-${m.year}-${p.programme_id}`);
  const shortLo = Math.max(0, p.target_fill * p.intake - p.q75), shortHi = Math.max(0, p.target_fill * p.intake - p.q25);
  return `<article class="card ${p.status}">
    <div class="card-head"><span class="name">${esc(p.programme)} · ${esc(p.campus)}</span>${chip(p.status)}</div>
    <div class="muted" style="font-size:13px">${esc(p.institution)}</div>
    <div class="grid-facts">
      <div><div class="k">Seat-fill forecast</div><div class="v">${fmt.pct(p.median / p.intake)} <span class="muted">(${fmt.int(p.median)}/${p.intake})</span></div></div>
      <div><div class="k">Target</div><div class="v">${fmt.pct(p.target_fill)}</div></div>
      <div><div class="k">P(meet target)</div><div class="v">${fmt.pct(p.p_meet_target)} <span class="muted">${fmt.pp(p.p_change_wow)} wk</span></div></div>
      <div><div class="k">Likely shortfall (50%)</div><div class="v">${fmt.int(shortLo)}–${fmt.int(shortHi)} seats</div></div>
      <div><div class="k">Owner</div><div class="v" style="font-family:var(--sans)">${esc(dec?.decision_owner)}</div></div>
      <div><div class="k">Decide by</div><div class="v">${dec ? fmt.date(dec.deadline) : "—"}</div></div>
    </div>
    <p class="why"><span class="tag fact">Fact</span> ${p.enrolled_to_date} enrolled and ${p.applications_to_date} applications by week ${m.week}; last year at this week: ${lastYr ? lastYr[m.week] : "—"} enrolled, final ${lastYr ? lastYr[m.cycle_weeks] : "—"}. Last 3 cycles averaged ${fmt.pct(p.base_rate_fill)} final fill.
    <br><span class="tag forecast">Forecast</span> 90% range ${fmt.int(p.q05)}–${fmt.int(p.q95)} enrolments (${esc(m.champion)}), data quality ${fmt.pct(p.data_quality.score)}.
    <br><span class="tag rec">Recommendation</span> <strong>${esc(rec.label)}</strong>: ${rec.id === "do_nothing" ? "no option clears its cost under current assumptions" : `+${rec.added_enrolments_mean} expected enrolments, P(target) → ${fmt.pct(rec.p_meet_target)}, expected net ${fmt.inr(rec.expected_net_value_inr)}`}. Confidence ${chip(a.robustness)}</p>
    <details><summary>Compare all options</summary>${optionsTable(a)}
      <p class="muted" style="font-size:12px"><span class="tag assumption">Assumption</span> Uplift ranges are priors, not SGI evidence, and seat value is a placeholder (${fmt.inr(a.value_per_seat_inr)} lifetime contribution per student). Best option at low / sampled / high uplift: ${esc(a.winners_low_draw_high.low)} / ${esc(a.winners_low_draw_high.draw)} / ${esc(a.winners_low_draw_high.high)}.</p>
    </details>
  </article>`;
}

function optionsTable(a) {
  return `<div class="table-wrap"><table><thead><tr><th>Option</th><th class="n">Cost</th><th class="n hide-sm">Assumed uplift</th><th class="n">Added enrolments</th><th class="n">P(target)</th><th class="n">Expected net</th></tr></thead><tbody>
  ${a.options.map((o) => `<tr${o.id === a.recommended ? ' class="selected"' : ""}><td>${esc(o.label)}</td><td class="n">${fmt.inr(o.cost_inr)}</td><td class="n hide-sm">${fmt.pct(o.assumed_uplift[0])}–${fmt.pct(o.assumed_uplift[1])}</td><td class="n">${o.added_enrolments_mean} <span class="muted">(${o.added_enrolments_p10_p90.join("–")})</span></td><td class="n">${fmt.pct(o.p_meet_target)}</td><td class="n">${fmt.inr(o.expected_net_value_inr)}</td></tr>`).join("")}
  </tbody></table></div>`;
}

function viewForecasts() {
  const d = state.data, m = d.meta;
  const rows = [...d.programmes].sort((a, b) => a.p_meet_target - b.p_meet_target);
  state.selected = state.selected || rows[0].programme_id;
  const p = byId()[state.selected];
  let h = `<h2>Programme forecasts</h2>
  <p class="lede">Final enrolment by programme, ${m.year} cycle, as of week ${m.week}. Campus and group totals are built by adding up programme draws, so the levels always agree. Select a row to see its enrolment curve.</p>
  <div class="panel" style="margin-bottom:14px">
    <div class="card-head"><h3>${esc(p.programme)} · ${esc(p.campus)} ${chip(p.status)}</h3>
      <button class="btn" id="reveal" aria-pressed="${state.reveal}">${state.reveal ? "Hide" : "Reveal"} actual outcome</button></div>
    ${curveChart(p)}
    <div class="legend"><span><i style="background:var(--accent)"></i>${m.year} to date</span><span><i style="background:var(--hist)"></i>prior cycles</span><span><i style="background:var(--band-50)"></i>50% range</span><span><i style="background:var(--band-90)"></i>90% range</span>${state.reveal ? '<span><i style="background:var(--green)"></i>actual (revealed)</span>' : ""}</div>
    <p class="muted" style="font-size:12px;margin:6px 0 0">Intake ${p.intake} (${esc(p.intake_source)}). ${p.intake_source === "PLACEHOLDER" ? "Sanctioned intake not yet verified: replace it with the regulator's approval letter." : ""}</p>
  </div>
  <div class="table-wrap"><table><thead><tr><th>Programme</th><th class="hide-sm">Campus</th><th class="n">To date</th><th class="n">Median</th><th>Range <span class="muted" style="text-transform:none">(0 to intake · ● to date · ┆ target)</span></th><th class="n">P(target)</th><th>Status</th><th class="n hide-sm">DQ</th></tr></thead><tbody>`;
  rows.forEach((r) => {
    h += `<tr class="clickable${r.programme_id === state.selected ? " selected" : ""}" data-pid="${r.programme_id}" tabindex="0">
      <td>${esc(r.programme)}</td><td class="hide-sm">${esc(r.campus)}</td><td class="n">${r.enrolled_to_date}</td><td class="n">${fmt.int(r.median)}/${r.intake}</td>
      <td>${intervalStrip(r)}</td><td class="n">${fmt.pct(r.p_meet_target)}</td><td>${chip(r.status)}</td><td class="n hide-sm">${fmt.pct(r.data_quality.score)}</td></tr>`;
  });
  h += `</tbody></table></div>`;
  h += `<h2>Roll-ups</h2><div class="table-wrap"><table><thead><tr><th>Level</th><th class="n">Seats</th><th class="n">Median</th><th class="n">50% range</th><th class="n">90% range</th><th class="n">P(target)</th></tr></thead><tbody>
  ${Object.entries(d.group).map(([k, v]) => `<tr><td>${esc(k.replace("group:", "Group · ").replace("campus:", "Campus · "))}</td><td class="n">${v.intake}</td><td class="n">${fmt.int(v.median)}</td><td class="n">${fmt.int(v.q25)}–${fmt.int(v.q75)}</td><td class="n">${fmt.int(v.q05)}–${fmt.int(v.q95)}</td><td class="n">${fmt.pct(v.p_meet_target)}</td></tr>`).join("")}
  </tbody></table></div>`;
  $app.innerHTML = h;
  $app.querySelectorAll("tr[data-pid]").forEach((tr) => {
    const go = () => { state.selected = tr.dataset.pid; viewForecasts(); };
    tr.addEventListener("click", go);
    tr.addEventListener("keydown", (e) => e.key === "Enter" && go());
  });
  document.getElementById("reveal").addEventListener("click", () => { state.reveal = !state.reveal; viewForecasts(); });
}

function viewLoop() {
  const L = state.data.loop, m = state.data.meta;
  if (L.status !== "CLOSED") { $app.innerHTML = `<h2>Loop closed</h2><p class="lede">${esc(L.message)}</p>`; return; }
  let h = `<h2>Loop closed: frozen forecast vs actual</h2>
  <p class="lede">The week-${m.week} forecast was frozen in the prediction lockbox before the outcome was known, and is scored here against what actually happened. It is never re-run or overwritten.</p>
  <div class="kpis">
    <div class="kpi"><div class="label">Group actual vs forecast</div><div class="value">${fmt.int(L.group.actual)}</div><div class="sub">forecast median ${fmt.int(L.group.median)}, 90% ${fmt.int(L.group.q05)}–${fmt.int(L.group.q95)} · ${L.group.in_90 ? "inside" : "outside"} the 90% range</div></div>
    <div class="kpi"><div class="label">50% range coverage</div><div class="value">${fmt.pct(L.coverage50)}</div><div class="sub">should be near 50%</div></div>
    <div class="kpi"><div class="label">90% range coverage</div><div class="value">${fmt.pct(L.coverage90)}</div><div class="sub">should be near 90%</div></div>
    <div class="kpi"><div class="label">Brier · seat-fill events</div><div class="value">${L.brier.toFixed(3)}</div><div class="sub">0 = perfect · 0.25 = coin flip · MAE ${L.mae_seats.toFixed(1)} seats</div></div>
  </div>
  <p class="muted mono" style="font-size:12px">frozen ${esc(L.frozen_at)} · model ${esc(L.model)} · content ${esc(L.content_hash)}… · data snapshot ${esc(L.data_snapshot_hash)}…</p>
  <div class="table-wrap"><table><thead><tr><th>Programme</th><th class="hide-sm">Campus</th><th class="n">Forecast median</th><th class="n">90% range</th><th class="n">Actual</th><th class="n">P(target) given</th><th>Target hit?</th><th>In 90%?</th></tr></thead><tbody>
  ${L.programmes.map((r) => `<tr><td>${esc(r.programme)}</td><td class="hide-sm">${esc(r.campus)}</td><td class="n">${fmt.int(r.forecast_median)}</td><td class="n">${fmt.int(r.q05)}–${fmt.int(r.q95)}</td><td class="n"><strong>${r.actual}</strong>/${r.intake}</td><td class="n">${fmt.pct(r.p_meet_target)}</td><td>${r.hit_target ? chip("GREEN", "yes") : chip("RED", "no")}</td><td>${r.in_90 ? "✓" : chip("AMBER", "miss")}</td></tr>`).join("")}
  </tbody></table></div>
  <div class="callout"><strong>Judging decisions by quality, not luck.</strong> The proposed decisions for this cycle are still <em>PROPOSED</em> in the register. In the demo nobody acted on them, so the actuals above show the "do nothing" counterfactual. When a decision is taken, <code>register.close()</code> records the outcome, a failure class (data, model, assumption, execution, external shock or random variance) and a decision-quality grade based on what was known at the time.</div>`;
  $app.innerHTML = h;
}

function viewModels() {
  const b = state.data.backtest, champ = state.data.meta.champion;
  const models = Object.keys(b.selection.crps_by_model);
  const weeks = [...new Set(b.validation.map((r) => r.week))].sort((a, c) => a - c);
  const palette = { seasonal_naive: "var(--ink-3)", pace_own: "var(--amber)", pace_pooled: "var(--green)", bayes_blend: "var(--accent)" };
  const series = (key, src) => models.map((mo) => ({ name: mo, color: palette[mo], bold: mo === champ, points: weeks.map((w) => [w, src.find((r) => r.model === mo && r.week === w)[key]]) }));
  const crpsMax = Math.ceil(Math.max(...b.validation.map((r) => r.crps)) * 50) / 50;
  let h = `<h2>Model evaluation</h2>
  <p class="lede">Rolling-origin backtest. Each origin year is forecast using only data available at that week. The champion is chosen on ${b.validation_years[0]}–${b.validation_years[b.validation_years.length - 1]} at the week-${b.selection.horizon_week} horizon. A simpler model wins any near-tie (within 2%). ${b.lockbox_years.join(", ")} is the lockbox: scored once and never used for tuning.</p>
  <div class="table-wrap"><table><thead><tr><th>Model</th><th>Role</th><th class="n">CRPS / intake @ wk ${b.selection.horizon_week}</th></tr></thead><tbody>
  ${models.map((mo) => `<tr${mo === champ ? ' class="selected"' : ""}><td class="mono">${mo}</td><td>${esc(b.selection.roles[mo])}</td><td class="n">${b.selection.crps_by_model[mo].toFixed(4)}</td></tr>`).join("")}
  </tbody></table></div>
  <div class="two" style="margin-top:16px">
    <div class="panel"><h3>Accuracy through the cycle</h3><p class="muted" style="font-size:13px;margin:0">CRPS ÷ intake, lower is better (validation years)</p>${lineChart(series("crps", b.validation), { yLabel: "CRPS / intake", yMax: crpsMax, xs: weeks })}</div>
    <div class="panel"><h3>90% interval coverage</h3><p class="muted" style="font-size:13px;margin:0">Share of actuals inside the 90% range. Dashed line = 0.90</p>${lineChart(series("cover90", b.validation), { yLabel: "coverage", yMax: 1, xs: weeks, refLine: 0.9 })}</div>
  </div>
  <div class="two" style="margin-top:16px">
    <div class="panel"><h3>Calibration of seat-fill probabilities</h3><p class="muted" style="font-size:13px;margin:0">Champion, all validation forecasts. On the diagonal = calibrated.</p>${reliabilityChart(b.reliability)}</div>
    <div class="panel"><h3>Lockbox (${b.lockbox_years.join(", ")}) at week ${b.selection.horizon_week}</h3>
      <div class="table-wrap"><table><thead><tr><th>Model</th><th class="n">CRPS</th><th class="n">Cov 90</th><th class="n">Brier</th></tr></thead><tbody>
      ${b.lockbox.filter((r) => r.week === b.selection.horizon_week).map((r) => `<tr><td class="mono">${r.model}</td><td class="n">${r.crps.toFixed(3)}</td><td class="n">${fmt.pct(r.cover90)}</td><td class="n">${r.brier.toFixed(3)}</td></tr>`).join("")}
      </tbody></table></div>
      <p class="muted" style="font-size:12px">Honest reading: the champion beats the seasonal baseline by only a hair, and pace models are better at predicting whether a target is hit (Brier). With 5 validation years the group-level 90% ranges are still somewhat narrow. Both points are logged in <code>docs/limitations.md</code>.</p></div>
  </div>`;
  $app.innerHTML = h;
}

function viewDecisions() {
  const ds = state.data.decisions, ps = byId();
  $app.innerHTML = `<h2>Decision register</h2>
  <p class="lede">An append-only log. Each decision keeps its problem, options, the forecast it was based on, its assumptions, the recommendation, owner and deadline. The outcome and postmortem are added later as new events, so the record never changes after the fact.</p>
  <div class="table-wrap"><table><thead><tr><th>Decision</th><th>Risk</th><th>Problem</th><th>Recommended</th><th>Confidence</th><th class="n">Expected value</th><th>Owner</th><th>Deadline</th><th>Status</th></tr></thead><tbody>
  ${ds.map((d) => { const p = ps[d.decision_id.split("-").slice(2).join("-")]; return `<tr><td class="mono" style="font-size:12px">${esc(d.decision_id)}</td><td>${chip(d.risk)}</td><td style="min-width:220px">${esc(d.problem)}</td><td>${esc(p ? optionLabel(d.recommended_action, p) : d.recommended_action)}</td><td>${chip(d.confidence)}</td><td class="n">${fmt.inr(d.expected_value)}</td><td>${esc(d.decision_owner)}</td><td class="mono">${esc(d.deadline)}</td><td>${esc(d.status)}</td></tr>`; }).join("")}
  </tbody></table></div>
  <p class="muted" style="font-size:12px">Delegation: AMBER items go to the Head of Admissions and RED items to the Director General. The chairman sees RED items in the brief. Expected value is based on assumptions (placeholder seat economics and prior uplift ranges).</p>`;
}

function viewOrg() {
  const es = state.data.entities;
  const hosp = es.find((e) => e.entity_id === "HOSP-CHAKIA");
  $app.innerHTML = `<h2>Organisation: entity registry</h2>
  <p class="lede">Phase 0 discovery from public sources (subhwanti.com, pharma.subhwanti.com and third-party directories), checked on ${esc(es[0].verified_at)}. This is the only real-world data on this site. Group roll-ups are blocked if any programme maps to an unknown or low-confidence entity.</p>
  <div class="callout"><strong>Chakia hospital: not verified.</strong> ${esc(hosp.verification_source)}. No hospital forecasts or quality alerts will be built until the legal name, registration and licensing are confirmed from internal documents.</div>
  <div class="table-wrap"><table><thead><tr><th>ID</th><th>Name</th><th>Type</th><th class="hide-sm">Campus</th><th>Regulators</th><th>Affiliation</th><th class="hide-sm">Programmes</th><th>Confidence</th></tr></thead><tbody>
  ${es.map((e) => `<tr><td class="mono" style="font-size:12px">${esc(e.entity_id)}</td><td>${esc(e.legal_name)}</td><td>${esc(e.entity_type)}</td><td class="hide-sm">${esc(e.campus)}</td><td>${esc(e.regulators)}</td><td>${esc(e.affiliating_body)}</td><td class="hide-sm" style="font-size:13px">${esc(e.approved_programmes)}</td><td>${chip(e.confidence)}</td></tr>`).join("")}
  </tbody></table></div>
  <p class="muted" style="font-size:12px">Leadership listed on subhwanti.com/leadership.php: Chairman, President, Director General and Group Director. Open questions include the Foundation's legal form (trust, society or Section 8 company), the conflicting pharmacy affiliation (BUHS vs AKU), whether SISM programmes are split between campuses, engineering branches and intakes, and the status of the historical names SIHE and SIMT.</p>`;
}

function viewAbout() {
  $app.innerHTML = `<h2>About SGI APEX</h2>
  <p class="lede">SGI APEX is a decision system for the chairman of the Subhwanti Sudama Rai Foundation / Subhwanti Group of Institutions. It turns raw operations into a small number of forecasts, risks and decisions, each with a probability, an owner and a deadline.</p>
  <div class="two">
    <div class="panel"><h3>Built in milestone 1</h3><ul class="tight">
      <li>Entity registry with verification sources and confidence (Phase 0)</li>
      <li>Bronze → silver → gold admissions pipeline with data-quality scoring</li>
      <li>Four forecast models with champion/challenger selection</li>
      <li>Correlated Monte Carlo draws whose programme, campus and group totals always agree</li>
      <li>Rolling-origin backtest, a lockbox year and a frozen prospective forecast</li>
      <li>GREEN/AMBER/RED exceptions, with materiality rules to avoid alarm fatigue</li>
      <li>Action options compared by simulation, with a robustness grade</li>
      <li>Append-only decision register and human-override log</li>
      <li>Chairman daily brief and this control tower</li></ul></div>
    <div class="panel"><h3>Next milestones</h3><ul class="tight">
      <li><strong>M1-real:</strong> replace the simulator with real admissions exports (ERP/CSV)</li>
      <li><strong>M2:</strong> 13-week cash forecast, liquidity scenarios and capital recommendations</li>
      <li><strong>M3:</strong> national-excellence gap analysis (NIRF/NAAC peers)</li>
      <li><strong>M4:</strong> hospital operations, once the entity is verified (non-clinical only)</li></ul>
      <h3 style="margin-top:12px">Never automated</h3><p style="margin:0;font-size:14px">Admissions approvals, student discipline, hiring/firing, clinical decisions, money movement and capital commitments. These always need an authorised human.</p></div>
  </div>
  <h2>Documentation</h2><ul class="tight">
    ${["chairman_operating_model", "entity_registry", "architecture", "data_sources", "forecasting_protocol", "governance", "privacy_security", "data_availability", "build_plan_90_day", "strategic_gap_analysis", "limitations"].map((f) => `<li><a href="https://github.com/kshreyan/sgi-apex/blob/main/docs/${f}.md">${f.replace(/_/g, " ")}</a></li>`).join("")}
  </ul>`;
}

const views = { tower: viewTower, forecasts: viewForecasts, loop: viewLoop, models: viewModels, decisions: viewDecisions, org: viewOrg, about: viewAbout };

function route() {
  const tab = (location.hash || "#tower").slice(1);
  const fn = views[tab] || viewTower;
  document.querySelectorAll(".tabs a").forEach((a) => a.classList.toggle("active", a.dataset.tab === tab));
  fn();
  window.scrollTo(0, 0);
}

fetch("data/apex.json", { cache: "no-cache" })
  .then((r) => r.json())
  .then((d) => {
    state.data = d;
    document.getElementById("foot-meta").textContent = `Data mode: ${d.meta.data_mode} · as of ${fmt.date(d.meta.as_of)} · built ${d.meta.generated} · champion ${d.meta.champion}`;
    window.addEventListener("hashchange", route);
    route();
  })
  .catch((e) => ($app.innerHTML = `<p>Could not load data: ${esc(e.message)}</p>`));
