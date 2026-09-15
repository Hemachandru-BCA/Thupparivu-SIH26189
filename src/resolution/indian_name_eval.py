"""
resolution/indian_name_eval.py
-------------------------------
Task 4 of the Tier-1 accuracy directive: entity resolution for Indian
name variations (spelling variants, reordering, initials, transliterations).

Evaluates the existing soundex/honorific matcher against a labeled
Indian-name pair set, then scores an embeddings-augmented matcher that adds
character n-gram overlap (pure numpy/difflib — no external embeddings).

Run:
    python -m src.resolution.indian_name_eval
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np

from src.resolution.entity_matcher import compare_names, MatchConfig, MatchResult


def character_ngrams(name: str, n: int = 3) -> Dict[str, int]:
    """Character n-gram frequency map for a normalized name."""
    norm = "".join(ch for ch in name.lower() if ch.isalnum())
    if len(norm) < n:
        return {norm: 1} if norm else {}
    out: Dict[str, int] = {}
    for i in range(len(norm) - n + 1):
        g = norm[i:i + n]
        out[g] = out.get(g, 0) + 1
    return out


def ngram_overlap(name_a: str, name_b: str, n: int = 3) -> float:
    """Jaccard-style n-gram overlap in [0, 1]."""
    ga, gb = character_ngrams(name_a, n), character_ngrams(name_b, n)
    if not ga or not gb:
        return 0.0
    inter = sum(min(ga.get(g, 0), gb.get(g, 0)) for g in set(ga) | set(gb))
    union = sum(max(ga.get(g, 0), gb.get(g, 0)) for g in set(ga) | set(gb))
    return inter / max(1.0, union)


def embeddings_augmented_score(name_a: str, name_b: str) -> float:
    """Blend existing phonetic/token match with char n-gram overlap to
    handle Indian transliteration variants that Soundex misses
    (e.g. 'Aiyyer' vs 'Iyer', 'Guptha' vs 'Gupta')."""
    base = compare_names(name_a, name_b)
    ngram2 = ngram_overlap(name_a, name_b, n=2)
    ngram3 = ngram_overlap(name_a, name_b, n=3)
    # Strong exact/token-set matches pass through unchanged.
    if base.score >= 0.95:
        return base.score
    # Blend: phonetic 60%, 2-gram 20%, 3-gram 20%.
    return 0.6 * base.score + 0.2 * ngram2 + 0.2 * ngram3


def evaluate(
    pairs: List[Dict[str, Any]],
    score_fn,
    threshold: float = 0.55,
) -> Dict[str, Any]:
    tp = fp = tn = fn = 0
    details: List[Dict[str, Any]] = []
    for pair in pairs:
        s = score_fn(pair["a"], pair["b"])
        pred = int(s >= threshold)
        truth = int(pair["label"])
        if pred == 1 and truth == 1:
            tp += 1
        elif pred == 1 and truth == 0:
            fp += 1
        elif pred == 0 and truth == 0:
            tn += 1
        else:
            fn += 1
        details.append({"a": pair["a"], "b": pair["b"], "label": truth,
                        "score": round(s, 4), "pred": pred})
    precision = tp / max(1, tp + fp)
    recall = tp / max(1, tp + fn)
    f1 = 2 * precision * recall / max(1e-9, precision + recall)
    return {
        "tp": tp, "fp": fp, "tn": tn, "fn": fn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "threshold": threshold,
        "details": details,
    }


def load_pairs(path: Path) -> List[Dict[str, Any]]:
    data = json.loads(path.read_text())
    pairs = data.get("pairs") or data
    return pairs


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--fixture",
        default=str(ROOT / "tests" / "fixtures" / "entity_resolution" / "indian_name_pairs.json"),
    )
    parser.add_argument("--out", default=str(ROOT / "data" / "exports" / "indian_name_eval.json"))
    parser.add_argument("--threshold", type=float, default=0.55)
    args = parser.parse_args()

    pairs = load_pairs(Path(args.fixture))
    n_test = len(pairs)
    positives = sum(1 for p in pairs if p["label"] == 1)
    negatives = n_test - positives

    soundex_result = evaluate(pairs, lambda a, b: compare_names(a, b).score, args.threshold)
    augmented = evaluate(pairs, embeddings_augmented_score, args.threshold)

    result = {
        "n_test_pairs": n_test,
        "n_positive": positives,
        "n_negative": negatives,
        "soundex_baseline": {k: soundex_result[k] for k in ("tp", "fp", "tn", "fn", "precision", "recall", "f1")},
        "embeddings_augmented": {k: augmented[k] for k in ("tp", "fp", "tn", "fn", "precision", "recall", "f1")},
        "threshold": args.threshold,
        "augmented_details": augmented["details"],
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2))
    print(json.dumps({k: v for k, v in result.items() if k != "augmented_details"}, indent=2))
    print(f"\nWrote Indian name-pair eval to {out}")


if __name__ == "__main__":
    main()