import json
import logging
import string
from pathlib import Path

log = logging.getLogger("ura.query_expander")

_SYNONYMS_CACHE: dict[str, list[str]] | None = None
_SYNONYMS_PATH = Path(__file__).parent / "synonyms.json"
_SYNONYMS_CACHE: dict[str, list[str]] | None = None
_MAX_VARIANTS = 3


def _load_synonyms() -> dict[str, list[str]]:
    global _SYNONYMS_CACHE
    if _SYNONYMS_CACHE is not None:
        return _SYNONYMS_CACHE
    try:
        _SYNONYMS_CACHE = json.loads(_SYNONYMS_PATH.read_text())
        return _SYNONYMS_CACHE
    except FileNotFoundError:
        log.warning("synonyms.json not found at %s", _SYNONYMS_PATH)
        return {}
    except json.JSONDecodeError as e:
        log.warning("Invalid synonyms.json: %s", e)
        return {}


def _generate_variants(query_text: str) -> list[str]:
    """Generate sparse-only query variants by substituting synonyms.

    Returns up to _MAX_VARIANTS variants. Variants are used ONLY for
    sparse (BM25) search — dense embedding is computed once for the
    original query only.
    """
    synonyms = _load_synonyms()
    if not synonyms:
        return []

    words = [w.strip(string.punctuation) for w in query_text.lower().split() if w.strip(string.punctuation)]
    if not words:
        return []

    variants: list[str] = []
    seen: set[str] = {query_text.lower()}

    for i, word in enumerate(words):
        if word in synonyms:
            for syn in synonyms[word]:
                if len(variants) >= _MAX_VARIANTS:
                    break
                variant = " ".join(words[:i] + [syn] + words[i + 1 :])
                if variant not in seen:
                    variants.append(variant)
                    seen.add(variant)
            if len(variants) >= _MAX_VARIANTS:
                break

    return variants
