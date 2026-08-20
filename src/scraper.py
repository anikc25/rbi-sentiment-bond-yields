"""
Scrape the RBI Monetary Policy page (annualpolicy.aspx) and build an index
of every MPC document (resolution, governor's statement, minutes, etc.)
with its date, type, and source URL.

Mechanism (reverse-engineered from the live page): clicking a year tab
calls a JS function GetYear(year) which sets a hidden field `hdnYear` to
the year and submits a plain postback (empty __EVENTTARGET/__EVENTARGUMENT).
The server reads hdnYear directly and re-renders the page with that year's
content -- no separate AJAX endpoint involved. We replicate that exact POST
for every financial year.

Run from anywhere:
    python src/scraper.py
    (or)  cd src && python scraper.py

Output:
    data/raw/mpc_document_index.csv
"""
import re
import time

import pandas as pd
import requests
from bs4 import BeautifulSoup

try:
    from paths import DOC_INDEX_CSV          # when run as `python scraper.py` from src/
except ImportError:
    from src.paths import DOC_INDEX_CSV      # when run as `python src/scraper.py` from root

BASE = "https://www.rbi.org.in"
POLICY_URL = f"{BASE}/scripts/annualpolicy.aspx"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": POLICY_URL,
}

HIDDEN_FIELDS = [
    "__VIEWSTATE", "__VIEWSTATEGENERATOR",
    "__EVENTVALIDATION", "__VIEWSTATEENCRYPTED",
]

DATE_RE = re.compile(r"^[A-Z][a-z]{2}\s+\d{1,2},\s+\d{4}$")
FY_RE = re.compile(r"^(\d{4})-(\d{4})$")
PRID_RE = re.compile(r"prid=(\d+)", re.I)


def _hidden(soup):
    out = {}
    for name in HIDDEN_FIELDS:
        tag = soup.find("input", {"name": name})
        if tag is not None:
            out[name] = tag.get("value", "")
    return out


def _available_years(soup):
    """FY labels ('2016-2017', ...) RBI's own year-tab links advertise -- informational only."""
    return sorted({a.get_text(strip=True) for a in soup.find_all("a", class_="year_tree")})


def classify(text):
    t = text.lower().replace("\u2019", "'")
    if "minutes of the monetary policy committee" in t:
        return "minutes"
    if "resolution of the monetary policy committee" in t:
        return "resolution"
    if "developmental and regulatory policies" in t:
        return "devreg"
    if "transcript" in t:
        return "transcript"
    if "governor's statement" in t or "governor's opening statement" in t:
        return "governor_statement"
    # pre-2020 statements were titled "Statement by <Governor's Name>, Governor, ..."
    if t.startswith("statement by") and "governor" in t:
        return "governor_statement"
    return "other"


def parse_page(soup, year_label):
    """Walk the page in document order, tracking the last-seen date and heading."""
    content = soup.find("div", {"id": "pgContent"}) or soup.body or soup
    rows, cur_date, cur_head = [], None, None

    for node in content.descendants:
        if isinstance(node, str):
            if node.parent is not None and node.parent.name == "a":
                continue
            t = node.strip()
            if not t:
                continue
            if DATE_RE.match(t):
                cur_date = t
            else:
                cur_head = t
        elif getattr(node, "name", None) == "a":
            href = node.get("href", "") or ""
            m = PRID_RE.search(href)
            if not m:
                continue
            link_text = node.get_text(strip=True)
            label = link_text if link_text.lower() != "full document" else (cur_head or "")
            rows.append({
                "fin_year": year_label,
                "listed_date": cur_date,
                "title": label,
                "doc_type": classify(label),
                "prid": m.group(1),
                "url": href if href.startswith("http") else BASE + "/" + href.lstrip("/"),
            })
    return rows


def fetch_year(session, fy_label):
    """Replay the hdnYear postback for one financial year label; return its soup."""
    m = FY_RE.match(fy_label)
    if not m:
        raise ValueError(f"Unexpected FY label: {fy_label!r}")
    hdn_year = m.group(2)   # "2016-2017" -> "2017" (matches the id="2017" on RBI's own link)

    # fresh GET first so __VIEWSTATE / __EVENTVALIDATION are always current for this POST
    r = session.get(POLICY_URL, headers=HEADERS, timeout=30)
    r.raise_for_status()
    base_soup = BeautifulSoup(r.text, "lxml")

    payload = _hidden(base_soup)
    payload["__EVENTTARGET"] = ""
    payload["__EVENTARGUMENT"] = ""
    payload["hdnYear"] = hdn_year
    payload["UsrFontCntr$txtSearch"] = ""
    payload["UsrFontCntr$btn"] = ""

    r2 = session.post(POLICY_URL, data=payload, headers=HEADERS, timeout=30)
    r2.raise_for_status()
    return BeautifulSoup(r2.text, "lxml")


def scrape_index(years=None, pause=2.0):
    s = requests.Session()
    r = s.get(POLICY_URL, headers=HEADERS, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")

    advertised = _available_years(soup)
    print(f"Year tabs found on page: {advertised}")
    years = years or advertised

    all_rows = []
    for yl in years:
        try:
            soup_y = fetch_year(s, yl)
        except Exception as e:
            print(f"  !! {yl} failed: {e}")
            continue
        rows = parse_page(soup_y, yl)
        print(f"  {yl}: {len(rows)} document links")
        all_rows += rows
        time.sleep(pause)

    df = pd.DataFrame(all_rows).drop_duplicates(subset=["prid"])
    return df.sort_values("prid").reset_index(drop=True)


if __name__ == "__main__":
    years = [f"{y}-{y+1}" for y in range(2016, 2027)]
    df = scrape_index(years)
    df.to_csv(DOC_INDEX_CSV, index=False)
    print(f"\nSaved {len(df)} rows -> {DOC_INDEX_CSV}")
    print(df["doc_type"].value_counts())
