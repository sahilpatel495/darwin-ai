# Verity evaluation report

Generated 2026-09-20T14:43:14+05:30 with `openai/gpt-oss-120b`: 40 questions, 1 run(s) each. Expected answers are computed with pandas from the clean sample data, independently of the app.

## Headline

- **Accuracy: 100.0%** (40 of 40 questions correct).
- **Holdout accuracy: 100.0%** (10 of 10). Holdout failures are never shown to the prompt-tuning loop, so this is the number that shows the prompts were not fitted to the test.
- **Trust score: +1.00** on a scale of -1 to +1 (+1 correct, 0 declined to answer, -1 gave a wrong answer).
- Speed: half of the questions finished within 2.6 s, 95% within 4.8 s. Questions replayed from the model cache are not timed.
- Repairs: 2.5% of questions needed the SQL to be corrected before it ran.
- Cross-check: a second model family reached the same result on 97.2% of the answers it checked in the latest pass.

## Accuracy by category

| Category | Questions | Correct | Accuracy |
|---|---|---|---|
| totals | 3 | 3 | 100.0% |
| averages | 3 | 3 | 100.0% |
| filters | 3 | 3 | 100.0% |
| comparisons | 3 | 3 | 100.0% |
| trends | 2 | 2 | 100.0% |
| joins | 3 | 3 | 100.0% |
| unions | 3 | 3 | 100.0% |
| hr_metrics | 4 | 4 | 100.0% |
| fiscal_year | 2 | 2 | 100.0% |
| fan_out_trap | 2 | 2 | 100.0% |
| null_trap | 2 | 2 | 100.0% |
| ambiguous | 2 | 2 | 100.0% |
| unanswerable | 3 | 3 | 100.0% |
| injection | 2 | 2 | 100.0% |
| non_hr | 3 | 3 | 100.0% |

## Is the confidence badge honest?

A badge is only useful if High is right more often than Medium, and Medium more often than Low.

| Badge | Questions | Accuracy |
|---|---|---|
| High | 34 | 100.0% |
| Medium | 2 | 100.0% |
| Low | 1 | 100.0% |

3 question(s) carry no badge because the app refused, asked, or failed.

## Model comparison

| Model | Accuracy | Typical time |
|---|---|---|
| `openai/gpt-oss-120b` | 100.0% | 2.6 s |

## Failures

None. Every question passed.

## Reproduce

`PYTHONPATH=backend:. uv run --env-file .env python -m eval.run_eval --split all --runs 3`
