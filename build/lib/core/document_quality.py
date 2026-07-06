import hashlib
import re
from datetime import UTC, datetime

_RELIABILITY_DOMAINS: dict[str, float] = {
    "github.com": 0.9,
    "docs.python.org": 0.95,
    "wikipedia.org": 0.8,
    "stackoverflow.com": 0.85,
    "medium.com": 0.5,
    "reddit.com": 0.4,
    "twitter.com": 0.3,
    "x.com": 0.3,
}

_LANG_CACHE: dict[str, str] = {}


def detect_language(text: str) -> str:
    if not text.strip():
        return "unknown"
    sample = text[:2000]
    cache_key = hashlib.md5(sample.encode()).hexdigest()
    if cache_key in _LANG_CACHE:
        return _LANG_CACHE[cache_key]
    try:
        from lingua import Language, LanguageDetectorBuilder

        detector = LanguageDetectorBuilder.from_languages(
            Language.ENGLISH,
            Language.SPANISH,
            Language.FRENCH,
            Language.GERMAN,
            Language.PORTUGUESE,
            Language.ITALIAN,
            Language.CATALAN,
            Language.DUTCH,
        ).build()
        detected = detector.detect_language_of(sample)
        result = detected.iso_code_639_1.name.lower() if detected else "unknown"
    except Exception:
        result = _fast_lang_detect(sample)
    _LANG_CACHE[cache_key] = result
    return result


def _fast_lang_detect(text: str) -> str:
    common_en = {"the", "and", "you", "that", "was", "for", "are", "with", "this", "have"}
    common_es = {"que", "los", "las", "del", "por", "con", "una", "para", "como", "mas"}
    words = set(re.findall(r"[a-zA-Z]{2,}", text.lower()))
    en_score = len(words & common_en)
    es_score = len(words & common_es)
    if en_score > es_score:
        return "en"
    if es_score > en_score:
        return "es"
    return "unknown"


def source_reliability(url: str) -> float:
    if not url:
        return 0.5
    for domain, score in _RELIABILITY_DOMAINS.items():
        if domain in url:
            return score
    return 0.5


def extract_publication_date(text: str) -> str | None:
    patterns = [
        (r"\b(20\d{2})[-/](0[1-9]|1[0-2])[-/](0[1-9]|[12]\d|3[01])\b", "%Y-%m-%d"),
        (r"\b(0[1-9]|[12]\d|3[01])[-/](0[1-9]|1[0-2])[-/](20\d{2})\b", "%d-%m-%Y"),
    ]
    for pattern, fmt in patterns:
        match = re.search(pattern, text[:5000])
        if match:
            try:
                return datetime.strptime(match.group(0), fmt).isoformat()
            except ValueError:
                continue
    return None


def content_type(text: str) -> str:
    lines = text.strip().split("\n")
    if any(l.strip().startswith("```") for l in lines[:20]):
        return "code"
    if re.search(r"(?:def |class |import |function|const |var |let )", text[:2000]):
        return "code"
    if re.search(r"<html|<div|<p>|<body", text[:500]):
        return "html"
    if re.search(r"\|\s*[-]+\s*\|", text):
        return "table"
    if len(lines) > 50 and all(len(l) > 200 for l in lines[:10] if l.strip()):
        return "documentation"
    return "article"


def is_stale(indexed_at: str | None, ttl_days: int = 30) -> bool:
    if not indexed_at:
        return True
    try:
        parsed = datetime.fromisoformat(indexed_at)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        delta = datetime.now(UTC) - parsed
        return delta.days > ttl_days
    except (ValueError, TypeError):
        return True


def doc_id_from_text(text: str, prefix: str = "doc") -> str:
    return f"{prefix}_{hashlib.sha256(text.encode()).hexdigest()[:16]}"


def adaptive_threshold(
    scores: list[float],
    base_threshold: float = 0.5,
    min_threshold: float = 0.2,
    std_factor: float = 1.0,
) -> float:
    """Compute an adaptive threshold based on score distribution.

    Uses mean + std_factor * stddev when scores are diverse,
    otherwise falls back to base_threshold.

    Args:
        scores: list of relevance scores (typically RRf or composite)
        base_threshold: fallback threshold when distribution is flat
        min_threshold: floor for the computed threshold
        std_factor: multiples of stddev above mean

    Returns:
        float threshold in [min_threshold, 1.0]

    """
    if not scores:
        return base_threshold
    import statistics

    mean = statistics.mean(scores)
    stdev = statistics.stdev(scores) if len(scores) > 1 else 0.0
    if stdev < 0.05:
        return base_threshold
    threshold = mean + std_factor * stdev
    return max(min_threshold, min(threshold, 1.0))
