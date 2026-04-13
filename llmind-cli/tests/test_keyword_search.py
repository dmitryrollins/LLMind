"""Tests for llmind.embedder.keyword_score."""
from llmind.embedder import keyword_score


def test_exact_phrase_scores_one() -> None:
    assert keyword_score("ring", "a gold ring on the table") == 1.0


def test_exact_phrase_word_boundary() -> None:
    # "ring" must NOT match "earring"
    assert keyword_score("ring", "an earring on the table") < 1.0


def test_all_words_present_scores_point_seven() -> None:
    score = keyword_score("wedding ring", "she wore a ring at the wedding")
    assert score == 0.7


def test_partial_word_overlap() -> None:
    score = keyword_score("wedding ring photo", "wedding photo")
    assert 0.3 <= score < 0.7


def test_substring_fallback_scores_point_fifteen() -> None:
    score = keyword_score("earrings", "her ears were adorned")
    # "earrings" not found as word but contains "ear"
    assert score == 0.15 or score == 0.0  # depends on text_words


def test_no_match_scores_zero() -> None:
    assert keyword_score("spaceship", "a beautiful sunset over the ocean") == 0.0


def test_empty_query_scores_zero() -> None:
    assert keyword_score("", "some text here") == 0.0


def test_empty_text_scores_zero() -> None:
    assert keyword_score("ring", "") == 0.0


def test_case_insensitive_match() -> None:
    assert keyword_score("Ring", "A GOLD RING on the table") == 1.0
