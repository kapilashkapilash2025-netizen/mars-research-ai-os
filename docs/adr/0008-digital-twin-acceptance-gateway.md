# ADR 0008: Digital Twin Acceptance Gateway

Candidate producers cannot mutate canonical Twin state. A single deterministic gateway validates schema,
integrity, provenance, expiry, replay and conflict policy, then appends accepted history. This preserves
explicit human/system acceptance boundaries and is not a rover control path.
