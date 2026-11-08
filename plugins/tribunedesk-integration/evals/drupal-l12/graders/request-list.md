---
type: llm
focus:
  source: file
  path: tribunedesk-request.md
---

PASS if the message asks Tribune Desk for: a signing secret for webhooks, the webhook address
(https://news.example.com/...) set for the organization, and a token with the `articles:write`
scope (it may also ask for `articles:read` or the list of image hosts).
FAIL if it is missing one of those three, if it asks for read mode or media library scopes, or if
it contains a secret or token value.
