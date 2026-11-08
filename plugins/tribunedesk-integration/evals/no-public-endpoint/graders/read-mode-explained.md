---
type: llm
focus: last_message
---

PASS if the final message, in Polish, says the site cannot receive requests from the internet so
the integration polls Tribune Desk (read mode), says the conformance test passed in read mode,
and its launch steps include scheduling the poll and do not ask for a webhook address.
FAIL if it builds or recommends a webhook, or omits how the poll is run in production.
