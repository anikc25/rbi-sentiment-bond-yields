"""
Phase 3: sentiment scoring.

Baseline 1 (this file): dictionary-based hawkish/dovish lexicon scorer.
Baseline 2 (separate step, next): FinBERT sentence-level scoring.
"""
import re

# Hawkish terms -- signal a tightening bias / inflation concern.
HAWKISH_TERMS = [
    "increase the policy repo rate", "rate hike", "hiked the repo rate",
    "withdrawal of accommodation", "upside risk to inflation",
    "upside risks to inflation", "inflationary pressures", "elevated inflation",
    "persistently high inflation", "sustained high inflation", "second round effects",
    "broad-based price pressures", "anchor inflation expectations", "remain vigilant",
    "vigilant", "calibrated tightening", "tightening of monetary policy",
    "restrictive", "overheating", "unacceptably high", "price stability",
    "inflation remains above target", "monetary tightening", "withdraw liquidity",
    "normalise liquidity", "normalize liquidity", "tighten",
]

# Dovish terms -- signal an easing bias / growth support.
DOVISH_TERMS = [
    "reduce the policy repo rate", "rate cut", "cut the repo rate", "accommodative",
    "remain accommodative", "support growth", "supporting growth", "revive growth",
    "stimulate growth", "downside risk to growth", "downside risks to growth",
    "growth concerns", "slowdown", "economic slack", "space for policy action",
    "ample liquidity", "durable recovery", "nascent recovery",
    "supportive of growth", "monetary easing", "easing of monetary policy",
    "neutral stance", "shift the stance", "changing the stance to neutral",
]

_TOKEN_RE = re.compile(r"[A-Za-z']+")


def _count_phrase(text_lower: str, phrase: str) -> int:
    return len(re.findall(re.escape(phrase.lower()), text_lower))


def lexicon_score(text: str) -> dict:
    """Dictionary-based hawkish/dovish score for one document.

    score = (hawkish_count - dovish_count) / total_words, per the project plan.
    Positive = hawkish-leaning, negative = dovish-leaning. Also returns a
    x1000-scaled version since the raw score is small (documents run
    thousands of words).
    """
    text_lower = text.lower()
    total_words = len(_TOKEN_RE.findall(text))

    hawkish_count = sum(_count_phrase(text_lower, p) for p in HAWKISH_TERMS)
    dovish_count = sum(_count_phrase(text_lower, p) for p in DOVISH_TERMS)

    score = (hawkish_count - dovish_count) / total_words if total_words else 0.0

    return {
        "hawkish_count": hawkish_count,
        "dovish_count": dovish_count,
        "total_words": total_words,
        "lexicon_score": score,
        "lexicon_score_x1000": score * 1000,
    }


def score_dataframe(df, text_col="text"):
    """Apply lexicon_score to every row of a DataFrame, return a new DataFrame
    with the score columns attached."""
    scores = df[text_col].apply(lexicon_score).apply(pd.Series)
    return pd.concat([df.reset_index(drop=True), scores.reset_index(drop=True)], axis=1)


# pandas is only needed for score_dataframe -- imported here, not at module
# level, so this file has no hard dependency on pandas being installed for
# the pure-function pieces above.
import pandas as pd  # noqa: E402


# ---------------------------------------------------------------------------
# Baseline 2: FinBERT sentence-level scoring
# ---------------------------------------------------------------------------

_FINBERT_MODEL_NAME = "ProsusAI/finbert"


def load_spacy_model():
    import spacy
    return spacy.load("en_core_web_sm")


def load_finbert():
    """Load FinBERT tokenizer + model. First call downloads ~440MB from
    Hugging Face and caches it locally under ~/.cache/huggingface; later
    calls are fast."""
    from transformers import AutoTokenizer, AutoModelForSequenceClassification
    tokenizer = AutoTokenizer.from_pretrained(_FINBERT_MODEL_NAME)
    model = AutoModelForSequenceClassification.from_pretrained(_FINBERT_MODEL_NAME)
    model.eval()
    return tokenizer, model


def split_sentences(text: str, nlp) -> list:
    """Split cleaned document text into sentences via spaCy, dropping tiny fragments."""
    doc = nlp(text)
    return [s.text.strip() for s in doc.sents if len(s.text.strip()) > 10]


def score_sentences_batch(sentences: list, tokenizer, model, batch_size: int = 16) -> list:
    """Run FinBERT on a list of sentences in batches. Returns a list of dicts,
    one per sentence, mapping label -> probability. Reads label order from the
    model's own config rather than hardcoding it, so it's correct regardless
    of FinBERT's internal ordering."""
    import torch
    id2label = model.config.id2label
    results = []
    for i in range(0, len(sentences), batch_size):
        batch = sentences[i:i + batch_size]
        inputs = tokenizer(batch, return_tensors="pt", padding=True, truncation=True, max_length=512)
        with torch.no_grad():
            outputs = model(**inputs)
        probs = torch.nn.functional.softmax(outputs.logits, dim=-1)
        for row in probs.tolist():
            results.append({id2label[j]: row[j] for j in range(len(row))})
    return results


def finbert_score_document(text: str, nlp, tokenizer, model, batch_size: int = 16) -> dict:
    """Sentence-split, score each sentence with FinBERT, aggregate to a
    document-level score. finbert_score = mean(positive) - mean(negative).

    IMPORTANT: FinBERT's positive/negative axis is general financial
    sentiment (profits/losses, good/bad news), NOT hawkish/dovish directly.
    Validate empirically (see the notebook's sanity-check cell) which
    direction it actually leans on known hawkish vs. dovish documents before
    interpreting the sign -- don't assume it matches lexicon_score's
    convention."""
    sentences = split_sentences(text, nlp)
    if not sentences:
        return {
            "sentence_count": 0, "mean_positive": 0.0, "mean_negative": 0.0,
            "mean_neutral": 0.0, "finbert_score": 0.0,
        }
    results = score_sentences_batch(sentences, tokenizer, model, batch_size)
    pos = sum(r.get("positive", 0.0) for r in results) / len(results)
    neg = sum(r.get("negative", 0.0) for r in results) / len(results)
    neu = sum(r.get("neutral", 0.0) for r in results) / len(results)
    return {
        "sentence_count": len(sentences),
        "mean_positive": pos,
        "mean_negative": neg,
        "mean_neutral": neu,
        "finbert_score": pos - neg,
    }
