# Digital Twin Acceptance Gateway

Only `TwinAcceptanceGateway` accepts validated immutable candidates into a canonical `DigitalTwinEngine`.
It validates schema, candidate fingerprint, expiry, source snapshot and replay state before calling the
existing explicit Twin update gateway. It appends history and never rewrites it. Candidates are rejected
for unsupported schema, fingerprint mismatch, duplicate/replay, expiry, source conflict or time reversal.

Acceptance events are immutable and deterministic: validation outcome, snapshot write and history write.
This is software provenance control, not a hardware or autonomous driving path.
