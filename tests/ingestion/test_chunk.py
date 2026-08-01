"""Tier 1 (docs/testing-design.md): chunk.py's make_windows() only --
the pure boundary-math function. chunk_document() (the real site of the
2026-07-22 stamp-ordering bug) is deliberately Tier 2/out of scope here
(real filesystem writes/rmtree)."""

from chunk import make_windows


def test_empty_text_produces_no_windows():
    assert make_windows("", size=10, step=5) == []


def test_text_shorter_than_size_produces_exactly_one_window_covering_all():
    text = "abcde"  # len 5, size 10
    windows = make_windows(text, size=10, step=5)
    assert windows == [(0, 5)]


def test_overlapping_windows_exact_boundaries_and_count():
    text = "a" * 25  # len 25
    windows = make_windows(text, size=10, step=5)
    assert windows == [(0, 10), (5, 15), (10, 20), (15, 25)]


def test_final_window_reaches_exactly_the_end_no_small_remainder_chunk():
    text = "a" * 23  # len 23, size 10, step 5
    windows = make_windows(text, size=10, step=5)
    # Without the "always reach exactly the end" behavior, naive striding
    # would produce a final tiny (20, 23) chunk after (15, 25) is skipped
    # -- instead the last window is pulled back to end exactly at n=23.
    assert windows[-1] == (15, 23)
    assert windows == [(0, 10), (5, 15), (10, 20), (15, 23)]


def test_non_overlapping_windows_when_step_equals_size():
    text = "a" * 20
    windows = make_windows(text, size=10, step=10)
    assert windows == [(0, 10), (10, 20)]


def test_windows_slice_the_real_text_correctly():
    text = "0123456789ABCDEFGHIJ"  # len 20
    windows = make_windows(text, size=10, step=10)
    slices = [text[start:end] for start, end in windows]
    assert slices == ["0123456789", "ABCDEFGHIJ"]
