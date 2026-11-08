---
type: llm
focus: last_message
---

PASS if the final message, in Polish, says plainly that level 4 (the media library) is not tested
by tdkit 1.0, so there is no green conformance test for it, and its launch steps are only about
the token, enabling the integration and the media library, and a manual check with one photo.
FAIL if it claims a passed conformance test for level 4, or its launch steps mention a webhook,
a webhook address or a signing secret.
