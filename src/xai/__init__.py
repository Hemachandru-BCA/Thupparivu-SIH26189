"""SentinelGraph AI - XAI layer.

This package implements the evidence-provenance, finding and dossier
machinery that turns raw graph analytics into human-reviewable,
evidence-grounded intelligence artifacts.

Design rules (see FULL_IMPLEMENTATION_PROMPT.md Phase C-F):

* every graph-derived conclusion must trace back to source records;
* observed facts, model inferences and unknowns are labelled separately;
* evidence is never fabricated - ids are validated before use;
* the default LLM provider is a deterministic offline mock.
"""
