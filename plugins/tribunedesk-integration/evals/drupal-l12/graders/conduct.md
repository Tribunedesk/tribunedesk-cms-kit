---
type: llm
focus: trace
---

PASS if all of these hold in the session:
- before writing integration code the assistant printed a plan (files to add or change), even
  though the user approved it in advance, and did not stop to wait for approval;
- it ended stages with short summaries (what was done, the result, what is next);
- it wrote to the user in English;
- when it stated a rule of the Tribune Desk contract it named the documentation file it took it
  from (for example `guide/1-article-delivery.md`).
FAIL if any of them is missing, or if the assistant asked the user to approve the plan and
stopped there.
