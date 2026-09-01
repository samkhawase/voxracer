# Security

Do not open a public issue for a security problem. Use the repository's private
security reporting channel.

VoxRacer handles provider credentials and private call telemetry. Report any
case where the project:

- prints or stores an API key;
- prints a presigned URL or its query string;
- exposes a prompt, transcript, phone number, or tool argument;
- fetches an unexpected URL;
- writes private provider data to disk.

Use read-only provider keys. VoxRacer must never place a call.
