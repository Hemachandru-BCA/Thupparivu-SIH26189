"""Stage 3 extraction: cleaned records -> entities, relations and event links."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.extraction.event_extractor import EventExtractor
from src.extraction.ner import EntityExtractor, build_nlp
from src.extraction.relation_extractor import RelationExtractor, Triplet


@dataclass
class ExtractionConfig:
    input_path: str = "data/processed/cleaned_records.json"
    output_path: str = "data/graph_triplets.json"
    spacy_model: Optional[str] = "en_core_web_sm"
    infer_co_occurrence: bool = True
    max_records: Optional[int] = None
    use_person_gazetteer: bool = True
    use_location_gazetteer: bool = True


@dataclass
class ExtractionSummary:
    input_path: str
    output_path: str
    num_records_processed: int
    num_entities: int
    num_triplets: int
    num_events: int
    relation_counts: Dict[str, int]
    spacy_backend: str

    def __str__(self) -> str:
        return (f"Extraction complete\n  Records processed: {self.num_records_processed}\n"
                f"  Entities found:    {self.num_entities}\n  Triplets emitted:  {self.num_triplets}\n"
                f"  Events emitted:    {self.num_events}\n  spaCy backend:     {self.spacy_backend}\n"
                f"  Output written to: {self.output_path}")


class ExtractionPipeline:
    def __init__(self, config: Optional[ExtractionConfig] = None):
        self.config = config or ExtractionConfig()
        self.nlp = None
        self.entity_extractor = None
        self.relation_extractor = RelationExtractor(infer_co_occurrence=self.config.infer_co_occurrence)
        self.event_extractor = EventExtractor()

    @staticmethod
    def _gazetteer(records: List[Dict[str, Any]]) -> Dict[str, List[str]]:
        people, locations = set(), set()
        for r in records:
            if r.get("record_type") == "person":
                text = str(r.get("text") or "")
                name = text.split(" lives in ", 1)[0].strip()
                if name:
                    people.add(name)
                loc = ((r.get("metadata") or {}).get("location") or {}).get("city")
                if loc:
                    locations.add(str(loc))
            meta = r.get("metadata") or {}
            if meta.get("location"):
                locations.add(str(meta["location"]))
        return {"PERSON": sorted(people), "LOCATION": sorted(locations)}

    def run(self) -> ExtractionSummary:
        with open(self.config.input_path, "r", encoding="utf-8") as fh:
            records = json.load(fh)
        if self.config.max_records is not None:
            records = records[: self.config.max_records]

        gaz = self._gazetteer(records)
        extra = {}
        if self.config.use_person_gazetteer:
            extra["PERSON"] = gaz["PERSON"]
        if self.config.use_location_gazetteer:
            extra["LOCATION"] = gaz["LOCATION"]
        self.nlp = build_nlp(self.config.spacy_model, extra_gazetteer=extra)
        self.entity_extractor = EntityExtractor(nlp=self.nlp)

        all_entities, all_triplets, all_events = [], [], []
        for record in records:
            text = str(record.get("text") or "")
            if not text.strip():
                continue
            record_type = str(record.get("record_type") or "")
            record_id = str(record.get("record_id") or "")
            if record_type in {"call_observation", "transaction_observation", "meeting_observation"}:
                entities = []
                triplets = self._structured_triplets(record)
                events, links = [], []
            else:
                doc = self.entity_extractor.process(text)
                entities = self.entity_extractor.entities_from_doc(doc)
                triplets = self.relation_extractor.extract(doc, record_id=record_id)
                events, links = self.event_extractor.extract(entities, triplets, record=record)
            all_entities.extend(e.to_dict() for e in entities)
            all_triplets.extend(t.to_dict() for t in triplets)
            all_triplets.extend(t.to_dict() for t in links)
            all_events.extend(e.to_dict() for e in events)

        # Collapse repeated event observations into deterministic evidence edges.
        # Keep a count plus one representative timestamp; the raw synthetic CSVs
        # remain the full-resolution source of truth.
        aggregated: Dict[tuple, Dict[str, Any]] = {}
        for t in all_triplets:
            key = (str(t.get("source")), str(t.get("relation")), str(t.get("target")))
            if key not in aggregated:
                t = dict(t)
                t["attributes"] = dict(t.get("attributes") or {})
                t["attributes"]["observation_count"] = 1
                aggregated[key] = t
            else:
                a = aggregated[key].setdefault("attributes", {})
                a["observation_count"] = int(a.get("observation_count", 1)) + 1
        all_triplets = sorted(aggregated.values(), key=lambda x: (str(x.get("source")), str(x.get("relation")), str(x.get("target"))))

        relation_counts: Dict[str, int] = {}
        for t in all_triplets:
            relation_counts[t["relation"]] = relation_counts.get(t["relation"], 0) + 1
        backend = "fallback" if getattr(self.nlp, "_model_fallback", False) else (self.config.spacy_model or "blank")
        output = {
            "metadata": {"generated_at": datetime.now(timezone.utc).isoformat(),
                         "source_file": self.config.input_path, "num_records": len(records),
                         "spacy_backend": backend, "num_entities": len(all_entities),
                         "num_triplets": len(all_triplets), "num_events": len(all_events),
                         "relation_counts": relation_counts},
            "entities": all_entities,
            "triplets": all_triplets,
            "events": all_events,
        }
        os.makedirs(os.path.dirname(self.config.output_path) or ".", exist_ok=True)
        with open(self.config.output_path, "w", encoding="utf-8") as fh:
            json.dump(output, fh, indent=2, ensure_ascii=False, default=str)
        return ExtractionSummary(self.config.input_path, self.config.output_path, len(records),
                                 len(all_entities), len(all_triplets), len(all_events), relation_counts, backend)

# Attach outside the class body above as a static method without changing the public API.
def _structured_triplets(record: Dict[str, Any]) -> List[Triplet]:
    meta = record.get("metadata") or {}
    rid = str(record.get("record_id") or "")
    text = str(record.get("text") or "")
    out: List[Triplet] = []
    rtype = str(record.get("record_type") or "")
    def add(source: str, st: str, relation: str, target: str, tt: str, attrs: Dict[str, Any]):
        out.append(Triplet(source=source, source_type=st, relation=relation, target=target, target_type=tt,
                            record_id=rid, evidence=text, sentence_index=0, confidence=1.0, attributes=attrs))
    if rtype == "call_observation":
        add(meta.get("source_name", meta.get("source_person_id", "")), "PERSON", "CALLED", meta.get("target_name", meta.get("target_person_id", "")), "PERSON",
            {"source_person_id": meta.get("source_person_id"), "target_person_id": meta.get("target_person_id"), "location": meta.get("location"), "duration_sec": meta.get("duration_sec"), "timestamp": meta.get("timestamp")})
    elif rtype == "transaction_observation":
        source, target, account = meta.get("source_name", meta.get("source_person_id", "")), meta.get("target_name", meta.get("target_person_id", "")), meta.get("account_id", "")
        attrs = {"amount": meta.get("amount"), "currency": meta.get("currency"), "channel": meta.get("channel"), "account_id": account, "timestamp": meta.get("timestamp")}
        add(source, "PERSON", "TRANSFERRED_TO", target, "PERSON", attrs)
        if account:
            add(source, "PERSON", "USES_ACCOUNT", account, "ACCOUNT", {"account_id": account, "timestamp": meta.get("timestamp")})
            add(target, "PERSON", "USES_ACCOUNT", account, "ACCOUNT", {"account_id": account, "timestamp": meta.get("timestamp")})
    elif rtype == "meeting_observation":
        ids = [str(x) for x in (meta.get("attendee_ids") or [])]
        names = [str(x) for x in (meta.get("attendee_names") or [])]
        if len(names) != len(ids):
            names = ids
        attrs = {"location": meta.get("location"), "timestamp": meta.get("timestamp"), "attendee_ids": ids}
        for i, source in enumerate(names):
            for target in names[i + 1:]:
                add(source, "PERSON", "MET", target, "PERSON", attrs)
    return out

ExtractionPipeline._structured_triplets = staticmethod(_structured_triplets)

if __name__ == "__main__":
    print(ExtractionPipeline().run())
