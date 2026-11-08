---
type: llm
focus:
  source: file
  path: tribunedesk-request.md
---

PASS if the message asks Tribune Desk to enable the integration and the media library for the
organization and for a token with `media:read`, `media:write` and `settings:read` (more scopes
are fine).
FAIL if it asks for a signing secret, a webhook address or read mode, or contains a token value.
