"""Tier 1 (docs/testing-design.md): generate.py's two pulled-forward
pure functions, _detect_out_of_scope_countries() and
_out_of_scope_disclosure() (ADR-0015). Includes a direct regression case
for the real Niger-in-Nigeria / Mali-in-Somalia substring bug (ADR-0015
round 3) -- both keyword pairs are literal substrings of each other, and
this module deliberately uses \\b-bounded regex matching (unlike
search.py's plain `in` check) specifically to avoid a false match/merge
between them."""

from generate import _detect_out_of_scope_countries, _out_of_scope_disclosure


# ---- _detect_out_of_scope_countries() -------------------------------


def test_detects_single_out_of_scope_country():
    assert _detect_out_of_scope_countries("What is happening in Nigeria?") == ["Nigeria"]


def test_case_insensitive_detection():
    assert _detect_out_of_scope_countries("What about NIGERIA right now?") == ["Nigeria"]


def test_in_scope_only_query_detects_nothing():
    assert _detect_out_of_scope_countries("What is happening in Kenya and Uganda?") == []


def test_niger_and_nigeria_both_detected_as_distinct_countries():
    # Regression case, ADR-0015 round 3: "niger" is a literal substring of
    # "nigeria". A plain `in` check would either miss "Niger" as a
    # separate mention or misfire depending on word order. \b-bounded
    # matching must catch both as distinct, real mentions.
    result = _detect_out_of_scope_countries("How does this compare to Nigeria and Niger?")
    assert "Nigeria" in result
    assert "Niger" in result
    assert len(result) == 2


def test_mali_and_somalia_both_detected_as_distinct_countries():
    # Same substring-collision class, the other documented pair:
    # "mali" is a literal substring of "somalia".
    result = _detect_out_of_scope_countries("The situation in Somalia differs from Mali.")
    assert "Somalia" in result
    assert "Mali" in result
    assert len(result) == 2


def test_nigeria_alone_does_not_falsely_detect_niger():
    result = _detect_out_of_scope_countries("What is happening in Nigeria?")
    assert result == ["Nigeria"]
    assert "Niger" not in result


def test_somalia_alone_does_not_falsely_detect_mali():
    result = _detect_out_of_scope_countries("What is happening in Somalia?")
    assert result == ["Somalia"]
    assert "Mali" not in result


def test_congo_and_drc_aliases_deduplicate_to_one_display_name():
    result = _detect_out_of_scope_countries("What about the DRC, also known as Congo?")
    assert result == ["the Democratic Republic of Congo"]


# ---- _out_of_scope_disclosure() --------------------------------------


def test_disclosure_single_country_uses_singular_verb():
    text = _out_of_scope_disclosure(["Nigeria"])
    assert "Nigeria is outside this assistant's five-country curated scope" in text
    assert "Kenya, Uganda, Tanzania, Ethiopia, Rwanda" in text


def test_disclosure_two_countries_uses_plural_verb_and_and():
    text = _out_of_scope_disclosure(["Nigeria", "Niger"])
    assert "Nigeria and Niger are outside this assistant's five-country curated scope" in text


def test_disclosure_three_countries_uses_oxford_style_join():
    text = _out_of_scope_disclosure(["Nigeria", "Egypt", "Zambia"])
    assert "Nigeria, Egypt and Zambia are outside this assistant's five-country curated scope" in text
