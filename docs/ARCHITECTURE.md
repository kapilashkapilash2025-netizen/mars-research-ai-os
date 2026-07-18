# Architecture Notes

The project will begin as a modular monolith. Components should have clear interfaces so they can be separated later only when scale or deployment needs justify it.

Core design principles:

1. Evidence before confidence: research answers must retain source provenance.
2. Reproducibility: inputs, model versions, tools, and outputs should be recorded.
3. Human control: consequential research conclusions require review.
4. Modular tools: agents use explicit, testable capabilities.
5. Open standards: prefer portable formats and public interfaces.

