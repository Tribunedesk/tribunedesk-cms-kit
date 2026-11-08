---
type: llm
focus:
  source: file
  path: tribunedesk-request.md
---

PASS if the message asks Tribune Desk to switch on read mode for the organization, to enable the
integration, and for a token with `articles:read` and `articles:write`.
FAIL if it asks for a signing secret or a webhook address, or contains a token value.
