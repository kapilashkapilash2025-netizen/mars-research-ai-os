# ADR 0013: Reproducible image and secure-update foundation

Use deterministic manifests and A/B slot state simulation before image flashing. A new slot must pass health
checks before activation; failed health rolls back. This is not a cryptographic signing or physical update implementation.
