"""Measure candidates against an operator-approved frozen public corpus."""
from __future__ import annotations

import hashlib
from dataclasses import replace
from pathlib import Path
from time import monotonic

from .oracle import evaluate, load_cases
from .schema import Check
from .verify import classify, invoke


CORPUS = "examples.json"


def score(build: Check, run: Check, corpus: Path, work: Path, home: Path, image: str, deadline: float,
          stop: Path, missing: list[str]) -> dict:
    cases = load_cases(corpus, public=True)
    receipt = {"corpus_sha256": hashlib.sha256(corpus.read_bytes()).hexdigest(),
               "runner": image, "policy_valid": True, "compiled": False, "missing": missing,
               "total": len(cases), "passed_cases": 0, "cases": [], "discrepancies": [],
               "public_passed": False, "independent_verification": "not_run"}
    if missing:
        return {**receipt, "classification": "missing_deliverables"}
    compilation = invoke(build, work, home, image, timeout=max(0, deadline-monotonic()), stop=stop)
    if not compilation["passed"]:
        return {**receipt, "classification": classify(compilation),
                "build_diagnostic": compilation["stderr"][-800:] or compilation["stdout"][-800:]}
    result = evaluate(replace(run, oracle=corpus.name), work, home, corpus.parent, image,
                      deadline-monotonic(), stop, public=True)
    return {**receipt, **result, "compiled": True, "public_passed": result["passed"]}


def passing(candidate: dict) -> set[int]:
    return {case["case"] for case in candidate["cases"] if case["verdict"] == "pass"}


def compare(incumbent: dict, challenger: dict, *, protect_passing: bool) -> dict:
    if any(incumbent[key] != challenger[key] for key in ("corpus_sha256", "runner", "total")):
        raise ValueError("cannot compare candidates from different public evaluation conditions")
    old, new = passing(incumbent), passing(challenger)
    losses, gains = sorted(old-new), sorted(new-old)
    old_rank = (incumbent["compiled"], len(old), -len(incumbent["missing"]))
    new_rank = (challenger["compiled"], len(new), -len(challenger["missing"]))
    if challenger["compiled"] and len(challenger["cases"]) != challenger["total"]:
        reason = "incomplete_evaluation"
    elif old_rank[0] and not new_rank[0]:
        reason = "build_regression"
    elif protect_passing and losses:
        reason = "public_regression"
    elif new_rank > old_rank:
        reason = "improved"
    else:
        reason = "tie_keeps_incumbent" if new_rank == old_rank else "lower_public_score"
    return {"accepted": reason == "improved", "reason": reason, "lost_cases": losses,
            "gained_cases": gains}
