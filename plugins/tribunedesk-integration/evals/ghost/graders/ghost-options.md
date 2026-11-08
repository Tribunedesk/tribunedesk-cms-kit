---
type: llm
focus: last_message
---

PASS if the reply, in Polish, recognises the site runs on Ghost(Pro), explains that Ghost cannot
receive Tribune Desk's webhook on its own so the integration needs either a small bridge service
or read mode (polling), says the media library (level 4) is not possible with Ghost, and asks
one question with a recommendation before building anything.
FAIL if it starts building a Ghost plugin or theme code, promises the media library, or asks
several questions at once without a recommendation.
