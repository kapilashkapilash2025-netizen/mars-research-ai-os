# Contributing

All development is handled through pull requests.

## Workflow

1. Start from the latest `main` branch.
2. Create a focused branch such as `agent/dataset-catalog` or `feature/evidence-api`.
3. Add or update automated tests with the implementation.
4. Run the local checks before pushing.
5. Open a draft pull request early and describe the scientific or engineering goal.
6. Merge only after review and passing checks.

Do not commit secrets, private datasets, model weights, or generated research artifacts.

## Local checks

```bash
python -m pytest
python -m ruff check .
```

