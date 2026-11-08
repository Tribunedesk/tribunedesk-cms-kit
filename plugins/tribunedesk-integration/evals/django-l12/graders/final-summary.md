---
type: llm
focus: last_message
---

PASS if the final message, in Polish, sums up the build of levels 1 and 2 in webhook mode, says
the conformance test (tdkit check) passed, and gives launch steps that include putting the
signing secret and the token into the production environment and giving Tribune Desk the
webhook address.
FAIL if it claims levels that were not built (3 or 4), gives read mode or photo library steps,
or does not say whether the conformance test passed.
