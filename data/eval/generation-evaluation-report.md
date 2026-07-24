# Generation-Phase Evaluation Report

Judge model used: **gpt-5.4-mini** (fallback from gpt-5.4 used: True)

## Claim-level citation precision

Unit is **claims** (a sentence carrying >=1 valid [n] marker; a multi-marker claim like `[4][7]` is judged once as one claim, not twice), not raw citation markers -- per ADR-0011.

**Aggregate**: supported=423, partial=37, unsupported=21, citation_precision=0.879

### Per category

- **general**: supported=258, partial=15, unsupported=10, citation_precision=0.912
- **multi_country**: supported=62, partial=5, unsupported=3, citation_precision=0.886
- **ooni_methodology**: supported=40, partial=2, unsupported=1, citation_precision=0.930
- **refusal**: supported=13, partial=5, unsupported=5, citation_precision=0.565
- **synthesis_supplement**: supported=50, partial=10, unsupported=2, citation_precision=0.806

## Mechanical counts (citations.py, free)

invalid_markers=0, unsupported_paragraphs=29

- **general**: invalid_markers=0, unsupported_paragraphs=18
- **multi_country**: invalid_markers=0, unsupported_paragraphs=3
- **ooni_methodology**: invalid_markers=0, unsupported_paragraphs=2
- **refusal**: invalid_markers=0, unsupported_paragraphs=0
- **synthesis_supplement**: invalid_markers=0, unsupported_paragraphs=6

## Refusal slice review

- `refusal-0000` (heuristic_declined=True, n_citations=4): What has OONI's network measurement work found about internet censorship in Rwanda?
- `refusal-0001` (heuristic_declined=False, n_citations=10): Did OONI detect any instances of Telegram or WhatsApp blocking in Rwanda?
- `refusal-0002` (heuristic_declined=False, n_citations=9): What test-helper infrastructure or false-positive rate does OONI report for measurements taken in Rwanda?
- `refusal-0003` (heuristic_declined=False, n_citations=2): According to Freedom House's Freedom on the Net report, what is Tanzania's internet freedom score for 2024?
- `refusal-0004` (heuristic_declined=False, n_citations=1): How did Freedom House score Tanzania's internet freedom in 2022 compared to 2024?
- `refusal-0005` (heuristic_declined=False, n_citations=1): What internet shutdowns has Access Now documented in Somalia?
- `refusal-0006` (heuristic_declined=True, n_citations=4): What does this corpus's evidence say about internet censorship in the Democratic Republic of Congo?
- `refusal-0007` (heuristic_declined=True, n_citations=3): What internet shutdowns occurred in Ethiopia during the 2015-2016 Oromo protests?
- `refusal-0008` (heuristic_declined=False, n_citations=4): What 5G network rollout milestones has Rwanda achieved, according to ITU broadband infrastructure reports?
