"""
Download raw HTML + PDF for each indexed MPC document
(resolution, governor's statement, minutes only — see KEEP below).

Requires data/raw/mpc_document_index.csv to exist already (run scraper.py first).

Run from anywhere:
    python src/download.py
    (or)  cd src && python download.py

Output:
    data/raw/html/*.html
    data/raw/pdf/*.pdf
    data/raw/download_manifest.csv
"""
import re
import time

import pandas as pd
import requests
from bs4 import BeautifulSoup

try:
    from paths import DOC_INDEX_CSV, DOWNLOAD_MANIFEST_CSV, HTML_DIR, PDF_DIR
    from scraper import HEADERS, BASE
except ImportError:
    from src.paths import DOC_INDEX_CSV, DOWNLOAD_MANIFEST_CSV, HTML_DIR, PDF_DIR
    from src.scraper import HEADERS, BASE

KEEP = {"resolution", "governor_statement", "minutes"}


def safe(s):
    return re.sub(r"[^A-Za-z0-9_-]+", "_", str(s)).strip("_")[:80]


def main():
    if not DOC_INDEX_CSV.exists():
        raise FileNotFoundError(
            f"{DOC_INDEX_CSV} not found — run `python src/scraper.py` first."
        )

    df = pd.read_csv(DOC_INDEX_CSV)
    df = df[df["doc_type"].isin(KEEP)].copy()

    s = requests.Session()
    manifest = []

    for _, row in df.iterrows():
        stem = f"{safe(row.listed_date)}_{row.doc_type}_{row.prid}"
        hpath = HTML_DIR / f"{stem}.html"

        if not hpath.exists():
            r = s.get(row.url, headers=HEADERS, timeout=45)
            r.raise_for_status()
            hpath.write_text(r.text, encoding="utf-8")
            time.sleep(1.5)

        html = hpath.read_text(encoding="utf-8")
        soup = BeautifulSoup(html, "lxml")

        pdf_url, ppath = None, None
        for a in soup.find_all("a", href=True):
            if ".PDF" in a["href"].upper() and "rbidocs" in a["href"].lower():
                pdf_url = a["href"] if a["href"].startswith("http") else BASE + a["href"]
                break

        if pdf_url:
            ppath = PDF_DIR / f"{stem}.pdf"
            if not ppath.exists():
                pr = s.get(pdf_url, headers=HEADERS, timeout=60)
                if pr.ok and pr.content[:4] == b"%PDF":
                    ppath.write_bytes(pr.content)
                else:
                    ppath = None
                time.sleep(1.5)

        manifest.append({
            **row.to_dict(),
            "html_path": str(hpath),
            "pdf_path": str(ppath) if ppath else None,
        })
        print("ok", stem)

    pd.DataFrame(manifest).to_csv(DOWNLOAD_MANIFEST_CSV, index=False)
    print(f"\nSaved manifest -> {DOWNLOAD_MANIFEST_CSV}")


if __name__ == "__main__":
    main()
