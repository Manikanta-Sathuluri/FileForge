# Security Policy

## Scope

This project is designed as a local/offline image-to-PDF utility.

The application does not intentionally:
- upload images;
- collect telemetry;
- access browser credentials;
- modify startup persistence;
- execute shell commands;
- download software at runtime.

## Reporting a vulnerability

Please do not publish sensitive security details in a public issue.

Open a private GitHub security advisory if enabled for the repository, or contact the maintainer privately.

## Executable releases

Release executables should be scanned before publication. Official releases should eventually be code-signed with a trusted Windows code-signing certificate.

Users should verify the SHA-256 checksum published with each release.
