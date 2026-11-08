---
type: llm
focus:
  source: file
  path: tribunedesk-request.md
---

PASS if the message asks Tribune Desk for: a signing secret for webhooks, the webhook address
(https://blog.example.com/...) set for the organization, and a token with the `articles:write`
scope (it may also ask for `articles:read` or the list of image hosts, for downloading images).
FAIL if it is missing one of those three, if it asks for read mode, for media library scopes
(`media:read`, `media:write`) or for the "read more" box, or if it contains a secret or token
value.
