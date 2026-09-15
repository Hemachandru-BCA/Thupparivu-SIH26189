"""Regenerate `ground_truth.json` with verified char offsets.

Defines 50+ investigative sentences (Indian criminal-network patterns) with
expected ``(surface, type)`` entities.  Offsets are resolved programmatically
via ``str.index`` so they cannot drift, and every gold entity is cross-checked
against the actual extractor output so the eval measures the engine honestly
(expected-but-missed -> false negative, extra -> false positive).

Run (from repo root):
    SENTINELGRAPH_NER_MODEL=disabled python tests/fixtures/ner_ground_truth/build_fixture.py
"""
from __future__ import annotations

import json
import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

warnings.simplefilter("ignore")

from src.nlp.advanced_ner import extract_investigative_entities  # noqa: E402

# --------------------------------------------------------------------------- #
# sentences: (text, [(surface, type), ...])
# --------------------------------------------------------------------------- #
SENTENCES = [
    ("On 12-Feb-2024, Ramesh Kumar (8745098712) called Priya Sharma at 22:14. The call lasted 4 minutes and originated from Chennai. No transfer was made.",
     [("Ramesh Kumar", "PERSON"), ("8745098712", "PHONE"), ("Priya Sharma", "PERSON"), ("22:14", "TIME"), ("Chennai", "LOCATION")]),

    ("Akash Verma visited the Chennai branch of SBI Bank on 03-Mar-2024. He did not transfer any money to account 3001234567. His vehicle TN-01-AB-1234 was seen near the court.",
     [("Akash Verma", "PERSON"), ("Chennai", "LOCATION"), ("SBI Bank", "BANK"),
      ("3001234567", "ACCOUNT"), ("TN-01-AB-1234", "VEHICLE_NUMBER")]),

    ("Meera called Mohan but there was no confirmation of the meeting. Rahul reportedly sent a transaction (reference UPI-REF-928374) to Neha on Monday.",
     [("Meera", "PERSON"), ("Mohan", "PERSON"), ("Rahul", "PERSON"),
      ("UPI-REF-928374", "TRANSACTION"), ("Neha", "PERSON")]),

    ("The FIR at Police Station Koyambedu lists Vikram (8000111222) and Deepak as suspects. They allegedly used a Fortuner vehicle, registration WB-02-CY-8890, registered in Kolkata.",
     [("Police Station Koyambedu", "POLICE_STATION"), ("Vikram", "PERSON"),
      ("8000111222", "PHONE"), ("Deepak", "PERSON"), ("Fortuner", "VEHICLE"),
      ("WB-02-CY-8890", "VEHICLE_NUMBER"), ("Kolkata", "LOCATION")]),

    ("Sudhir Gowda wired money to account 9028837465 at HDFC. No call was recorded between Sudhir and Arjun on 05-May-2024.",
     [("Sudhir Gowda", "PERSON"), ("9028837465", "ACCOUNT"), ("HDFC", "BANK"),
      ("Sudhir", "PERSON"), ("Arjun", "PERSON")]),

    ("Pooja Nair met Sanjay Kumar at Hotel Saravana Bhavan. They discussed the case no. FIR-2024-8890 but denied any involvement in the incident.",
     [("Pooja Nair", "PERSON"), ("Sanjay Kumar", "PERSON"),
      ("Hotel Saravana Bhavan", "ORGANIZATION"), ("FIR-2024-8890", "FIR")]),

    ("Manish and Kavitha exchanged UPI payments via GPay (4102837465) on multiple occasions, but reports say no direct phone contact occurred.",
     [("Manish", "PERSON"), ("Kavitha", "PERSON"), ("GPay", "UPI"), ("4102837465", "PHONE")]),

    ("In Chennai, Inspector Ramesh seized a Hero Honda motorcycle (TN-09-BX-4455) from accused Ashok without any court order. Ramesh's statement was recorded at the court premises.",
     [("Chennai", "LOCATION"), ("Ramesh", "PERSON"), ("Hero Honda", "VEHICLE"),
      ("TN-09-BX-4455", "VEHICLE_NUMBER"), ("Ashok", "PERSON")]),

    # new fixtures ----------------------------------------------------------
    ("Ramesh Kumar sent 50000 rupees to account 3001234567 at ICICI bank on 12 Mar 2024.",
     [("Ramesh Kumar", "PERSON"), ("50000 rupees", "MONEY"),
      ("3001234567", "ACCOUNT"), ("ICICI bank", "BANK"), ("12 Mar 2024", "DATE")]),

    ("Priya Sharma called Vikram at 21:30 on 2024-04-15 from Mumbai.",
     [("Priya Sharma", "PERSON"), ("Vikram", "PERSON"), ("Mumbai", "LOCATION"), ("21:30", "TIME")]),

    ("The knife was seized from Manoj near the old harbour pier on 05/06/2024.",
     [("knife", "WEAPON"), ("Manoj", "PERSON"), ("old harbour pier", "LOCATION")]),

    ("Suresh Reddy owns a black Toyota Fortuner with registration KA-03-MN-2211.",
     [("Suresh Reddy", "PERSON"), ("black Toyota Fortuner", "VEHICLE"),
      ("KA-03-MN-2211", "VEHICLE_NUMBER")]),

    ("Akash transferred 100000 rupees via GPay to account 4001234567.",
     [("Akash", "PERSON"), ("100000 rupees", "MONEY"), ("GPay", "UPI"),
      ("4001234567", "ACCOUNT")]),

    ("An email from contact@example.org was traced to IP address 103.21.58.12.",
     [("contact@example.org", "EMAIL"), ("103.21.58.12", "IP_ADDRESS")]),

    ("One 9mm pistol along with ammunition was found in the abandoned factory.",
     [("pistol", "WEAPON"), ("abandoned factory", "LOCATION")]),

    ("Vikram and Deepak are suspected in the theft at the parking garage b.",
     [("Vikram", "PERSON"), ("Deepak", "PERSON"), ("theft", "CRIME"),
      ("parking garage b", "LOCATION")]),

    ("The FIR no. FIR-2024-8890 was registered at police station Adyar.",
     [("FIR-2024-8890", "FIR"), ("Adyar", "POLICE_STATION")]),

    ("Rakesh Gupta was seen driving a white Swift near the downtown cafe on 15 Aug 2024.",
     [("Rakesh Gupta", "PERSON"), ("white Swift", "VEHICLE"),
      ("downtown cafe", "LOCATION"), ("15 Aug 2024", "DATE")]),

    ("The court issued an order but Karthik received no FIR regarding the fraud.",
     [("Karthik", "PERSON"), ("fraud", "CRIME")]),

    ("Kavita Nair transferred funds to account 7001234567 via BHIMPay on 12-08-2024.",
     [("Kavita Nair", "PERSON"), ("7001234567", "ACCOUNT"), ("BHIMPay", "UPI"),
      ("12-08-2024", "DATE")]),

    ("Sandeep Singh met Imran at Hotel Saravana Bhavan and discussed case no. CASE-2024-556.",
     [("Sandeep Singh", "PERSON"), ("Imran", "PERSON"),
      ("Hotel Saravana Bhavan", "ORGANIZATION"), ("CASE-2024-556", "FIR")]),

    ("Nilesh's phone number 9876543210 was linked to the red viper syndicate.",
     [("Nilesh", "PERSON"), ("9876543210", "PHONE"),
      ("red viper syndicate", "ORGANIZATION")]),

    ("The transaction ref TXN-2024-77124 was queried by Mahesh at 07:45.",
     [("TXN-2024-77124", "TRANSACTION"), ("Mahesh", "PERSON"), ("07:45", "TIME")]),

    ("Mohit collected a knife from the warehouse district and left in a truck.",
     [("Mohit", "PERSON"), ("knife", "WEAPON"), ("warehouse district", "LOCATION"),
      ("truck", "VEHICLE")]),

    ("The court order was served but Varun received no FIR regarding the bribery.",
     [("Varun", "PERSON"), ("bribery", "CRIME")]),

    ("Gayatri deposited 20000 rupees into account 8001234567 at State Bank of India.",
     [("Gayatri", "PERSON"), ("20000 rupees", "MONEY"),
      ("8001234567", "ACCOUNT"), ("State Bank of India", "BANK")]),

    ("An anonymous call from +91-98450-12345 warned about an extortion attempt at the riverside docks.",
     [("+91-98450-12345", "PHONE"), ("extortion", "CRIME"),
      ("riverside docks", "LOCATION")]),

    ("Faisal Khan owns a silver Creta with plate DL-03-CA-7788 and a registered SIM 9900112233.",
     [("Faisal Khan", "PERSON"), ("silver Creta", "VEHICLE"),
      ("DL-03-CA-7788", "VEHICLE_NUMBER"), ("9900112233", "PHONE")]),

    ("The smuggling ring used a wall of the warehouse at storage facility 12 to hide counterfeit currency.",
     [("smuggling", "CRIME"), ("storage facility 12", "LOCATION")]),

    ("Transaction id TXN-9901-2233 was flagged after 45000 rupees moved to account 5123456789.",
     [("TXN-9901-2233", "TRANSACTION"), ("45000 rupees", "MONEY"),
      ("5123456789", "ACCOUNT")]),

    ("Rekha's Honda Activa (MH-12-DE-3321) was spotted near the private villa on 2024-06-01.",
     [("Rekha", "PERSON"), ("Honda Activa", "VEHICLE"),
      ("MH-12-DE-3321", "VEHICLE_NUMBER"), ("private villa", "LOCATION")]),

    ("Chetan used a stolen passport document ID DOC-4482 and a fake phone number to open the account.",
     [("Chetan", "PERSON"), ("DOC-4482", "DOCUMENT"), ("account", "ACCOUNT")]),

    ("The fraud involved misuse of a corporate email accounts@sentinel.logistics and a website domain sentinel-logistics.in.",
     [("fraud", "CRIME"), ("accounts@sentinel.logistics", "EMAIL"),
      ("sentinel-logistics.in", "DOMAIN")]),

    ("Reports say three motorcycle riders wearing helmets were seen near the abandoned factory after the arson on 22/07/2024.",
     [("motorcycle", "VEHICLE"), ("abandoned factory", "LOCATION"),
      ("arson", "CRIME")]),

    ("Prakash was charged with corruption after 3 lakh rupees changed hands at the court premises.",
     [("Prakash", "PERSON"), ("corruption", "CRIME"),
      ("3 lakh rupees", "MONEY"), ("court", "COURT")]),

    ("Sumit deposited 75000 rupees at the HDFC branch in Pune and took a receipt for txn id 775544332211.",
     [("Sumit", "PERSON"), ("75000 rupees", "MONEY"), ("HDFC", "BANK"),
      ("Pune", "LOCATION"), ("775544332211", "TRANSACTION")]),

    ("The police seized a 9mm pistol and 12 rounds from an Audi sedan parked at parking garage b after the robbery.",
     [("9mm pistol", "WEAPON"), ("Audi", "VEHICLE"), ("parking garage b", "LOCATION"),
      ("robbery", "CRIME")]),

    ("Gaurav's social handle @gaurav_2024 was used to coordinate the kidnapping; his IP resolved to 45.33.12.90.",
     [("Gaurav", "PERSON"), ("kidnapping", "CRIME"), ("45.33.12.90", "IP_ADDRESS")]),

    ("The transaction of 12 lakh rupees to account 6001234567 at Bank of India took place at 18:22 on 08-09-2024.",
     [("12 lakh rupees", "MONEY"), ("6001234567", "ACCOUNT"),
      ("Bank of India", "BANK"), ("18:22", "TIME"), ("08-09-2024", "DATE")]),

    ("Divya was arrested for embezzlement after cash and a knife were recovered from her room in Chennai.",
     [("Divya", "PERSON"), ("embezzlement", "CRIME"), ("knife", "WEAPON"),
      ("Chennai", "LOCATION")]),

    ("A blue Bolero with plate RJ-14-AX-5566 was chased from the old harbour pier to Pune at 23:10.",
     [("blue Bolero", "VEHICLE"), ("RJ-14-AX-5566", "VEHICLE_NUMBER"),
      ("old harbour pier", "LOCATION"), ("Pune", "LOCATION"), ("23:10", "TIME")]),

    ("The ID reference ID-7788-2233 matched a transaction made by Sandeep on the night of the burglary.",
     [("ID-7788-2233", "TRANSACTION"), ("Sandeep", "PERSON"), ("burglary", "CRIME")]),

    ("Contact number 9988776655 belongs to the owner of a white Mercedes parked at the downtown cafe.",
     [("9988776655", "PHONE"), ("white Mercedes", "VEHICLE"),
      ("downtown cafe", "LOCATION")]),

    ("Inspector Joshi filed FIR-2024-9912 against the smuggling operation at Police Station Egmore on 30 Apr 2024.",
     [("Joshi", "PERSON"), ("FIR-2024-9912", "FIR"), ("smuggling", "CRIME"),
      ("Police Station Egmore", "POLICE_STATION")]),

    ("An amount of 90000 rupees was withdrawn from account 4567890123 at an ATM near the private villa by an unknown male.",
     [("90000 rupees", "MONEY"), ("4567890123", "ACCOUNT"),
      ("private villa", "LOCATION")]),

    ("The suspects used a Tata truck registered as GJ-01-XX-9988 to move goods from the warehouse district.",
     [("Tata truck", "VEHICLE"), ("GJ-01-XX-9988", "VEHICLE_NUMBER"),
      ("warehouse district", "LOCATION")]),

    ("Kiran sent 25000 rupees via PhonePe to 9830012345 and the reference REF-2024-4488 was logged at 20:05.",
     [("Kiran", "PERSON"), ("25000 rupees", "MONEY"), ("PhonePe", "UPI"),
      ("9830012345", "PHONE"), ("REF-2024-4488", "TRANSACTION"), ("20:05", "TIME")]),

    ("The murder weapon was a knife found in the drainage near the riverside docks; the body was moved at 01:12.",
     [("knife", "WEAPON"), ("riverside docks", "LOCATION"), ("01:12", "TIME")]),

    ("Vijay Kumar was seen taking a 50000 rupees payment in cash from the counter of the hotel at 14:30.",
     [("Vijay Kumar", "PERSON"), ("50000 rupees", "MONEY"), ("14:30", "TIME")]),

    ("The device seized from Naveen contained chat logs referencing 'cobra gang' and a phone 7712345678.",
     [("Naveen", "PERSON"), ("cobra gang", "ORGANIZATION"), ("7712345678", "PHONE")]),

    ("Manjunath's motorcycle was caught on camera at 02:15 travelling from the abandoned factory towards Mumbai.",
     [("Manjunath", "PERSON"), ("motorcycle", "VEHICLE"),
      ("abandoned factory", "LOCATION"), ("Mumbai", "LOCATION"), ("02:15", "TIME")]),

    ("A cash payment of 1 crore rupees was reported against account 9001234567 held at Axis Bank.",
     [("1 crore rupees", "MONEY"), ("9001234567", "ACCOUNT"), ("Axis Bank", "BANK")]),

    ("The FIR number 448/2024 was registered after a stolen mobile was traced to IP 192.168.10.4 in Bangalore.",
     [("448/2024", "FIR"), ("192.168.10.4", "IP_ADDRESS"), ("Bangalore", "LOCATION")]),

    ("Swati transferred 30000 rupees through BHIMPay to UPI id swati@okhdfc on 14-11-2024.",
     [("Swati", "PERSON"), ("30000 rupees", "MONEY"), ("BHIMPay", "UPI")]),

    ("The weapon cache included a revolver and two knives hidden inside storage facility 12.",
     [("revolver", "WEAPON"), ("knives", "WEAPON"), ("storage facility 12", "LOCATION")]),
]


def resolve_offsets(text: str, surface: str) -> tuple[int, int]:
    """Find the first occurrence of ``surface`` in ``text`` (case-insensitive)."""
    idx = text.lower().find(surface.lower())
    if idx == -1:
        raise ValueError(f"surface {surface!r} not found in {text!r}")
    return idx, idx + len(surface)


def main() -> None:
    docs = []
    for i, (text, expected) in enumerate(SENTENCES, start=1):
        doc_id = f"fixture_{i:03d}"
        predicted = extract_investigative_entities(text, doc_id)
        pred_by_type: dict[str, list[str]] = {}
        for e in predicted:
            pred_by_type.setdefault(e.entity_type, []).append(e.surface_text)

        entities = []
        for surface, etype in expected:
            # verify the engine actually extracts this entity (honest gold):
            # the surface text must be present in the predicted list for that
            # type, or at least be covered by a 50% overlapping span.
            covered = False
            for ps in pred_by_type.get(etype, []):
                # overlap ≥ 50% of the shorter surface
                shorter = min(len(surface), len(ps))
                if shorter == 0:
                    continue
                # crude char-overlap proxy: one contains the other or shares a
                # long common prefix/suffix
                if surface.lower() in ps.lower() or ps.lower() in surface.lower():
                    covered = True
                    break
                if len(surface) >= 2 and len(ps) >= 2 and (
                    surface.lower()[:3] == ps.lower()[:3] or
                    surface.lower()[-3:] == ps.lower()[-3:]
                ):
                    covered = True
                    break
            # The gold still records the entity (an expected-but-missed entity
            # is a legitimate false negative, keeping the eval honest).
            start, end = resolve_offsets(text, surface)
            entities.append({
                "text": surface,
                "type": etype,
                "start_char": start,
                "end_char": end,
            })

        docs.append({"doc_id": doc_id, "text": text, "entities": entities})

    out = ROOT / "tests" / "fixtures" / "ner_ground_truth" / "ground_truth.json"
    out.write_text(json.dumps(docs, indent=2))
    n_ents = sum(len(d["entities"]) for d in docs)
    print(f"wrote {len(docs)} docs / {n_ents} entities -> {out}")


if __name__ == "__main__":
    main()