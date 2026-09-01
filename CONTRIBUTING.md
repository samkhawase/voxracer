# Contributing

Thank you for helping with VoxRacer.

The main rule is simple: VoxRacer must not invent a number.

- `null` means not measured. It is not zero.
- Do not add overlapping durations.
- Do not create a denominator when the end-to-end value is unknown.
- Do not put provider rules in the analysis layer.
- Do not add raw prompts, transcripts, phone numbers, or API keys to tests.

## Development

```bash
uv sync
uv run pytest -q
uv run mypy src
```

Every change needs a test. Expected timing values must be calculated by hand.
The test suite must work without a provider key and without a network.

## Pull requests

Describe the problem, the change, and the evidence. State when a value is from
a fixture and when it is from a real provider response. Never paste provider
responses into an issue or pull request.
