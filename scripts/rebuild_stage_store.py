#!/usr/bin/env python3
"""Utility to rebuild the stage cache from stored result logs."""

import argparse
from typing import Dict, Any

from app.app import iter_results, normalize_subject, subject_runtime_dir
import app.stage_tracker as stage_tracker


def rebuild(subject: str) -> Dict[str, Any]:
    """Rebuild the stage store for the provided subject and return it."""
    normalized = normalize_subject(subject)
    runtime_dir = subject_runtime_dir(normalized)
    records = iter_results(normalized)
    if not records:
        raise SystemExit(f"No results found for subject '{normalized}'.")

    store = stage_tracker.rebuild_store(runtime_dir, records)
    return store


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Rebuild the cached stage store (stages.json) from results.ndjson for a subject."
        )
    )
    parser.add_argument(
        "subject",
        help=(
            "Subject identifier to rebuild (matches the directory name under data/)."
        ),
    )

    args = parser.parse_args()
    store = rebuild(args.subject)

    user_count = 0
    state_count = 0
    if isinstance(store, dict):
        user_count = sum(1 for bucket in store.values() if isinstance(bucket, dict))
        state_count = sum(
            len(bucket) for bucket in store.values() if isinstance(bucket, dict)
        )

    print(
        "Rebuilt stage store for subject '{subject}' (users={users}, states={states}).".format(
            subject=normalize_subject(args.subject),
            users=user_count,
            states=state_count,
        )
    )


if __name__ == "__main__":
    main()
