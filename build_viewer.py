"""Build viewer.html from data/faculty_matches.json.

Usage:  python build_viewer.py [input.json] [output.html]
Re-run any time the scraper rewrites the JSON. Output is a single
self-contained HTML file that opens by double-click (no server).
"""
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "data" / "faculty_matches.json"
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "viewer.html"


def embed_json(obj):
    s = json.dumps(obj, ensure_ascii=False)
    # Make safe inside <script>: no "</script>", no HTML comment tricks, no JS line separators.
    return (s.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
             .replace("\u2028", "\\u2028").replace("\u2029", "\\u2029"))


TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Faculty Matches</title>
<style>
:root {
  --bg: #f7f7f8; --panel: #ffffff; --text: #1d1d1f; --muted: #666a73; --border: #dcdde1;
  --accent: #2f5fd0; --chip: #eef1f7; --chip-on: #2f5fd0; --chip-on-text: #fff;
  --green: #1f7a3a; --green-bg: #e3f4e8; --red: #a52a2a; --red-bg: #fbe5e5;
  --grey: #555; --grey-bg: #ececec; --star: #d99a00; --row-alt: #fafafb;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #15171a; --panel: #1e2125; --text: #e6e6e6; --muted: #9aa0a8; --border: #33373d;
    --accent: #7aa2ff; --chip: #2a2e35; --chip-on: #7aa2ff; --chip-on-text: #10131a;
    --green: #7fd99a; --green-bg: #1d3a26; --red: #ff9b9b; --red-bg: #45201f;
    --grey: #c2c2c2; --grey-bg: #33363b; --star: #ffc940; --row-alt: #1b1e22;
  }
}
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--text);
  font: 14px/1.45 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }
a { color: var(--accent); }
header { padding: 14px 16px 6px; }
header h1 { margin: 0; font-size: 20px; }
header .counts { color: var(--muted); }
.controls { display: flex; flex-wrap: wrap; gap: 8px 14px; align-items: center;
  padding: 10px 16px; background: var(--panel); border-top: 1px solid var(--border);
  border-bottom: 1px solid var(--border); position: sticky; top: 0; z-index: 2; }
.controls input[type=search] { flex: 1 1 240px; min-width: 0; }
input, select, button { font: inherit; color: var(--text); background: var(--bg);
  border: 1px solid var(--border); border-radius: 6px; padding: 5px 8px; }
button { cursor: pointer; }
button:hover { border-color: var(--accent); }
label.cb { display: inline-flex; gap: 5px; align-items: center; white-space: nowrap; }
.chips { display: flex; flex-wrap: wrap; gap: 6px; }
.chip { display: inline-block; padding: 2px 9px; border-radius: 999px; background: var(--chip);
  border: 1px solid var(--border); font-size: 12px; white-space: nowrap; }
button.chip.on { background: var(--chip-on); color: var(--chip-on-text); border-color: var(--chip-on); }
main { padding: 10px 16px 40px; }
.card { background: var(--panel); border: 1px solid var(--border); border-radius: 8px;
  padding: 10px 12px; margin-bottom: 8px; }
.top { display: flex; gap: 10px; align-items: flex-start; }
.star { background: none; border: none; font-size: 20px; line-height: 1; padding: 0 2px;
  color: var(--muted); }
.star.on { color: var(--star); }
.main { flex: 1; min-width: 0; }
.name { font-weight: 600; font-size: 15px; }
.sub { color: var(--muted); }
.meta { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; margin-top: 5px; }
.badge { padding: 1px 8px; border-radius: 4px; font-size: 12px; font-weight: 600; }
.b-accepting { color: var(--green); background: var(--green-bg); }
.b-unknown { color: var(--grey); background: var(--grey-bg); }
.b-not_accepting { color: var(--red); background: var(--red-bg); }
.score { margin-left: auto; text-align: right; white-space: nowrap; color: var(--muted); font-size: 12px; }
.score b { color: var(--text); font-size: 16px; }
.terms { margin-top: 5px; font-size: 13px; }
.terms .cat { color: var(--muted); }
details { margin-top: 6px; }
summary { cursor: pointer; color: var(--accent); font-size: 13px; }
.ev { margin: 6px 0 0; padding-left: 18px; }
.ev li { margin-bottom: 6px; color: var(--text); }
.ev-acc { margin: 6px 0; padding: 6px 8px; border-left: 3px solid var(--border); background: var(--bg); }
.empty { color: var(--muted); padding: 30px 0; text-align: center; }
.tabs { display: flex; gap: 6px; margin-top: 10px; }
.tabs button.on { background: var(--accent); color: var(--chip-on-text); border-color: var(--accent); }
.hidden { display: none !important; }
.note { color: var(--muted); margin: 0 0 10px; }
.tbl-wrap { overflow-x: auto; }
table.miss { width: 100%; border-collapse: collapse; background: var(--panel); border: 1px solid var(--border); }
table.miss th, table.miss td { text-align: left; padding: 6px 8px; border-bottom: 1px solid var(--border); vertical-align: top; }
table.miss th { font-size: 12px; color: var(--muted); font-weight: 600; }
table.miss tr:nth-child(even) td { background: var(--row-alt); }
.b-excluded { color: var(--grey); background: var(--grey-bg); }
.b-crawl_failed { color: var(--red); background: var(--red-bg); }
@media (max-width: 600px) {
  .top { flex-wrap: wrap; }
  .score { margin-left: 0; width: 100%; text-align: left; }
  .controls { position: static; }
}
</style>
</head>
<body>
<header>
  <h1>Faculty Matches</h1>
  <div class="counts"><span id="shown">0</span> shown of <span id="total">0</span> total
    &middot; <span id="slCount">0</span> shortlisted &middot; built __BUILT__</div>
  <div class="tabs">
    <button type="button" id="tabMatches" class="on">Faculty matches</button>
    <button type="button" id="tabMissing">Programs not covered (<span id="missTotal">0</span>)</button>
  </div>
</header>
<div id="missingView" class="hidden">
  <div class="controls">
    <input type="search" id="mq" placeholder="Search institution, department, state...">
    <select id="mtype">
      <option value="">Reason: all</option>
      <option value="crawl_failed">Broken (site couldn't be scraped)</option>
      <option value="excluded">Not searched (PsyD / School / other)</option>
    </select>
    <span class="sub"><span id="missShown">0</span> shown</span>
  </div>
  <main>
    <p class="note">APA lists 442 accredited doctoral programs. Only Clinical, Counseling, School and combined
      <b>PhD</b> programs were searched (PsyD programs skipped). "Broken" means the program was in scope but its
      site blocked the scraper or no faculty list was found &mdash; check those by hand.</p>
    <div class="tbl-wrap"><table class="miss">
      <thead><tr><th>Institution</th><th>Department</th><th>State</th><th>Area</th><th>Degree</th><th>Reason</th></tr></thead>
      <tbody id="missBody"></tbody>
    </table></div>
  </main>
</div>
<div id="matchesView">
<div class="controls">
  <input type="search" id="q" placeholder="Search name, institution, terms, evidence...">
  <select id="acc">
    <option value="">Accepting: all</option>
    <option value="accepting">Accepting</option>
    <option value="unknown">Unknown</option>
    <option value="not_accepting">Not accepting</option>
  </select>
  <select id="area"><option value="">Program area: all</option></select>
  <select id="state"><option value="">State: all</option></select>
  <select id="sort">
    <option value="default">Sort: default</option>
    <option value="score">Topic score (high first)</option>
    <option value="name">Name</option>
    <option value="institution">Institution</option>
    <option value="state">State</option>
  </select>
  <label class="cb"><input type="checkbox" id="cycle"> Fall 2027 only</label>
  <label class="cb"><input type="checkbox" id="youth"> Youth focus only</label>
  <label class="cb"><input type="checkbox" id="slOnly"> Shortlisted only</label>
  <div class="chips" id="catChips"></div>
  <button id="export">Export shortlist CSV</button>
  <button id="reset">Reset filters</button>
</div>
<main id="list"></main>
</div>

<script id="data" type="application/json">__DATA__</script>
<script id="missing" type="application/json">__MISSING__</script>
<script>
(function () {
  "use strict";
  var DATA = JSON.parse(document.getElementById("data").textContent || "[]");
  var CATS = {
    adverse_childhood_experiences: "ACEs / Adverse childhood",
    juvenile_delinquency: "Juvenile delinquency",
    antisocial_conduct: "Antisocial / conduct",
    recidivism_prevention: "Recidivism / prevention",
    household_dysfunction: "Household dysfunction",
    emotion_regulation: "Emotion regulation",
    self_concept_clarity: "Self-concept clarity"
  };
  var ACC_LABEL = { accepting: "Accepting", unknown: "Unknown", not_accepting: "Not accepting" };
  var LS_KEY = "facultyShortlist.v1";

  function esc(v) {
    return String(v == null ? "" : v).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function safeUrl(u) {
    u = String(u || "").trim();
    return /^https?:\/\//i.test(u) ? u : "";
  }
  function catLabel(c) { return CATS[c] || String(c).replace(/_/g, " "); }
  function acc(r) { return (r.accepting && r.accepting.status) || "unknown"; }
  function keyOf(r) { return r.profile_url || (r.name + "|" + r.institution); }

  // Precompute
  DATA.forEach(function (r, i) {
    r._i = i;
    var terms = [];
    var mt = r.matched_terms || {};
    Object.keys(mt).forEach(function (k) { terms = terms.concat(mt[k] || []); });
    r._hay = [r.name, r.institution, r.department, r.program_area, r.state,
      (r.topic_categories || []).map(catLabel).join(" "), terms.join(" "),
      (r.evidence || []).join(" "), r.accepting && r.accepting.evidence].join(" ").toLowerCase();
  });

  // Shortlist storage
  var shortlist = {};
  try { shortlist = JSON.parse(localStorage.getItem(LS_KEY) || "{}") || {}; } catch (e) { shortlist = {}; }
  function saveShortlist() { try { localStorage.setItem(LS_KEY, JSON.stringify(shortlist)); } catch (e) {} }

  var $ = function (id) { return document.getElementById(id); };
  var activeCats = {};

  // Populate dropdowns
  function fillSelect(sel, values) {
    values.forEach(function (v) {
      var o = document.createElement("option"); o.value = v; o.textContent = v; sel.appendChild(o);
    });
  }
  function uniq(field) {
    var s = {};
    DATA.forEach(function (r) { if (r[field]) s[r[field]] = 1; });
    return Object.keys(s).sort();
  }
  fillSelect($("area"), uniq("program_area"));
  fillSelect($("state"), uniq("state"));

  var catKeys = Object.keys(CATS);
  DATA.forEach(function (r) {
    (r.topic_categories || []).forEach(function (c) { if (catKeys.indexOf(c) < 0) catKeys.push(c); });
  });
  catKeys.forEach(function (c) {
    var b = document.createElement("button");
    b.className = "chip"; b.type = "button"; b.textContent = catLabel(c); b.dataset.cat = c;
    b.title = "Show rows tagged with any selected category";
    b.addEventListener("click", function () {
      activeCats[c] = !activeCats[c]; b.classList.toggle("on", !!activeCats[c]); render();
    });
    $("catChips").appendChild(b);
  });

  function filtered() {
    var q = $("q").value.trim().toLowerCase().split(/\s+/).filter(Boolean);
    var a = $("acc").value, area = $("area").value, st = $("state").value;
    var cyc = $("cycle").checked, youth = $("youth").checked, sl = $("slOnly").checked;
    var cats = Object.keys(activeCats).filter(function (k) { return activeCats[k]; });
    var out = DATA.filter(function (r) {
      if (a && acc(r) !== a) return false;
      if (area && r.program_area !== area) return false;
      if (st && r.state !== st) return false;
      if (cyc && !(r.accepting && r.accepting.current_cycle)) return false;
      if (youth && !r.youth_focus) return false;
      if (sl && !shortlist[keyOf(r)]) return false;
      if (cats.length && !cats.some(function (c) { return (r.topic_categories || []).indexOf(c) >= 0; })) return false;
      for (var i = 0; i < q.length; i++) if (r._hay.indexOf(q[i]) < 0) return false;
      return true;
    });
    var s = $("sort").value;
    var str = function (f) { return function (x, y) {
      return String(x[f] || "").localeCompare(String(y[f] || "")) || x._i - y._i; }; };
    if (s === "score") out.sort(function (x, y) { return (y.topic_score || 0) - (x.topic_score || 0) || x._i - y._i; });
    else if (s === "name") out.sort(str("name"));
    else if (s === "institution") out.sort(str("institution"));
    else if (s === "state") out.sort(str("state"));
    return out;
  }

  function card(r) {
    var k = keyOf(r), on = !!shortlist[k], st = acc(r), A = r.accepting || {};
    var prof = safeUrl(r.profile_url), web = safeUrl(r.program_website);
    var h = '<div class="card"><div class="top">';
    h += '<button class="star' + (on ? " on" : "") + '" data-key="' + esc(k) + '" title="Toggle shortlist" aria-label="Toggle shortlist">' + (on ? "&#9733;" : "&#9734;") + "</button>";
    h += '<div class="main"><div class="name">' + (prof ? '<a href="' + esc(prof) + '" target="_blank" rel="noopener">' + esc(r.name) + "</a>" : esc(r.name)) + "</div>";
    h += '<div class="sub">' + esc(r.institution) + (r.department ? " &middot; " + esc(r.department) : "") + (r.state ? " &middot; " + esc(r.state) : "") + "</div>";
    h += '<div class="meta"><span class="badge b-' + esc(st) + '">' + esc(ACC_LABEL[st] || st) + (A.current_cycle ? " &middot; Fall 2027" : "") + "</span>";
    if (r.program_area) h += '<span class="sub">' + esc(r.program_area) + "</span>";
    if (r.youth_focus) h += '<span class="chip">youth focus</span>';
    (r.topic_categories || []).forEach(function (c) { h += '<span class="chip">' + esc(catLabel(c)) + "</span>"; });
    h += "</div>";
    var mt = r.matched_terms || {}, parts = [];
    Object.keys(mt).forEach(function (c) {
      if ((mt[c] || []).length) parts.push('<span class="cat">' + esc(catLabel(c)) + ":</span> " + esc(mt[c].join(", ")));
    });
    if (parts.length) h += '<div class="terms">' + parts.join(" &nbsp;|&nbsp; ") + "</div>";
    h += "<details><summary>Evidence &amp; details</summary>";
    if (A.evidence) h += '<div class="ev-acc"><b>Accepting evidence:</b> ' + esc(A.evidence) + "</div>";
    if (A.page_mentions_2027) h += '<div class="sub">Page mentions 2027.</div>';
    var ev = r.evidence || [];
    if (ev.length) h += '<ul class="ev">' + ev.map(function (e) { return "<li>" + esc(e) + "</li>"; }).join("") + "</ul>";
    if (web) h += '<div>Program website: <a href="' + esc(web) + '" target="_blank" rel="noopener">' + esc(web) + "</a></div>";
    var named = (r.named_on_program_accepting_page || []).map(safeUrl).filter(Boolean);
    if (named.length) h += "<div>Named on program accepting page: " + named.map(function (u) {
      return '<a href="' + esc(u) + '" target="_blank" rel="noopener">' + esc(u) + "</a>"; }).join(", ") + "</div>";
    if (r.apa_program_number != null) h += '<div class="sub">APA program #' + esc(r.apa_program_number) + "</div>";
    h += "</details></div>";
    h += '<div class="score"><b>' + esc(r.topic_score) + '</b> score<br>' + esc(r.core_terms) + " core terms</div>";
    h += "</div></div>";
    return h;
  }

  function render() {
    var rows = filtered();
    $("total").textContent = DATA.length;
    $("shown").textContent = rows.length;
    $("slCount").textContent = Object.keys(shortlist).length;
    $("list").innerHTML = rows.length ? rows.map(card).join("") : '<div class="empty">No matches.</div>';
  }

  $("list").addEventListener("click", function (e) {
    var b = e.target.closest("button.star");
    if (!b) return;
    var k = b.dataset.key;
    if (shortlist[k]) delete shortlist[k]; else shortlist[k] = Date.now();
    saveShortlist(); render();
  });

  ["q", "acc", "area", "state", "sort", "cycle", "youth", "slOnly"].forEach(function (id) {
    $(id).addEventListener(id === "q" ? "input" : "change", render);
  });
  $("reset").addEventListener("click", function () {
    $("q").value = ""; ["acc", "area", "state"].forEach(function (id) { $(id).value = ""; });
    $("sort").value = "default"; ["cycle", "youth", "slOnly"].forEach(function (id) { $(id).checked = false; });
    activeCats = {}; document.querySelectorAll("#catChips .chip").forEach(function (b) { b.classList.remove("on"); });
    render();
  });

  function csvCell(v) {
    var s = String(v == null ? "" : v);
    if (/^[=+\-@]/.test(s)) s = "'" + s; // avoid spreadsheet formula injection
    return '"' + s.replace(/"/g, '""') + '"';
  }
  $("export").addEventListener("click", function () {
    var rows = DATA.filter(function (r) { return shortlist[keyOf(r)]; });
    if (!rows.length) { alert("Shortlist is empty."); return; }
    var head = ["name", "institution", "department", "state", "program_area", "accepting_status",
      "fall_2027", "youth_focus", "topic_score", "core_terms", "topic_categories", "matched_terms",
      "profile_url", "program_website", "accepting_evidence"];
    var lines = [head.join(",")];
    rows.forEach(function (r) {
      var A = r.accepting || {}, mt = r.matched_terms || {};
      var terms = Object.keys(mt).map(function (c) { return (mt[c] || []).join("; "); }).filter(Boolean).join("; ");
      lines.push([r.name, r.institution, r.department, r.state, r.program_area, acc(r),
        A.current_cycle ? "yes" : "no", r.youth_focus ? "yes" : "no", r.topic_score, r.core_terms,
        (r.topic_categories || []).map(catLabel).join("; "), terms, r.profile_url, r.program_website,
        A.evidence].map(csvCell).join(","));
    });
    var blob = new Blob(["\ufeff" + lines.join("\r\n")], { type: "text/csv;charset=utf-8" });
    var a = document.createElement("a");
    a.href = URL.createObjectURL(blob); a.download = "faculty_shortlist.csv";
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(function () { URL.revokeObjectURL(a.href); }, 1000);
  });

  // Programs not covered tab
  var MISSING = JSON.parse(document.getElementById("missing").textContent || "[]");
  var TYPE_LABEL = { excluded: "Not searched", crawl_failed: "Broken" };
  $("missTotal").textContent = MISSING.length;
  function renderMissing() {
    var q = $("mq").value.trim().toLowerCase().split(/\s+/).filter(Boolean), t = $("mtype").value;
    var rows = MISSING.filter(function (m) {
      if (t && m.reason_type !== t) return false;
      var hay = [m.institution, m.department, m.city, m.state, m.area, m.degree, m.reason].join(" ").toLowerCase();
      for (var i = 0; i < q.length; i++) if (hay.indexOf(q[i]) < 0) return false;
      return true;
    });
    rows.sort(function (x, y) {
      return (x.reason_type === y.reason_type ? 0 : x.reason_type === "crawl_failed" ? -1 : 1) ||
        String(x.state).localeCompare(String(y.state)) || String(x.institution).localeCompare(String(y.institution));
    });
    $("missShown").textContent = rows.length;
    $("missBody").innerHTML = rows.map(function (m) {
      var web = safeUrl(m.website);
      return "<tr><td>" + (web ? '<a href="' + esc(web) + '" target="_blank" rel="noopener">' + esc(m.institution) + "</a>" : esc(m.institution)) +
        "</td><td>" + esc(m.department) + "</td><td>" + esc(m.state) + "</td><td>" + esc(m.area) +
        "</td><td>" + esc(m.degree) + '</td><td><span class="badge b-' + esc(m.reason_type) + '">' +
        esc(TYPE_LABEL[m.reason_type] || m.reason_type) + '</span> <span class="sub">' +
        esc(m.reason.replace(/^[^:]*:\s*/, "")) + "</span></td></tr>";
    }).join("") || '<tr><td colspan="6" class="empty">No programs.</td></tr>';
  }
  $("mq").addEventListener("input", renderMissing);
  $("mtype").addEventListener("change", renderMissing);
  function showTab(missing) {
    $("missingView").classList.toggle("hidden", !missing);
    $("matchesView").classList.toggle("hidden", missing);
    $("tabMissing").classList.toggle("on", missing);
    $("tabMatches").classList.toggle("on", !missing);
  }
  $("tabMatches").addEventListener("click", function () { showTab(false); });
  $("tabMissing").addEventListener("click", function () { showTab(true); });

  render();
  renderMissing();
})();
</script>
</body>
</html>
"""


def main():
    data = json.loads(SRC.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise SystemExit(f"Expected a JSON array in {SRC}")
    miss_path = SRC.parent / "missing_programs.json"   # from `python scrape.py missing`
    missing = json.loads(miss_path.read_text(encoding="utf-8")) if miss_path.exists() else []
    html = (TEMPLATE.replace("__BUILT__", datetime.now().strftime("%Y-%m-%d %H:%M"))
                    .replace("__MISSING__", embed_json(missing))
                    .replace("__DATA__", embed_json(data)))
    OUT.write_text(html, encoding="utf-8")
    print(f"Wrote {OUT} ({len(data)} rows, {len(missing)} missing programs, {OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
