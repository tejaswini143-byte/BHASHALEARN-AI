"""Deterministic page-local chunking with Unicode grapheme-safe boundaries."""
from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass


CHUNKING_VERSION = "page-char-v1"


@dataclass(frozen=True)
class DocumentChunk:
    id: str
    page_number: int
    ordinal: int
    content: str
    content_hash: str


def normalize_page_text(value: str) -> str:
    """NFC-normalize and collapse whitespace without changing script or punctuation."""
    if not isinstance(value, str):
        raise TypeError("Page text must be a string")
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", value.replace("\x00", ""))).strip()


def _is_extend(char: str) -> bool:
    code = ord(char)
    return (
        unicodedata.category(char).startswith("M")
        or 0xFE00 <= code <= 0xFE0F
        or 0xE0100 <= code <= 0xE01EF
        or 0x1F3FB <= code <= 0x1F3FF
        or code == 0x20E3
    )


def _graphemes(value: str) -> list[str]:
    """Small UAX-29-aware splitter for combining marks, ZWJ and flag pairs."""
    parts: list[str] = []
    regional_count = 0
    join_next = False
    for char in value:
        code = ord(char)
        regional = 0x1F1E6 <= code <= 0x1F1FF
        if not parts:
            parts.append(char)
        elif _is_extend(char) or char == "\u200d" or join_next or _ends_with_virama(parts[-1]):
            parts[-1] += char
        elif regional and regional_count % 2 == 1:
            parts[-1] += char
        else:
            parts.append(char)
        if regional:
            regional_count += 1
        else:
            regional_count = 0
        join_next = char == "\u200d"
    return parts


def _ends_with_virama(cluster: str) -> bool:
    """Keep Indic consonant conjuncts together after virama/halant marks."""
    if not cluster:
        return False
    name = unicodedata.name(cluster[-1], "")
    return "VIRAMA" in name or "HALANT" in name


def chunk_pages(
    document_id: str,
    pages: list[tuple[int, str]],
    *,
    chunk_size: int = 1000,
    overlap: int = 150,
) -> list[DocumentChunk]:
    """Split each page independently using Unicode code-point budgets.

    Boundaries are kept on grapheme clusters. Chunks prefer a nearby whitespace
    boundary in the final quarter of the size budget. Overlap is measured in
    Unicode code points; page boundaries are never crossed.
    """
    if not document_id or chunk_size < 1 or overlap < 0 or overlap >= chunk_size:
        raise ValueError("Invalid document ID or chunk size/overlap configuration")
    result: list[DocumentChunk] = []
    ordinal = 0
    for page_number, raw_text in pages:
        if page_number < 1:
            raise ValueError("Page numbers start at one")
        normalized = normalize_page_text(raw_text)
        if not normalized:
            continue
        clusters = _graphemes(normalized)
        starts: list[int] = []
        position = 0
        for cluster in clusters:
            starts.append(position)
            position += len(cluster)
        cursor = 0
        while cursor < len(clusters):
            start_char = starts[cursor]
            hard_end = cursor
            while hard_end < len(clusters) and starts[hard_end] + len(clusters[hard_end]) - start_char <= chunk_size:
                hard_end += 1
            if hard_end == cursor:
                hard_end += 1  # A single grapheme may exceed the code-point target.
            end = hard_end
            if hard_end < len(clusters):
                floor = start_char + int(chunk_size * 0.75)
                whitespace = [i for i in range(cursor, hard_end) if clusters[i].isspace() and starts[i] >= floor]
                if whitespace:
                    end = whitespace[-1] + 1
            content = "".join(clusters[cursor:end]).strip()
            if content:
                content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
                stable_id = hashlib.sha256(
                    f"{CHUNKING_VERSION}\0{document_id}\0{page_number}\0{ordinal}\0{content_hash}".encode("utf-8")
                ).hexdigest()
                result.append(DocumentChunk(stable_id, page_number, ordinal, content, content_hash))
                ordinal += 1
            if end >= len(clusters):
                break
            end_char = starts[end] if end < len(starts) else len(normalized)
            target_start = max(start_char + 1, end_char - overlap)
            next_cursor = end
            while next_cursor > cursor and starts[next_cursor - 1] >= target_start:
                next_cursor -= 1
            cursor = next_cursor if next_cursor < end else end
    return result
