# VoxRacer roadmap

This is a new public project. The first release is a local profiler for
voice-agent response time.

## 1. Foundation

Status: complete.

- Define the canonical session, turn, and span types.
- Keep eight metric keys.
- Validate session JSON.
- Measure intervals as unions.
- Keep unknown values as `null`.
- Run all tests without a network connection.

## 2. First provider

Status: complete.

- Add the ElevenLabs client.
- Read only the fields needed for timing.
- Filter provider data at parse time.
- Map the result to the canonical model.
- Test with redacted fixtures.
- Read transcript timing for speech-to-text and endpointing.
- Keep provider time to first audio separate from caller-perceived time.

Stop if the provider gives a duration but no reliable position. Do not invent a
position.

## 3. Useful alpha

Status: next.

- Add a simple command for the latest call.
- Show measured, unknown, and not-applicable values.
- Document provider limits.
- Ask voice-agent builders to test the command.
- Collect interviews and waitlist signups.

## 4. Second provider

- Add Vapi after the first provider works.
- Keep provider rules inside the adapter.
- Test different stage boundaries.
- Test URL validation and secret redaction.

## 5. Diagnosis

- Add deterministic findings after measurement works across providers.
- Show the evidence for every finding.
- Never use an LLM for diagnosis.
