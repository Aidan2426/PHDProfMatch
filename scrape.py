"""
Scrape APA-accredited Clinical / Counseling Psychology PhD programs, crawl each
program's website for faculty, and flag faculty whose pages mention research on
ACEs, juvenile delinquency, antisocial / conduct problems, youth behavior
problems, or juvenile recidivism prevention. Also tries to detect whether each
faculty member says they're accepting students for Fall 2027.

Usage:
    python scrape.py programs                 # step 1 -> data/programs.json
    python scrape.py faculty                  # step 2 -> data/faculty_matches.json
    python scrape.py faculty --limit 5        # quick test on first 5 programs
    python scrape.py faculty --browser        # re-crawl weak programs w/ Playwright
    python scrape.py faculty --only 158,217   # specific APA program numbers

HTML is cached in ./cache so reruns are cheap. Delete cache/ to refetch.
"""
import argparse
import hashlib
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urljoin, urldefrag, urlparse

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).parent
DATA = ROOT / "data"
CACHE = ROOT / "cache"
DATA.mkdir(exist_ok=True)
CACHE.mkdir(exist_ok=True)

APA = "https://accredited-programs-services.apa.org/accredited-search"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")
HEADERS = {"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"}
APA_HEADERS = {**HEADERS, "Origin": "https://apps.apa.org", "Referer": "https://apps.apa.org/"}

AREAS = ["Clinical Psychology", "Counseling Psychology",
         "Combined, Clinical-Counseling Psychology",
         "Combined, Clinical-Counseling-School Psychology",
         "Combined, Clinical-School Psychology",
         "Combined, Counseling-School Psychology"]

MAX_LISTING_PAGES = 6      # faculty/people pages per program
MAX_PROFILES = 120         # profile pages per program
TIMEOUT = 20

# --------------------------------------------------------------------------
# Research-topic keywords. Each category -> {"core": [...], "broad": [...]}.
# A faculty member is kept if they hit >=1 core term OR >=2 distinct broad terms.
# Tweak freely.
# --------------------------------------------------------------------------
TOPICS = {
    "adverse_childhood_experiences": {
        "core": [r"adverse childhood experiences?", r"childhood adversit(y|ies)", r"early (life )?adversity",
                 r"child(hood)? (maltreatment|abuse|neglect)", r"polyvictimization"],
        "broad": [r"child(hood)? trauma", r"early (life )?trauma", r"foster care", r"child welfare"],
    },
    "juvenile_delinquency": {
        "core": [r"delinquen\w*", r"juvenile (justice|offend\w*|detention|court|crime|correction\w*)",
                 r"justice[- ]involved (youth|adolescents|juveniles|children)", r"youth(ful)? offend\w*",
                 r"young offenders?", r"adolescent offend\w*", r"(school|youth) violence",
                 r"gang (involvement|membership|violence|members?)", r"school[- ]to[- ]prison"],
        "broad": [],
    },
    "antisocial_conduct": {
        "core": [r"antisocial", r"conduct (problems?|disorders?)", r"callous[- ]unemotional",
                 r"psychopath(y|ic|s)?", r"oppositional defiant", r"disruptive behaviou?rs?"],
        "broad": [r"externaliz\w*", r"aggressi(on|ve behaviou?rs?)", r"bullying"],
    },
    "recidivism_prevention": {
        "core": [r"recidivism", r"re-?offend\w*", r"diversion programs?", r"multisystemic therapy",
                 r"functional family therapy", r"(youth )?violence prevention", r"(crime|delinquency) prevention"],
        "broad": [r"risk assessment", r"forensic", r"reentry", r"incarcerat\w*"],
    },
}
ACES_CASE = re.compile(r"\bACEs\b")  # case-sensitive so "aces" doesn't match
TOPIC_RX = {cat: [(re.compile(r"\b" + p + r"\b", re.I), tier) for tier in ("core", "broad") for p in v[tier]]
            for cat, v in TOPICS.items()}
YOUTH = re.compile(r"\b(youth|child\w*|adolescen\w*|juvenile\w*|teen\w*|kids)\b", re.I)
NOT_NAME = re.compile(
    r"\b(students?|programs?|psychology|university|about|graduate|course|courses|clinical|explore|quick|"
    r"links?|title|emergency|research|department|center|centre|lab|labs|science|sciences|development|"
    r"faculty|staff|people|directory|news|events?|admissions?|home|contact|apply|degree|office|services?|"
    r"concentration|overview|areas?|care|resources?|catalog|majors?|minors?|academic|welcome|page|not found|"
    r"learn|more|health|violence|behaviou?r|analysis|connected|disparities|initiatives?|institute|clinic|"
    r"college|school|schools|training|requirements|policies|giving|alumni|calendar|history)\b", re.I)
PERSON_PAGE = re.compile(r"\b(professor|ph\.?\s?d|psy\.?\s?d|lecturer|faculty member|principal investigator)\b", re.I)

# Accepting-students language
ACCEPT_YES = re.compile(
    r"(is|are|will|plans? to|anticipates?|expects?|intends? to|currently|actively)\s+(be\s+)?"
    r"(accepting|recruiting|reviewing applications|taking|admitting|considering)\b[^.]{0,80}"
    r"(students?|applicants?|applications|mentees)"
    r"|accepting (new )?(graduate |doctoral |phd )?students"
    r"|recruiting (a |new )?(graduate |doctoral |phd )?students?", re.I)
ACCEPT_NO = re.compile(
    r"(not|no longer)\s+(currently\s+|be\s+|actively\s+)*(accepting|recruiting|taking|admitting|reviewing)[^.]{0,60}"
    r"(students?|applicants?|applications)", re.I)
YEAR = re.compile(r"\b(2027|2026[-–/]\s?(20)?27|fall\s+2027)\b", re.I)
# relative phrasing; as of Oct 2026 "coming year" = the Fall 2027 entry cycle
CURRENT_CYCLE = re.compile(r"\b(2027|2026[-–/]\s?(20)?27|coming (academic |admissions? )?(year|cycle)|"
                           r"upcoming (academic |admissions? |application )?(year|cycle)|next (academic )?year|"
                           r"this (admissions? |application )?cycle)\b", re.I)

FACULTY_LINK = re.compile(
    r"faculty|people|directory|our[- ]team|mentors?|core[- ]faculty|research[- ]labs?|"
    r"accepting|admissions?|prospective", re.I)
PROFILE_HREF = re.compile(
    r"/(people|faculty|profiles?|directory|person|staff|experts?|faculty-staff|our-people|"
    r"bio|team|members?)/[^/?#]+", re.I)
NAME_TEXT = re.compile(r"^(Dr\.?\s+)?[A-Z][\w'’.-]+(\s+[A-Z][\w'’.-]*\.?){1,3}(,\s*(Ph\.?D|Psy\.?D)\.?)?$")
SKIP_EXT = re.compile(r"\.(pdf|docx?|xlsx?|pptx?|jpe?g|png|gif|zip|mp4|mp3)$", re.I)

session = requests.Session()
session.headers.update(HEADERS)


# --------------------------------------------------------------------------
# Fetching (cached)
# --------------------------------------------------------------------------
def _cache_path(url, kind):
    return CACHE / f"{kind}_{hashlib.sha1(url.encode()).hexdigest()}.html"


def fetch_requests(url):
    p = _cache_path(url, "r")
    if p.exists():
        return p.read_text(encoding="utf-8", errors="ignore")
    try:
        r = session.get(url, timeout=TIMEOUT, allow_redirects=True)
        ctype = r.headers.get("content-type", "")
        html = r.text if r.ok and "html" in ctype else ""
    except requests.RequestException:
        html = ""
    p.write_text(html, encoding="utf-8")
    return html


class BrowserFetcher:
    """Playwright fallback for JS-rendered or bot-blocked sites. Single-threaded."""

    def __init__(self):
        from playwright.sync_api import sync_playwright
        self._pw = sync_playwright().start()
        self._b = self._pw.chromium.launch()
        self._pg = self._b.new_context(user_agent=UA).new_page()

    def __call__(self, url):
        p = _cache_path(url, "b")
        if p.exists():
            return p.read_text(encoding="utf-8", errors="ignore")
        try:
            self._pg.goto(url, wait_until="domcontentloaded", timeout=30000)
            self._pg.wait_for_timeout(2500)
            html = self._pg.content()
        except Exception:
            html = ""
        p.write_text(html, encoding="utf-8")
        return html

    def close(self):
        self._b.close()
        self._pw.stop()


# --------------------------------------------------------------------------
# Step 1: APA programs
# --------------------------------------------------------------------------
def scrape_programs():
    seen, programs = set(), []
    for area in AREAS:
        r = requests.post(f"{APA}/search", headers=APA_HEADERS, json={
            "programLevel": "Doctoral", "states": [], "option1": [area],
            "option2": ["Ph.D."], "keyword": ""})
        r.raise_for_status()
        rows = r.json()
        print(f"{area}: {len(rows)}")
        for row in rows:
            n = row["apaProgramNumber"]
            if n in seen:
                continue
            seen.add(n)
            d = requests.get(f"{APA}/details/{n}", headers=APA_HEADERS).json()
            programs.append({
                "apa_program_number": n,
                "institution": d.get("InstitutionName"),
                "city": d.get("InstitutionCity"),
                "state": d.get("InstitutionState"),
                "department": (d.get("ProgramDepartment") or "").strip(),
                "degree": d.get("ProgramDegree"),
                "area": d.get("SubstantiveArea"),
                "setting": d.get("SettingType"),
                "accreditation_status": d.get("CurrentAccredStatus"),
                "website": d.get("WebsiteURL"),
                "outcomes_data_url": d.get("DocC20URL"),
            })
            time.sleep(0.1)
    out = DATA / "programs.json"
    out.write_text(json.dumps(programs, indent=2), encoding="utf-8")
    print(f"Saved {len(programs)} programs -> {out}")


def scrape_missing():
    """List APA doctoral programs not covered by faculty_matches: either filtered out
    (PsyD, School Psych, ...) or searched but the site couldn't be crawled."""
    def search(o1=(), o2=()):
        r = requests.post(f"{APA}/search", headers=APA_HEADERS, json={
            "programLevel": "Doctoral", "states": [], "option1": list(o1), "option2": list(o2), "keyword": ""})
        r.raise_for_status()
        return r.json()

    opts = requests.get(f"{APA}/options", params={"programLevel": "Doctoral"}, headers=APA_HEADERS).json()
    kind = {}  # program number -> (area, degree)
    for area in opts["option1"][1:]:
        for deg in opts["option2"][1:]:
            for row in search([area], [deg]):
                kind[row["apaProgramNumber"]] = (area, deg)

    programs = {p["apa_program_number"]: p for p in json.loads((DATA / "programs.json").read_text(encoding="utf-8"))}
    logs = {l["apa_program_number"]: l for l in json.loads((DATA / "crawl_log.json").read_text(encoding="utf-8"))}

    missing = []
    for row in search():
        n = row["apaProgramNumber"]
        area, deg = kind.get(n, ("Unknown", "Unknown"))
        base = {"apa_program_number": n, "institution": row["institutionName"], "city": row["institutionCity"],
                "state": row["institutionState"], "department": (row["programDepartment"] or "").strip(),
                "area": area, "degree": deg}
        if n not in programs:
            missing.append({**base, "reason_type": "excluded",
                            "reason": f"Not searched: {area} {deg}", "website": None})
            continue
        log = logs.get(n, {})
        if log.get("error") or log.get("profiles_checked", 0) < 5:
            why = log.get("error") or f"only {log.get('profiles_checked', 0)} faculty profiles found"
            missing.append({**base, "reason_type": "crawl_failed",
                            "reason": f"Searched, site not read: {why}", "website": programs[n]["website"]})

    out = DATA / "missing_programs.json"
    out.write_text(json.dumps(missing, indent=2, ensure_ascii=False), encoding="utf-8")
    n_ex = sum(m["reason_type"] == "excluded" for m in missing)
    print(f"{len(missing)} missing ({n_ex} excluded, {len(missing) - n_ex} crawl failed) -> {out}")


# --------------------------------------------------------------------------
# Step 2: faculty crawl
# --------------------------------------------------------------------------
def site_key(url):
    host = urlparse(url).hostname or ""
    parts = host.split(".")
    return ".".join(parts[-2:])


def clean_text(soup):
    for t in soup(["script", "style", "noscript", "svg", "header", "footer", "nav", "form"]):
        t.decompose()
    main = soup.find("main") or soup.find(id=re.compile("content|main", re.I)) or soup.body or soup
    return re.sub(r"\s+", " ", main.get_text(" ", strip=True))


def links(soup, base):
    for a in soup.find_all("a", href=True):
        href = urldefrag(urljoin(base, a["href"].strip()))[0]
        if href.startswith("http") and not SKIP_EXT.search(href):
            yield href, a.get_text(" ", strip=True)


def snippet(text, m, width=160):
    s, e = max(0, m.start() - width), min(len(text), m.end() + width)
    return ("…" if s else "") + text[s:e].strip() + ("…" if e < len(text) else "")


def match_topics(text):
    """Returns (hits {cat: {term: snippet}}, n_core_patterns, n_broad_patterns)."""
    hits, core, broad = {}, 0, 0
    for cat, rxs in TOPIC_RX.items():
        for rx, tier in rxs:
            ms = list(rx.finditer(text))
            if not ms:
                continue
            core += tier == "core"
            broad += tier == "broad"
            for m in ms:
                hits.setdefault(cat, {}).setdefault(m.group(0).lower(), snippet(text, m))
    m = ACES_CASE.search(text)
    if m:
        core += 1
        hits.setdefault("adverse_childhood_experiences", {}).setdefault("ACEs", snippet(text, m))
    return hits, core, broad


def accepting_status(text):
    no = ACCEPT_NO.search(text)
    yes = ACCEPT_YES.search(text)
    status, ev = "unknown", None
    if no:
        status, ev = "not_accepting", snippet(text, no, 120)
    elif yes:
        status, ev = "accepting", snippet(text, yes, 120)
    return {"status": status, "evidence": ev,
            "current_cycle": bool(ev and CURRENT_CYCLE.search(ev)),   # statement refers to Fall 2027 cycle
            "page_mentions_2027": bool(YEAR.search(text))}


def is_name(t):
    t = re.sub(r"\s+", " ", t or "").strip()
    return 3 < len(t) < 60 and not t.isupper() and bool(NAME_TEXT.match(t)) and not NOT_NAME.search(t)


def page_name(soup, anchor):
    """Person's name from h1/h2/title/link text, or None if page isn't a person."""
    cands = [h.get_text(" ", strip=True) for h in soup.find_all(["h1", "h2"], limit=4)]
    if soup.title:
        cands.append(re.split(r"\s+[|\-–—:]\s+", soup.title.get_text(strip=True))[0])
    cands.append(anchor)
    for t in cands:
        if is_name(t):
            return re.sub(r"\s+", " ", t).strip()
    return None


def crawl_program(prog, fetch):
    start = prog.get("website")
    log = {"apa_program_number": prog["apa_program_number"], "start": start,
           "listing_pages": [], "profiles_checked": 0, "error": None}
    if not start:
        log["error"] = "no website"
        return [], log
    if not start.startswith("http"):
        start = "https://" + start
    key = site_key(start)

    html = fetch(start)
    if not html:
        log["error"] = "start page fetch failed"
        return [], log
    soup = BeautifulSoup(html, "lxml")

    # 1) Candidate faculty / people / accepting pages (start page + 1 hop)
    cands = {start: 0}
    for href, txt in links(soup, start):
        if site_key(href) != key:
            continue
        score = 2 * bool(FACULTY_LINK.search(txt)) + bool(FACULTY_LINK.search(urlparse(href).path))
        if re.search(r"accepting", txt + href, re.I):
            score += 3
        if score:
            cands[href] = max(cands.get(href, 0), score)
    listing = [u for u, _ in sorted(cands.items(), key=lambda kv: -kv[1])][:MAX_LISTING_PAGES]

    profiles = {}          # url -> anchor text
    program_level = []     # accepting-list pages
    results = {}
    seen_names = set()
    for url in listing:
        h = html if url == start else fetch(url)
        if not h:
            continue
        log["listing_pages"].append(url)
        s = BeautifulSoup(h, "lxml")
        anchors = list(links(s, url))
        text = clean_text(BeautifulSoup(h, "lxml"))
        if YEAR.search(text) and re.search(r"accepting|recruiting", text, re.I):
            program_level.append({"url": url, "evidence": snippet(text, YEAR.search(text), 300)})
        for href, txt in anchors:
            if site_key(href) != key or href in cands:
                continue
            if PROFILE_HREF.search(urlparse(href).path) or NAME_TEXT.match(txt or ""):
                if NAME_TEXT.match(txt or "") or len(txt) < 60:
                    profiles.setdefault(href, txt)

    # 2) Visit profiles, match topics
    for url, anchor in list(profiles.items())[:MAX_PROFILES]:
        h = fetch(url)
        log["profiles_checked"] += 1
        if not h:
            continue
        s = BeautifulSoup(h, "lxml")
        name = page_name(s, anchor)
        if not name:
            continue
        text = clean_text(s)
        if len(text) < 150 or not PERSON_PAGE.search(text):
            continue
        hits, n_core, n_broad = match_topics(text)
        if not (n_core >= 1 or n_broad >= 2):
            continue
        key_ = name.lower()
        if key_ in seen_names:
            continue
        seen_names.add(key_)
        acc = accepting_status(text)
        # cross-reference program-level "accepting" pages for this person's last name
        last = name.replace(",", " ").split()[-1] if name.split() else ""
        listed = [p["url"] for p in program_level
                  if last and len(last) > 2 and last.lower() in clean_text(BeautifulSoup(fetch(p["url"]), "lxml")).lower()]
        results[url] = {
            "name": name,
            "profile_url": url,
            "institution": prog["institution"],
            "department": prog["department"],
            "program_area": prog["area"],
            "state": prog["state"],
            "apa_program_number": prog["apa_program_number"],
            "program_website": prog["website"],
            "topic_categories": sorted(hits),
            "topic_score": 3 * n_core + n_broad,
            "core_terms": n_core,
            "youth_focus": len(YOUTH.findall(text)) >= 3,
            "matched_terms": {k: sorted(v) for k, v in hits.items()},
            "evidence": [v2 for v in hits.values() for v2 in list(v.values())[:2]][:6],
            "accepting": acc,
            "named_on_program_accepting_page": listed,
        }
    log["program_accepting_pages"] = [p["url"] for p in program_level]
    return list(results.values()), log


def run_faculty(limit=None, only=None, browser=False, workers=12):
    programs = json.loads((DATA / "programs.json").read_text(encoding="utf-8"))
    if only:
        programs = [p for p in programs if p["apa_program_number"] in only]
    if limit:
        programs = programs[:limit]

    all_hits, logs = [], []
    with ThreadPoolExecutor(workers) as ex:
        futs = {ex.submit(crawl_program, p, fetch_requests): p for p in programs}
        for i, f in enumerate(as_completed(futs), 1):
            p = futs[f]
            try:
                hits, log = f.result()
            except Exception as e:
                hits, log = [], {"apa_program_number": p["apa_program_number"], "error": repr(e)}
            all_hits += hits
            logs.append(log)
            print(f"[{i}/{len(programs)}] {p['institution']} — {len(hits)} matches, "
                  f"{log.get('profiles_checked', 0)} profiles {log.get('error') or ''}", flush=True)

    if browser:
        weak = {l["apa_program_number"] for l in logs if l.get("error") or l.get("profiles_checked", 0) < 5}
        print(f"\nBrowser fallback for {len(weak)} weak programs…")
        bf = BrowserFetcher()
        try:
            for p in programs:
                if p["apa_program_number"] not in weak:
                    continue
                try:
                    hits, log = crawl_program(p, bf)
                except Exception as e:
                    hits, log = [], {"apa_program_number": p["apa_program_number"], "error": repr(e)}
                log["browser"] = True
                all_hits = [h for h in all_hits if h["apa_program_number"] != p["apa_program_number"]] + hits
                logs = [l for l in logs if l["apa_program_number"] != p["apa_program_number"]] + [log]
                print(f"  {p['institution']} — {len(hits)} matches, {log.get('profiles_checked', 0)} profiles")
        finally:
            bf.close()

    # rank: accepting this cycle first, then youth focus, then topic strength
    rank = {"accepting": 0, "unknown": 1, "not_accepting": 2}
    all_hits.sort(key=lambda h: (rank[h["accepting"]["status"]], not h["accepting"]["current_cycle"],
                                 not h["youth_focus"], -h["topic_score"]))
    (DATA / "faculty_matches.json").write_text(json.dumps(all_hits, indent=2, ensure_ascii=False), encoding="utf-8")
    (DATA / "crawl_log.json").write_text(json.dumps(logs, indent=2), encoding="utf-8")
    print(f"\n{len(all_hits)} faculty matches -> data/faculty_matches.json")
    print(f"Crawl log (check programs with errors / 0 profiles) -> data/crawl_log.json")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=["programs", "faculty", "missing"])
    ap.add_argument("--limit", type=int)
    ap.add_argument("--only", type=lambda s: {int(x) for x in s.split(",")})
    ap.add_argument("--browser", action="store_true")
    ap.add_argument("--workers", type=int, default=12)
    a = ap.parse_args()
    if a.step == "programs":
        scrape_programs()
    elif a.step == "missing":
        scrape_missing()
    else:
        run_faculty(a.limit, a.only, a.browser, a.workers)
