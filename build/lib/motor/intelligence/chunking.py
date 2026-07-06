"""SemanticChunker — divide documentos por estructura (títulos, secciones, párrafos).

Uso:
    chunker = SemanticChunker(max_tokens=512, overlap_tokens=64)
    chunks = chunker.chunk(document_text, doc_id="doc_001")
"""

from __future__ import annotations

import re
import logging
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger("ura.chunker.semantic")


@dataclass
class Chunk:
    document_id: str
    chunk_id: str
    parent_id: str = ""
    offset: int = 0
    length: int = 0
    section: str = ""
    texto: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def chunk_index(self) -> int:
        parts = self.chunk_id.rsplit("_", 1)
        return int(parts[-1]) if len(parts) > 1 and parts[-1].isdigit() else 0


class SemanticChunker:
    """Divide texto por estructura semántica: títulos, secciones, párrafos.

    Estrategia:
    1. Detectar bloques por títulos (##, ###)
    2. Si un bloque excede max_tokens, subdividir por párrafos
    3. Cada chunk incluye el contexto del título y metadatos de estructura
    """

    def __init__(
        self,
        max_tokens: int = 512,
        overlap_tokens: int = 64,
        respect_headings: bool = True,
    ) -> None:
        self.max_tokens = max_tokens
        self.overlap_tokens = overlap_tokens
        self.respect_headings = respect_headings

    def chunk(
        self,
        texto: str,
        doc_id: str = "",
        section: str = "",
    ) -> list[Chunk]:
        text = texto.strip()
        if not text:
            return []

        if self.respect_headings:
            sections = self._split_by_headings(text)
        else:
            sections = [("", text)]

        chunks: list[Chunk] = []
        global_offset = 0

        for sec_title, sec_body in sections:
            effective_section = section + (" > " + sec_title if sec_title else "")
            sec_chunks = self._chunk_section(sec_body, doc_id, effective_section, global_offset)
            chunks.extend(sec_chunks)
            global_offset += len(sec_body)

        # Assign chunk_ids and parent_id
        for i, c in enumerate(chunks):
            c.chunk_id = f"{doc_id}_{i}" if doc_id else f"chunk_{i}"
            c.parent_id = doc_id

        return chunks

    def _split_by_headings(self, text: str) -> list[tuple[str, str]]:
        """Divide texto por títulos markdown (##, ###, etc.)."""
        pattern = re.compile(r"^(#{2,})\s+(.+)$", re.MULTILINE)
        parts = pattern.split(text)

        if len(parts) <= 1:
            return [("", text)]

        sections: list[tuple[str, str]] = []
        current_title = ""
        current_body: list[str] = []

        for i, part in enumerate(parts):
            if i == 0:
                preamble = part.strip()
                if preamble:
                    current_body.append(preamble)
                continue

            if i % 3 == 1:
                if current_body or current_title:
                    sections.append((current_title, "\n".join(current_body).strip()))
                current_title = parts[i + 1] if i + 1 < len(parts) else ""
                current_body = []
            elif i % 3 == 2:
                pass
            elif i % 3 == 0:
                body = part.strip()
                if body:
                    current_body.append(body)

        if current_body or current_title:
            sections.append((current_title, "\n".join(current_body).strip()))

        return sections

    def _chunk_section(
        self,
        text: str,
        doc_id: str,
        section: str,
        offset: int,
    ) -> list[Chunk]:
        token_count = self._estimate_tokens(text)

        if token_count <= self.max_tokens:
            return [
                Chunk(
                    document_id=doc_id,
                    chunk_id="",
                    offset=offset,
                    length=len(text),
                    section=section,
                    texto=text,
                )
            ]

        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        if not paragraphs:
            return [
                Chunk(
                    document_id=doc_id,
                    chunk_id="",
                    offset=offset,
                    length=len(text),
                    section=section,
                    texto=text[:self._char_limit()],
                )
            ]

        chunks: list[Chunk] = []
        current_texts: list[str] = []
        current_tokens = 0
        current_offset = offset

        for para in paragraphs:
            para_tokens = self._estimate_tokens(para)

            if current_tokens + para_tokens > self.max_tokens and current_texts:
                chunk_text = "\n\n".join(current_texts)
                char_limit = self._char_limit()
                chunk_text = chunk_text[:char_limit]
                chunks.append(
                    Chunk(
                        document_id=doc_id,
                        chunk_id="",
                        offset=current_offset,
                        length=len(chunk_text),
                        section=section,
                        texto=chunk_text,
                    )
                )

                # Overlap: keep last paragraph(s) for context
                overlap_paras: list[str] = []
                overlap_tokens = 0
                for p in reversed(current_texts):
                    pt = self._estimate_tokens(p)
                    if overlap_tokens + pt <= self.overlap_tokens:
                        overlap_paras.insert(0, p)
                        overlap_tokens += pt
                    else:
                        break
                current_texts = overlap_paras
                current_tokens = overlap_tokens
                current_offset += len(chunk_text) - len("\n\n".join(overlap_paras))

            current_texts.append(para)
            current_tokens += para_tokens

        if current_texts:
            chunk_text = "\n\n".join(current_texts)
            char_limit = self._char_limit()
            chunks.append(
                Chunk(
                    document_id=doc_id,
                    chunk_id="",
                    offset=current_offset,
                    length=len(chunk_text),
                    section=section,
                    texto=chunk_text[:char_limit],
                )
            )

        return chunks

    def _estimate_tokens(self, text: str) -> int:
        return len(text) // 4

    def _char_limit(self) -> int:
        return self.max_tokens * 4
