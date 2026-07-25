# Prompt A/B Comparison Report

Closes ADR-0012 Decision 2 / docs/evaluation-design.md Decision 6 -- the LLM-evaluation phase's rubric gap (only one generation approach was ever compared). Model held fixed (`gpt-5.4-mini`), `temperature=0.2` for both arms, retrieval held fixed per question (one `search()` call reused for both prompts). Judged with the existing, unmodified `judge.py`.

**Judge model used:** gpt-5.4-mini (fallback from gpt-5.4 used: True)

**Stratified subset allocation** (largest-remainder, preserving each category's real share of the 122-question combined set): {'ooni_methodology': 4, 'multi_country': 7, 'general': 22, 'synthesis_supplement': 4, 'refusal': 3}

## Per-arm results

| Metric | Prompt A | Prompt B |
|---|---|---|
| n answers | 40 | 40 |
| n claims judged | 177 | 160 |
| verdict counts | {'supported': 158, 'unsupported': 5, 'partial': 14} | {'supported': 139, 'partial': 9, 'unsupported': 12} |
| citation precision | 0.893 | 0.869 |
| claims per answer (mean) | 4.425 | 4.000 |
| abstention rate | 0.000 | 0.025 |
| mean prompt tokens | 3727 | 3902 |
| mean completion tokens | 235 | 411 |
| total prompt tokens (subset) | 149065 | 156065 |
| total completion tokens (subset) | 9395 | 16443 |
