"""
Shared helpers for Phase 2: extracting and cleaning text from the downloaded
RBI PDFs (primary source) with an HTML fallback for a small number of
documents where the downloaded PDF turned out to be the wrong file.

Design notes (from inspecting real samples across 2016-2026 in
02_text_cleaning.ipynb):
- PDF is the primary source: much less boilerplate than the HTML pages,
  which carry RBI's entire site navigation menu (~280 lines) before content.
- Header anchor: RBI's phone number format changed at least 3 times across
  the decade (022-2266-0502 / 91 22 2266 0502 / 022 2261 0835), so it's not
  reliable alone. helpdoc@rbi.org.in is identical in every sample seen and is
  the primary anchor; phone is kept as a secondary check since the two anchors
  appear in different orders in different eras (whichever ends LATEST wins).
- Footer anchor: "Press Release: YYYY-YYYY/NNN" (RBI's internal filing number)
  is stable across every signatory (Yogesh Dayal, Puneet Pancholy, etc.)
- Known bad PDFs: 5 documents where the downloaded PDF is provably the wrong
  file (confirmed by content inspection -- e.g. prid 36654 downloaded RBI's
  generic "Vision and Values" brochure instead of the actual governor's
  statement, because that page genuinely has no document-specific PDF, only
  site-wide boilerplate PDF links). For these we fall back to the HTML page.
"""
import re

import pdfplumber
from bs4 import BeautifulSoup

# Confirmed by content inspection: downloaded PDF does not match the real
# document. Use the HTML page for these instead.
KNOWN_BAD_PDF_PRIDS = {36654, 37151, 37734, 56606, 62261}

# --- boilerplate anchors ---

_EMAIL_ANCHOR_RE = re.compile(r"helpdoc@rbi\.org\.in", re.IGNORECASE)

# Phone format varies across eras (022-2266-0502 / 91 22 2266 0502 /
# completely different numbers in some years) -- kept as a secondary anchor,
# email is the primary/reliable one.
_PHONE_ANCHOR_RE = re.compile(
    r"Phone\s*:?\s*(?:91\s*-?\s*22|022)\s*-?\s*2266\s*-?\s*0502", re.IGNORECASE
)

_PRESS_RELEASE_ID_RE = re.compile(r"Press Release\s*:\s*\d{4}-\d{4}/\d+")

_PAGE_NUM_LINE_RE = re.compile(r"^\s*\d{1,3}\s*$", re.MULTILINE)

# For the HTML fallback: real content usually starts right after "Date : <date>"
_HTML_CONTENT_START_RE = re.compile(r"Date\s*:\s*[A-Z][a-z]{2}\s+\d{1,2},\s+\d{4}")

# Generic fallback anchor: a plain "Month Day, Year" date (e.g. "June 7, 2017"),
# used when email/phone got mangled by PDF extraction, or the page has no
# "Date :" label at all (RBI's oldest page template, 2016). This is the date
# every statement opens with, restating when it was issued.
_DATE_PATTERN_RE = re.compile(r"[A-Z][a-z]+ \d{1,2},?\s*\d{4}")


def extract_pdf_text(pdf_path) -> str:
    """Extract raw text from a PDF, joining all pages with newlines."""
    with pdfplumber.open(pdf_path) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)


def extract_html_text(html_path) -> str:
    """Extract raw text from an HTML page (includes RBI's full nav menu)."""
    html = open(html_path, encoding="utf-8").read()
    soup = BeautifulSoup(html, "lxml")
    return soup.get_text(separator="\n", strip=True)


def clean_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def strip_header(text: str) -> str:
    """Cut everything up to and including the header boilerplate.
    Takes whichever anchor (email, phone, or a plain date) ends LATEST in the
    text -- always tries all three, since sometimes an earlier anchor matches
    but boilerplate continues past it (e.g. a scrambled email block after a
    clean phone match)."""
    ends = []
    m = _EMAIL_ANCHOR_RE.search(text)
    if m:
        ends.append(m.end())
    m = _PHONE_ANCHOR_RE.search(text)
    if m:
        ends.append(m.end())
    m = _DATE_PATTERN_RE.search(text)
    if m:
        ends.append(m.end())
    return text[max(ends):] if ends else text


def strip_footer(text: str) -> str:
    m = _PRESS_RELEASE_ID_RE.search(text)
    return text[:m.start()] if m else text


def strip_page_numbers(text: str) -> str:
    return _PAGE_NUM_LINE_RE.sub("", text)


def clean_pdf_text(raw_text: str) -> str:
    text = strip_header(raw_text)
    text = strip_footer(text)
    text = strip_page_numbers(text)
    return clean_whitespace(text)


def clean_html_text(raw_text: str) -> str:
    """Cleaning pipeline for the HTML fallback path (nav-menu-heavy pages).
    Only anchors on the "Date :" label -- deliberately does NOT fall back to
    a generic date-pattern search here, because HTML pages can contain
    unrelated dates elsewhere (e.g. an accessibility-statement timestamp),
    which risks cutting at the wrong point. For the handful of documents with
    no "Date :" label at all (RBI's oldest page template, 2016), this
    returns the text uncut -- a known, accepted limitation for ~3 of 163
    documents rather than a fix that risks silently corrupting others."""
    m = _HTML_CONTENT_START_RE.search(raw_text)
    text = raw_text[m.end():] if m else raw_text
    text = strip_footer(text)
    return clean_whitespace(text)


def extract_document_text(row) -> tuple[str, str]:
    """Extract + clean text for one manifest row. Returns (cleaned_text, source)
    where source is 'pdf' or 'html', so we can track which path was used."""
    if int(row["prid"]) in KNOWN_BAD_PDF_PRIDS:
        raw = extract_html_text(row["html_path"])
        return clean_html_text(raw), "html"
    raw = extract_pdf_text(row["pdf_path"])
    return clean_pdf_text(raw), "pdf"
