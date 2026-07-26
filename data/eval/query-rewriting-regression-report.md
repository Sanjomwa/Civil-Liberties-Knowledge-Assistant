# Query rewriting evaluation -- regression set (101 questions)

Both runs use `src/retrieval/evaluate.py`'s own `hit_rate_and_mrr()` unchanged, method=hybrid, rrf_k=recorded default (10). Only the query text fed to `search()` differs: raw vs. `generate.rewrite_query()`'s output.

## Aggregate

| Metric | Raw | Rewritten | Delta |
|---|---|---|---|
| Hit Rate | 0.6535 | 0.6436 | -0.0099 |
| MRR | 0.2721 | 0.2585 | -0.0136 |
| Relaxed Hit Rate | 0.8416 | 0.8119 | -0.0297 |
| Relaxed MRR | 0.4459 | 0.4263 | -0.0196 |
| Hit Rate@3 | 0.3663 | 0.2871 | -0.0792 |
| Hit Rate@5 | 0.4752 | 0.4455 | -0.0297 |
| n | 101 | 101 | |

### 95% bootstrap CI (strict Hit Rate / MRR only, 2000 resamples)

| Metric | Raw CI | Rewritten CI | CIs overlap? |
|---|---|---|---|
| Hit Rate | [0.5545, 0.7426] | [0.5446, 0.7327] | yes (not distinguishable at 95%) |
| MRR | [0.2121, 0.3374] | [0.1963, 0.3267] | yes (not distinguishable at 95%) |

## Per category

### multi_country (n=22)

| Metric | Raw | Rewritten | Delta |
|---|---|---|---|
| Hit Rate | 0.6818 | 0.6364 | -0.0455 |
| MRR | 0.2439 | 0.2484 | +0.0045 |

### ooni_methodology (n=11)

| Metric | Raw | Rewritten | Delta |
|---|---|---|---|
| Hit Rate | 0.8182 | 0.9091 | +0.0909 |
| MRR | 0.5404 | 0.5005 | -0.0399 |

### general (n=68)

| Metric | Raw | Rewritten | Delta |
|---|---|---|---|
| Hit Rate | 0.6176 | 0.6029 | -0.0147 |
| MRR | 0.2378 | 0.2226 | -0.0152 |

