from backend.app.services.chunking import chunk_pages, normalize_page_text


def test_telugu_english_mixed_and_punctuation_are_preserved():
    pages = [(1, "తెలుగు పాఠం! English sentence, mixed తెలుగు-English.")]
    chunks = chunk_pages("doc", pages, chunk_size=120, overlap=10)
    assert len(chunks) == 1
    assert chunks[0].content == "తెలుగు పాఠం! English sentence, mixed తెలుగు-English."


def test_page_boundaries_empty_pages_and_order_are_preserved():
    chunks = chunk_pages("doc", [(1, "first page"), (2, "  \n  "), (3, "మూడవ పేజీ")], chunk_size=100, overlap=5)
    assert [(c.page_number, c.ordinal) for c in chunks] == [(1, 0), (3, 1)]
    assert [c.content for c in chunks] == ["first page", "మూడవ పేజీ"]


def test_overlap_is_stable_and_repeated_runs_have_identical_ids_and_hashes():
    text = "abcdefghijklmnopqrstuvwxyz" * 40
    first = chunk_pages("doc-1", [(1, text)], chunk_size=80, overlap=16)
    second = chunk_pages("doc-1", [(1, text)], chunk_size=80, overlap=16)
    assert first == second
    assert len(first) > 2
    assert all(a.content[-16:] == b.content[:16] for a, b in zip(first, first[1:]))
    assert all(c.content_hash and c.id for c in first)


def test_long_unbroken_text_is_bounded_and_no_zero_length_chunks_are_emitted():
    chunks = chunk_pages("doc", [(1, "x" * 3200)], chunk_size=300, overlap=40)
    assert len(chunks) > 8
    assert all(0 < len(c.content) <= 300 for c in chunks)
    assert "".join(c.content[:260] for c in chunks).startswith("x" * 500)


def test_unicode_combining_marks_emoji_zwj_and_flags_are_not_split():
    combining = "a\u0301"
    emoji = "👩‍👩‍👧‍👦"
    flag = "🇮🇳"
    text = (combining + emoji + flag) * 20
    chunks = chunk_pages("unicode", [(1, text)], chunk_size=10, overlap=2)
    assert "".join(chunk.content for chunk in chunks).startswith("á" + emoji + flag)
    assert all(not chunk.content.endswith("\u200d") for chunk in chunks)
    assert all(not chunk.content.startswith("\u200d") for chunk in chunks)
    assert all(not chunk.content.endswith("\u0c4d") for chunk in chunk_pages("unicode", [(1, "క\u0c4dషి " * 10)], chunk_size=4, overlap=1))


def test_normalization_is_nfc_and_whitespace_only_pages_are_empty():
    assert normalize_page_text("a\u0301  \n b") == "á b"
    assert chunk_pages("doc", [(1, " \n\t ")]) == []


def test_invalid_chunk_configuration_is_rejected():
    import pytest

    with pytest.raises(ValueError):
        chunk_pages("doc", [(1, "text")], chunk_size=10, overlap=10)
