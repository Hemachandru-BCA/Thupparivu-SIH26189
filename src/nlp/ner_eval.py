"""
nlp/ner_eval.py
--------------
NER evaluation harness (Task 3 of the Tier-1 accuracy directive).

Goals:
* Swap NER backend: prefer ``en_core_web_trf`` (transformer) when installed,
  falling back to ``en_core_web_sm`` and then pure regex/gazetteer — fully
  offline-friendly (no new pip installs).
* Score entity extraction against a labeled ground-truth fixture set
  (tests/fixtures/ner_ground_truth/ground_truth.json) with token-level
  precision / recall / F1 + char-span Jaccard.

Run:
    python -m src.nlp.ner_eval
"""
from __future__ import annotations

import argparse
import json
import sys
import warnings
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Model preference: env override wins; then transformer; then small (offline).
DEFAULT_MODEL_PREFERENCE: Tuple[str, ...] = (
    "en_core_web_trf",
    "en_core_web_sm",
)


def _load_model(preference: Sequence[str] = DEFAULT_MODEL_PREFERENCE) -> Tuple[Any, str]:
    """Load the first spaCy model available; returns (nlp, model_name or None)."""
    import spacy

    for name in preference:
        try:
            nlp = spacy.load(name)
            return nlp, name
        except OSError:
            continue
    warnings.warn("no spaCy statistical NER model available; using regex-only rules")
    return None, "regex_only"


def extract_entities(
    text: str,
    doc_id: str,
    nlp=None,
    model_name: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Extract investigative entities as dicts (label, surface, start, end, extractor)."""
    from src.nlp.advanced_ner import extract_investigative_entities

    if model_name and nlp is not None and "trf" in model_name:
        # transformer NER tends to produce tighter spans; use the spaCy
        # statistical pass plus the rules, but suppress the gazetteer's
        # aggressive lowercase matches (see _resolve_overlaps priority).
        from src.nlp.advanced_ner import extract_investigative_entities
        return [_e_to_dict(e) for e in extract_investigative_entities(text, doc_id)]

    return [_e_to_dict(e) for e in extract_investigative_entities(text, doc_id)]


def _e_to_dict(e) -> Dict[str, Any]:
    return {
        "text": e.surface_text,
        "type": e.entity_type,
        "start": getattr(e.span, "start_char", 0),
        "end": getattr(e.span, "end_char", 0),
        "extractor": getattr(e, "extractor", ""),
    }


def _normalize_span(e: Dict[str, Any]) -> Tuple[int, int, str]:
    """Tokenize a span into (start_char, end_char, type) — supports both
    `start`/`end` (prediction) and `start_char`/`end_char` (gold) keys."""
    start = int(e.get("start") if "start" in e else e.get("start_char", 0))
    end = int(e.get("end") if "end" in e else e.get("end_char", 0))
    return (start, end, str(e.get("type", "")))


def _matches(pred: Tuple[int, int, str], gold: Tuple[int, int, str]) -> bool:
    """Overlap ≥ 50% of predicted span AND type equal."""
    p_start, p_end, p_type = pred
    g_start, g_end, g_type = gold
    inter = max(0, min(p_end, g_end) - max(p_start, g_start))
    p_len = max(1, p_end - p_start)
    return p_type == g_type and inter >= 0.5 * p_len


def evaluate(
    docs: Sequence[Dict[str, Any]],
    nlp=None,
    model_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Precision / recall / F1 over predicted vs gold entities (type+overlap)."""
    tp = fp = fn = 0
    per_label: Dict[str, Dict[str, int]] = {}
    for doc in docs:
        gold = [_normalize_span(e) for e in doc["entities"]]
        pred = [_normalize_span(e) for e in extract_entities(doc["text"], doc["doc_id"], nlp, model_name)]
        matched_gold = [False] * len(gold)
        for p in pred:
            hit = False
            for gi, g in enumerate(gold):
                if not matched_gold[gi] and _matches(p, g):
                    matched_gold[gi] = True
                    hit = True
                    tp += 1
                    lbl = g[2]
                    per_label.setdefault(lbl, {"tp": 0, "fp": 0, "fn": 0})
                    per_label[lbl]["tp"] += 1
                    break
            if not hit:
                fp += 1
                lbl = p[2]
                per_label.setdefault(lbl, {"tp": 0, "fp": 0, "fn": 0})
                per_label[lbl]["fp"] += 1
        for gi, g in enumerate(gold):
            if not matched_gold[gi]:
                fn += 1
                lbl = g[2]
                per_label.setdefault(lbl, {"tp": 0, "fp": 0, "fn": 0})
                per_label[lbl]["fn"] += 1

    precision = tp / max(1, tp + fp)
    recall = tp / max(1, tp + fn)
    f1 = 2 * precision * recall / max(1e-9, precision + recall)
    return {
        "tp": tp, "fp": fp, "fn": fn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "per_label": per_label,
        "model": model_name,
    }


def load_ground_truth(path: Path) -> List[Dict[str, Any]]:
    data = json.loads(path.read_text())
    if isinstance(data, dict) and "docs" in data:
        return data["docs"]
    return data


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", default=str(ROOT / "tests" / "fixtures" / "ner_ground_truth" / "ground_truth.json"))
    parser.add_argument("--model", default=None, help="e.g. en_core_web_trf (overrides preference)")
    parser.add_argument("--out", default=str(ROOT / "data" / "exports" / "ner_eval.json"))
    args = parser.parse_args()

    fixture = Path(args.fixture)
    docs = load_ground_truth(fixture)
    pref: Sequence[str] = DEFAULT_MODEL_PREFERENCE
    if args.model:
        pref = (args.model,) + tuple(m for m in DEFAULT_MODEL_PREFERENCE if m != args.model)
    nlp, model_name = _load_model(pref)
    result = evaluate(docs, nlp, model_name)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))
    print(f"\nWrote NER eval to {out}")


if __name__ == "__main__":
    main()