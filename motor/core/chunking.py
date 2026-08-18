import re


def chunk_semantic(text: str, max_words: int = 500, min_words: int = 100) -> list[str]:
    """Chunk text at paragraph/section boundaries.
    Falls back to word-count sliding window when no boundaries found.
    """
    sections = _split_sections(text)
    chunks = []
    for sec in sections:
        sec = sec.strip()
        if not sec:
            continue
        words = sec.split()
        if len(words) <= max_words:
            chunks.append(sec)
        else:
            chunks.extend(_split_paragraphs(sec, max_words, min_words))
    if not chunks:
        chunks = _word_window(text, max_words, max_words // 10)
    return chunks


def _split_sections(text: str) -> list[str]:
    patterns = [
        r"(?=\n#{1,6}\s)",  # Markdown headings
        r"(?=\n[A-Z][^\n]{0,50}\n[-=]+\n)",  # Underlined headings
        r"(?=\n\d+\.\s+[A-Z])",  # Numbered sections
        r"(?=\n---+?\n)",  # Horizontal rules
        r"(?=<h[1-6])",  # HTML headings
    ]
    combined = "|".join(patterns)
    parts = re.split(combined, text) if combined else [text]
    return [p.strip() for p in parts if p.strip()]


def _split_paragraphs(text: str, max_words: int, min_words: int) -> list[str]:
    paragraphs = re.split(r"\n\s*\n", text)
    chunks = []
    buffer: list[str] = []
    buffer_words = 0
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        pw = len(para.split())
        if buffer_words + pw <= max_words:
            buffer.append(para)
            buffer_words += pw
        else:
            if buffer:
                chunks.append("\n\n".join(buffer))
            if pw > max_words:
                chunks.extend(_word_window(para, max_words, max_words // 10))
                buffer = []
                buffer_words = 0
            else:
                buffer = [para]
                buffer_words = pw
    if buffer and buffer_words >= min_words:
        chunks.append("\n\n".join(buffer))
    elif buffer:
        if chunks:
            chunks[-1] = chunks[-1] + "\n\n" + "\n\n".join(buffer)
        else:
            chunks.append("\n\n".join(buffer))
    return chunks


def _word_window(text: str, size: int, overlap: int) -> list[str]:
    words = text.split()
    if len(words) <= size:
        return [text]
    chunks = []
    start = 0
    while start < len(words):
        end = min(start + size, len(words))
        chunks.append(" ".join(words[start:end]))
        start += size - overlap
    return chunks
