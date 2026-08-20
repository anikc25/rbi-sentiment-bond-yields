"""
Central path config.

Every other script imports from here instead of hardcoding relative paths.
This means scraper.py / download.py / etc. all work correctly whether you
run them as `python src/scraper.py` from the project root, or as
`python scraper.py` from inside src/, or from a notebook in notebooks/.
"""
from pathlib import Path

# project root = the folder that contains src/, data/, notebooks/, reports/
ROOT = Path(__file__).resolve().parent.parent

DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
HTML_DIR = RAW_DIR / "html"
PDF_DIR = RAW_DIR / "pdf"
PROCESSED_DIR = DATA_DIR / "processed"
MARKET_DIR = DATA_DIR / "market"

REPORTS_DIR = ROOT / "reports"
FIGURES_DIR = REPORTS_DIR / "figures"

NOTEBOOKS_DIR = ROOT / "notebooks"

# make sure they all exist (harmless if they already do)
for d in [HTML_DIR, PDF_DIR, PROCESSED_DIR, MARKET_DIR, FIGURES_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# key files produced along the pipeline
DOC_INDEX_CSV = RAW_DIR / "mpc_document_index.csv"
DOWNLOAD_MANIFEST_CSV = RAW_DIR / "download_manifest.csv"
MASTER_TEXT_CSV = PROCESSED_DIR / "master_statements.csv"
SENTIMENT_CSV = PROCESSED_DIR / "sentiment_scores.csv"
MERGED_CSV = PROCESSED_DIR / "merged_dataset.csv"

USDINR_CSV = MARKET_DIR / "usdinr_daily.csv"
GSEC_CSV = MARKET_DIR / "india_10y_gsec_raw.csv"
CPI_CSV = MARKET_DIR / "cpi_surprise.csv"
REPO_RATE_CSV = MARKET_DIR / "repo_rate_history.csv"

if __name__ == "__main__":
    # quick sanity check: run `python src/paths.py` to print the layout
    for name, path in [
        ("ROOT", ROOT), ("HTML_DIR", HTML_DIR), ("PDF_DIR", PDF_DIR),
        ("PROCESSED_DIR", PROCESSED_DIR), ("MARKET_DIR", MARKET_DIR),
        ("FIGURES_DIR", FIGURES_DIR),
    ]:
        print(f"{name:15s} -> {path}  (exists: {path.exists()})")
