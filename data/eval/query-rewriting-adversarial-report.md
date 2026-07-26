# Query rewriting evaluation -- adversarial set (40 questions)

Both runs use `src/retrieval/evaluate.py`'s own `hit_rate_and_mrr()` unchanged, method=hybrid, rrf_k=recorded default (10). Only the query text fed to `search()` differs: raw vs. `generate.rewrite_query()`'s output.

## Aggregate

| Metric | Raw | Rewritten | Delta |
|---|---|---|---|
| Hit Rate | 0.6250 | 0.6250 | +0.0000 |
| MRR | 0.2874 | 0.3027 | +0.0153 |
| Relaxed Hit Rate | 0.7000 | 0.7250 | +0.0250 |
| Relaxed MRR | 0.3561 | 0.3835 | +0.0273 |
| Hit Rate@3 | 0.3500 | 0.3750 | +0.0250 |
| Hit Rate@5 | 0.4250 | 0.4500 | +0.0250 |
| n | 40 | 40 | |

### 95% bootstrap CI (strict Hit Rate / MRR only, 2000 resamples)

| Metric | Raw CI | Rewritten CI | CIs overlap? |
|---|---|---|---|
| Hit Rate | [0.4750, 0.7750] | [0.4750, 0.7750] | yes (not distinguishable at 95%) |
| MRR | [0.1828, 0.4011] | [0.1947, 0.4202] | yes (not distinguishable at 95%) |

## Per category

### multi_country (n=9)

| Metric | Raw | Rewritten | Delta |
|---|---|---|---|
| Hit Rate | 0.6667 | 0.6667 | +0.0000 |
| MRR | 0.3410 | 0.4136 | +0.0725 |

### ooni_methodology (n=4)

| Metric | Raw | Rewritten | Delta |
|---|---|---|---|
| Hit Rate | 1.0000 | 1.0000 | +0.0000 |
| MRR | 0.8000 | 0.8333 | +0.0333 |

### general (n=27)

| Metric | Raw | Rewritten | Delta |
|---|---|---|---|
| Hit Rate | 0.5556 | 0.5556 | +0.0000 |
| MRR | 0.1936 | 0.1871 | -0.0064 |

