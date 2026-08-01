"""Tier 1 (docs/testing-design.md): ground_truth.py's classify_category().
Written to explicitly catch the real 2026-07-22 OONI case-sensitivity
regression -- the corpus stores organization as "OONI" (uppercase), and
a prior version of this function compared against the lowercase literal
"ooni" without lowering the chunk's own field first, making the
ooni_methodology branch permanently unreachable. The test below uses the
real, uppercase "OONI" the corpus actually stores, not a pre-lowered
convenience value, so a case-sensitivity regression would be caught."""

from ground_truth import classify_category


def _chunk(organization: str, countries: list[str], text: str) -> dict:
    return {"organization": organization, "countries": countries, "text": text}


def test_multi_country_takes_precedence():
    chunk = _chunk("OONI", ["KE", "UG"], "some ooni probe measurement text")
    assert classify_category(chunk) == "multi_country"


def test_ooni_methodology_with_real_uppercase_organization_string():
    # Regression case for the 2026-07-22 bug: real corpus data stores
    # "OONI" (uppercase), not "ooni".
    chunk = _chunk(
        "OONI", ["KE"],
        "This section describes the test helper infrastructure and how "
        "a confirmed anomaly is distinguished from a false positive.",
    )
    assert classify_category(chunk) == "ooni_methodology"


def test_ooni_without_methodology_keywords_is_general():
    chunk = _chunk("OONI", ["KE"], "A general narrative paragraph about internet shutdowns.")
    assert classify_category(chunk) == "general"


def test_non_ooni_org_is_never_ooni_methodology_even_with_keywords():
    chunk = _chunk(
        "CIPESA", ["KE"],
        "This report references OONI's own measurement and test helper methodology.",
    )
    assert classify_category(chunk) == "general"


def test_single_country_non_ooni_is_general():
    chunk = _chunk("Access Now", ["RW"], "A narrative paragraph about a single country.")
    assert classify_category(chunk) == "general"
