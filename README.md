# VoxRacer

VoxRacer is a local profiler for voice-agent response time.

This is an early public development project. The first release will show where
time went during a voice-agent turn. It will not guess missing values.

## Current milestone

The current milestone defines a provider-neutral session model, timing math,
and the first provider adapter.

The first eight values are:

- caller-perceived time to first audio;
- endpointing;
- speech-to-text;
- language-model time to first token;
- tool time;
- text-to-speech time to first audio;
- playback;
- unattributed time.

`ttfab_ms` is the time from caller speech end to first agent audio in a
recording. Other values describe measured internal stages. `null` means that a
value is not measured. It does not mean zero.

The ElevenLabs adapter reads provider transcript timing for speech-to-text and
endpointing. It keeps provider-reported time to first audio in a separate turn
attribute. It does not treat provider timing as caller-perceived audio timing.

## Development

```bash
uv sync
uv run pytest -q
```

The test suite uses local fixtures. It does not call a provider.

Type checking uses strict mypy settings:

```bash
uv run mypy src
```

## License

Apache-2.0. See [LICENSE](LICENSE).
