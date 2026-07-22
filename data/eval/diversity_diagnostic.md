# Source-Diversity Diagnostic

n=101 questions (from `ground_truth_filtered.json`).

## Part 1 -- which backend does hybrid's doc set resemble more?

Hybrid's top-10 doc_id set overlaps MORE with **vector's** than text's in 18/101 questions (17.8%); more with **text's** in 29/101 (28.7%); tied in 54.

If the vector-leaning share is clearly the majority, that's direct evidence the vector backend -- not RRF fusion itself -- is what narrows hybrid's source diversity relative to text.

## Part 2 -- top 5 largest text-vs-hybrid diversity gaps

### Gap=3: Which of the study countries had the highest purchasing-power-adjusted income in 2025?

- text top-10 docs (5 distinct): ['accessnow-africa-2023-keepiton-shutdowns', 'accessnow-africa-2024-keepiton-shutdowns', 'accessnow-africa-2025-keepiton-shutdowns', 'cipesa-africa-2024-sifa-elections', 'cipesa-africa-2025-sifa-ai']

- hybrid top-10 docs (2 distinct): ['cipesa-africa-2024-sifa-elections', 'cipesa-africa-2025-sifa-ai']

- vector top-10 docs (2 distinct): ['cipesa-africa-2024-sifa-elections', 'cipesa-africa-2025-sifa-ai']

### Gap=3: What factors have caused journalists, LGBT+ people, and ordinary social media users in Uganda to hold back from speaking openly online?

- text top-10 docs (8 distinct): ['accessnow-africa-2025-keepiton-shutdowns', 'cipesa-africa-2024-sifa-elections', 'freedomhouse-rw-2022-fotn', 'freedomhouse-rw-2024-fotn', 'freedomhouse-ug-2023-fotn', 'freedomhouse-ug-2024-fotn', 'freedomhouse-ug-2025-fotn', 'ooni-tz-2024-lgbtiq-censorship']

- hybrid top-10 docs (5 distinct): ['freedomhouse-rw-2024-fotn', 'freedomhouse-ug-2023-fotn', 'freedomhouse-ug-2024-fotn', 'freedomhouse-ug-2025-fotn', 'ooni-tz-2024-lgbtiq-censorship']

- vector top-10 docs (4 distinct): ['freedomhouse-ug-2022-fotn', 'freedomhouse-ug-2023-fotn', 'freedomhouse-ug-2024-fotn', 'freedomhouse-ug-2025-fotn']

### Gap=3: What legal protections in Kenya give people rights over decisions made by automated systems and require human review?

- text top-10 docs (5 distinct): ['cipesa-africa-2025-sifa-ai', 'cipesa-et-2025-sifa-ai-country', 'cipesa-ke-2025-sifa-ai-country', 'cipesa-rw-2025-upr-submission', 'cipesa-ug-2025-sifa-ai-country']

- hybrid top-10 docs (2 distinct): ['cipesa-africa-2025-sifa-ai', 'cipesa-ke-2025-sifa-ai-country']

- vector top-10 docs (2 distinct): ['cipesa-africa-2025-sifa-ai', 'cipesa-ke-2025-sifa-ai-country']

### Gap=3: What changes did Uganda make to its computer misuse law in 2022 and 2023, and what penalties does the amended law impose for certain online offenses?

- text top-10 docs (6 distinct): ['freedomhouse-et-2022-fotn', 'freedomhouse-et-2024-fotn', 'freedomhouse-ke-2024-fotn', 'freedomhouse-ug-2022-fotn', 'freedomhouse-ug-2023-fotn', 'freedomhouse-ug-2024-fotn']

- hybrid top-10 docs (3 distinct): ['freedomhouse-ug-2022-fotn', 'freedomhouse-ug-2023-fotn', 'freedomhouse-ug-2024-fotn']

- vector top-10 docs (3 distinct): ['freedomhouse-ug-2022-fotn', 'freedomhouse-ug-2023-fotn', 'freedomhouse-ug-2024-fotn']

### Gap=3: What kinds of legal penalties does Rwanda impose for lawful online expression?

- text top-10 docs (7 distinct): ['cipesa-rw-2025-upr-submission', 'freedomhouse-et-2023-fotn', 'freedomhouse-et-2025-fotn', 'freedomhouse-rw-2022-fotn', 'freedomhouse-rw-2023-fotn', 'freedomhouse-rw-2024-fotn', 'freedomhouse-ug-2025-fotn']

- hybrid top-10 docs (4 distinct): ['cipesa-rw-2025-upr-submission', 'freedomhouse-rw-2022-fotn', 'freedomhouse-rw-2023-fotn', 'freedomhouse-rw-2024-fotn']

- vector top-10 docs (4 distinct): ['freedomhouse-ke-2022-fotn', 'freedomhouse-rw-2022-fotn', 'freedomhouse-rw-2023-fotn', 'freedomhouse-rw-2024-fotn']

