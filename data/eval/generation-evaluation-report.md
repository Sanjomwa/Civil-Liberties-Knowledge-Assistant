# Generation-Phase Evaluation Report

Judge model used: **gpt-5.4-mini** (fallback from gpt-5.4 used: True)

## Claim-level citation precision

Unit is **claims** (a sentence carrying >=1 valid [n] marker; a multi-marker claim like `[4][7]` is judged once as one claim, not twice), not raw citation markers -- per ADR-0011.

**Aggregate**: supported=431, partial=47, unsupported=18, citation_precision=0.869

### Per category

- **general**: supported=262, partial=25, unsupported=9, citation_precision=0.885
- **multi_country**: supported=65, partial=2, unsupported=3, citation_precision=0.929
- **ooni_methodology**: supported=38, partial=4, unsupported=1, citation_precision=0.884
- **refusal**: supported=6, partial=8, unsupported=3, citation_precision=0.353
- **synthesis_supplement**: supported=60, partial=8, unsupported=2, citation_precision=0.857

## Mechanical counts (citations.py, free)

invalid_markers=0, unsupported_paragraphs=21

- **general**: invalid_markers=0, unsupported_paragraphs=10
- **multi_country**: invalid_markers=0, unsupported_paragraphs=2
- **ooni_methodology**: invalid_markers=0, unsupported_paragraphs=2
- **refusal**: invalid_markers=0, unsupported_paragraphs=4
- **synthesis_supplement**: invalid_markers=0, unsupported_paragraphs=3

## Refusal slice review

- `refusal-0000` (heuristic_declined=False, n_citations=5): What has OONI's network measurement work found about internet censorship in Rwanda?
- `refusal-0001` (heuristic_declined=False, n_citations=5): Did OONI detect any instances of Telegram or WhatsApp blocking in Rwanda?
- `refusal-0002` (heuristic_declined=False, n_citations=5): What test-helper infrastructure or false-positive rate does OONI report for measurements taken in Rwanda?
- `refusal-0003` (heuristic_declined=False, n_citations=2): According to Freedom House's Freedom on the Net report, what is Tanzania's internet freedom score for 2024?
- `refusal-0004` (heuristic_declined=False, n_citations=3): How did Freedom House score Tanzania's internet freedom in 2022 compared to 2024?
- `refusal-0005` (heuristic_declined=False, n_citations=6): What internet shutdowns has Access Now documented in Somalia?
- `refusal-0006` (heuristic_declined=True, n_citations=3): What does this corpus's evidence say about internet censorship in the Democratic Republic of Congo?
- `refusal-0007` (heuristic_declined=True, n_citations=2): What internet shutdowns occurred in Ethiopia during the 2015-2016 Oromo protests?
- `refusal-0008` (heuristic_declined=False, n_citations=3): What 5G network rollout milestones has Rwanda achieved, according to ITU broadband infrastructure reports?
