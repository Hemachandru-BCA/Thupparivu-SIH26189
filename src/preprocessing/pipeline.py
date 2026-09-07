"""Stage 2 preprocessing: synthetic CSVs/FIRs/reports -> cleaned_records.json."""
from __future__ import annotations

import json
import os
import random
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from .cleaner import TextCleaningPipeline
from .fir_simulator import FirSimulator
from .models import StandardizedPerson
from .report_generator import ReportGenerator
from .standardizer import RecordStandardizer


@dataclass
class PipelineConfig:
    input_dir: str = "data/synthetic"
    output_dir: str = "data/processed"
    num_firs: int = 300
    ocr_sample_size: int = 25
    random_seed: int = 42
    include_event_observations: bool = True
    max_call_observations: Optional[int] = 5000
    max_transaction_observations: Optional[int] = 5000
    max_meeting_observations: Optional[int] = 1000


@dataclass
class PreprocessingSummary:
    input_dir: str
    output_dir: str
    num_persons: int
    num_firs: int
    num_reports: int
    num_calls_observed: int
    num_transactions_observed: int
    num_meetings_observed: int
    num_duplicates_removed_flagged: int
    num_records: int


class PreprocessingPipeline:
    def __init__(self, config: Optional[PipelineConfig] = None):
        self.config = config or PipelineConfig()
        self.standardizer = RecordStandardizer()
        self.cleaner = TextCleaningPipeline()
        self.rng = random.Random(self.config.random_seed)

    def run(self) -> PreprocessingSummary:
        cfg = self.config
        in_dir, out_dir = Path(cfg.input_dir), Path(cfg.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        persons = pd.read_csv(in_dir / "persons.csv", dtype=str).fillna("")
        calls = pd.read_csv(in_dir / "calls.csv", dtype=str).fillna("")
        txns = pd.read_csv(in_dir / "transactions.csv", dtype=str).fillna("")
        meetings = pd.read_csv(in_dir / "meetings.csv", dtype=str).fillna("")

        person_rows = {str(r["person_id"]): r for r in persons.to_dict(orient="records")}
        person_records: List[Dict[str, Any]] = []
        for row in persons.to_dict(orient="records"):
            loc = self.standardizer.location.standardize(row.get("address", ""))
            contact = self.standardizer.phone.standardize(row.get("phone_number", ""))
            # Keep the generator's truth metadata in the preprocessing artifact for validation,
            # but never use it as an observed graph relation.
            person_records.append({
                "record_id": row["person_id"],
                "record_type": "person",
                "text": f"{row['full_name']} lives in {loc.city}.",
                "language": "en", "language_confidence": 1.0,
                "is_duplicate": False, "duplicate_of": None,
                "metadata": {"person_id": row["person_id"], "gang_id": row.get("gang_id") or None,
                             "role": row.get("role") or None, "is_hidden_coordinator": row.get("is_hidden_coordinator") == "True",
                             "location": loc.model_dump() if hasattr(loc, "model_dump") else loc.dict(),
                             "phone": contact.model_dump() if hasattr(contact, "model_dump") else contact.dict()},
            })

        # Reports/FIRs retain the original preprocessing story, but event rows below carry the
        # actual graph-bearing observations from the generator.
        firs = FirSimulator(self.rng, self.standardizer).generate(persons, cfg.num_firs)
        reports = ReportGenerator(self.rng).generate(persons, calls, txns, meetings)
        records: List[Dict[str, Any]] = list(person_records)
        records.extend({
            "record_id": f.fir_id, "record_type": "fir", "text": f.narrative, "language": "en",
            "language_confidence": 1.0, "is_duplicate": False, "duplicate_of": None,
            "metadata": {"date_filed": f.date_filed, "location": f.incident_location.model_dump() if hasattr(f.incident_location, "model_dump") else f.incident_location.dict(),
                          "complainant_id": f.complainant_id, "accused_ids": f.accused_ids, "gang_id": f.gang_id},
        } for f in firs)
        records.extend({
            "record_id": r.report_id, "record_type": "intelligence_report", "text": r.summary, "language": "en",
            "language_confidence": 1.0, "is_duplicate": False, "duplicate_of": None,
            "metadata": {"generated_date": r.generated_date, "gang_ids": r.gang_ids, "subject_person_ids": r.subject_person_ids,
                          "evidence_channels": r.evidence_channels},
        } for r in reports)

        def add_obs(record_id: str, text: str, metadata: Dict[str, Any], obs_type: str):
            records.append({"record_id": record_id, "record_type": obs_type, "text": text, "language": "en",
                            "language_confidence": 1.0, "is_duplicate": False, "duplicate_of": None, "metadata": metadata})

        if cfg.include_event_observations:
            call_rows = calls if cfg.max_call_observations is None else calls.head(cfg.max_call_observations)
            for r in call_rows.to_dict(orient="records"):
                caller = person_rows.get(str(r["caller_id"]), {"full_name": r["caller_id"]})["full_name"]
                receiver = person_rows.get(str(r["receiver_id"]), {"full_name": r["receiver_id"]})["full_name"]
                add_obs(r["call_id"], f"{caller} called {receiver} for {r.get('duration_sec','0')} seconds from {r.get('tower_location','')} on {r.get('timestamp','')}.",
                        {"source_person_id": r["caller_id"], "target_person_id": r["receiver_id"], "source_name": caller, "target_name": receiver, "timestamp": r.get("timestamp"), "location": r.get("tower_location"), "duration_sec": r.get("duration_sec")}, "call_observation")
            txn_rows = txns if cfg.max_transaction_observations is None else txns.head(cfg.max_transaction_observations)
            for r in txn_rows.to_dict(orient="records"):
                account = r.get("account_id") or f"TXN-{r['transaction_id']}"
                sender = person_rows.get(str(r["sender_id"]), {"full_name": r["sender_id"]})["full_name"]
                receiver = person_rows.get(str(r["receiver_id"]), {"full_name": r["receiver_id"]})["full_name"]
                add_obs(r["transaction_id"], f"{sender} transferred {r.get('amount','')} {r.get('currency','')} to {receiver} via {r.get('channel','')} using account {account} on {r.get('timestamp','')}.",
                        {"source_person_id": r["sender_id"], "target_person_id": r["receiver_id"], "source_name": sender, "target_name": receiver, "timestamp": r.get("timestamp"), "account_id": account, "amount": r.get("amount"), "currency": r.get("currency"), "channel": r.get("channel")}, "transaction_observation")
            meet_rows = meetings if cfg.max_meeting_observations is None else meetings.head(cfg.max_meeting_observations)
            for r in meet_rows.to_dict(orient="records"):
                ids = [x for x in str(r.get("attendee_ids", "")).split("|") if x]
                names = [person_rows.get(str(pid), {"full_name": pid})["full_name"] for pid in ids]
                if len(names) >= 2:
                    add_obs(r["meeting_id"], f"{', '.join(names)} met at {r['location']} on {r.get('timestamp','')}.",
                            {"attendee_ids": ids, "attendee_names": names, "timestamp": r.get("timestamp"), "location": r.get("location")}, "meeting_observation")

        frame = pd.DataFrame(records)
        # Clean only the text while preserving record-level metadata.
        cleaned = self.cleaner.run(frame[["record_id", "record_type", "text"]])
        dup_map = dict(zip(cleaned["record_id"], cleaned["duplicate_of_index"]))
        lang_map = dict(zip(cleaned["record_id"], zip(cleaned["language"], cleaned["language_confidence"])))
        output: List[Dict[str, Any]] = []
        for idx, record in enumerate(records):
            c = cleaned.iloc[idx]
            dup_idx = c["duplicate_of_index"]
            duplicate_of = records[int(dup_idx)]["record_id"] if pd.notna(dup_idx) else None
            output.append({
                "record_id": record["record_id"], "record_type": record["record_type"],
                "text": c["cleaned_text"], "language": c["language"],
                "language_confidence": float(c["language_confidence"]),
                "is_duplicate": bool(c["is_duplicate"]), "duplicate_of": duplicate_of,
                "metadata": record.get("metadata", {}),
            })
        path = out_dir / "cleaned_records.json"
        path.write_text(json.dumps(output, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
        flagged = sum(1 for r in output if r["is_duplicate"])
        return PreprocessingSummary(str(in_dir), str(out_dir), len(persons), len(firs), len(reports),
                                    len(call_rows) if cfg.include_event_observations else 0,
                                    len(txn_rows) if cfg.include_event_observations else 0,
                                    len(meet_rows) if cfg.include_event_observations else 0,
                                    flagged, len(output))


if __name__ == "__main__":
    print(PreprocessingPipeline().run())
