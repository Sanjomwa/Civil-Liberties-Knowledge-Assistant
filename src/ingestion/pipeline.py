"""
pipeline.py — run the ingestion stages in order, stop on failure.

Calls acquire.py, extract.py, validate.py, metadata.py, and chunk.py in
sequence, as separate subprocess invocations of `uv run python ...` — the
same commands you'd type by hand, just run one after another. Logs what
ran and its exit status. Stops at the first failure rather than
continuing silently, per the architecture's "sequential and simple, no
orchestration framework" principle: this is a thin runner, not a workflow
engine.

Deliberately NOT included in the automatic sequence: the semantic review
step between validate.py and metadata.py. That step is a human reading
corpus/validation-report.md and logging an Included/Excluded decision by
hand in corpus/acquisition-log.md, per docs/corpus-inclusion-rubric.md —
running it as a scripted step would defeat the point of it being a human
judgment call. pipeline.py runs validate.py, then stops and prints a
reminder to do that review before re-running it to continue with
metadata.py and chunk.py.

Usage:
    uv run python src/ingestion/pipeline.py
"""

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
INGESTION_DIR = PROJECT_ROOT / "src" / "ingestion"

# Everything up to and including validate.py runs automatically every time.
AUTOMATED_STAGES = ["acquire.py", "extract.py", "validate.py"]

# These only make sense to run once a human has done the semantic review
# and logged Included/Excluded decisions in corpus/acquisition-log.md.
POST_REVIEW_STAGES = ["metadata.py", "chunk.py"]


def run_stage(script_name: str) -> None:
    script_path = INGESTION_DIR / script_name
    print(f"\n=== {script_name} ===", flush=True)
    result = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=PROJECT_ROOT,
    )
    if result.returncode != 0:
        print(
            f"\n[pipeline] {script_name} failed (exit {result.returncode}) "
            f"— stopping here rather than continuing with a corpus in an "
            f"unknown state.",
            file=sys.stderr,
        )
        sys.exit(result.returncode)


def main() -> None:
    run_all = "--all" in sys.argv

    for script_name in AUTOMATED_STAGES:
        run_stage(script_name)

    if not run_all:
        print(
            "\n[pipeline] Stopped after validate.py, as intended. Review "
            "corpus/validation-report.md, do the semantic review per "
            "docs/corpus-inclusion-rubric.md, and log each decision in "
            "corpus/acquisition-log.md. Once that's done, re-run this "
            "script with --all to continue through metadata.py and "
            "chunk.py for every document now marked Included."
        )
        return

    print(
        "\n[pipeline] --all passed: continuing on the assumption the "
        "semantic review in corpus/acquisition-log.md is already up to "
        "date for every document currently in corpus/validation-report.md."
    )
    for script_name in POST_REVIEW_STAGES:
        run_stage(script_name)

    print("\n[pipeline] Done — all stages completed successfully.")


if __name__ == "__main__":
    main()
