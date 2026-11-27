# taxonomy

Level 3 with categories and tags (audit 2026-11-27: every parity run skipped `l3-taxonomy*`,
because none of the blogs had them). A Django blog whose posts have a category and tags builds
levels 1-3, webhook; `l3-taxonomy-sync` and `l3-taxonomy` must pass, not be skipped.

## Prompt

Build our blog's integration with Tribune Desk: articles land in the CMS as drafts, Tribune Desk gets the link back after we publish, and the full content (internal links, the read-more box, SEO, author, AI label, and our categories and tags). The blog is public over https at https://blog.example.com, so a webhook is fine. I approve the plan in advance: do not wait for my go-ahead, but print the plan and sum up every stage. Also save the message for our Tribune Desk contact as `tribunedesk-request.md` in the project folder.

## Review

Judged by reading the run (the runner prints the files and the final message).

### conduct (the whole session)

PASS if all of these hold in the session:
- plan before code (SKILL.md, "The plan before code"): before its first edit of integration
  code the assistant wrote the plan (files to add and change) as a progress line, and did
  not stop to wait for approval;
- the final message carries the plan as built (files added and changed, per level) and a table
  of the stages with the result of each; short progress lines between stages are enough;
- it wrote to the user in English;
- when it stated a rule of the Tribune Desk contract it named the documentation file it took it
  from (for example `guide/3-full-content.md`).
FAIL if any of them is missing.

### taxonomy (the code)

PASS if a delivery's terms are set by `cms_term_id`, else by name, a term is never created from
a delivery, a send without `taxonomy` leaves the post's terms alone, and the daily full run (one
`run_id`, `is_last` on the last page) is a scheduled job named in the launch steps.
FAIL if any of them is missing.

### final-summary (the final message)

PASS if the final message, in English, sums up levels 1-3 in webhook mode, says `tdkit check`
passed with `l3-taxonomy-sync` and `l3-taxonomy` among the passed scenarios, and gives launch
steps including the schedule of the taxonomy run.
FAIL if the taxonomy scenarios were skipped.

### request-list (file tribunedesk-request.md)

PASS if the message asks for a signing secret, the webhook address set for the organization and
a token with `articles:write`.
FAIL if one of them is missing, if it asks for media library scopes, or it contains a secret or
token value.
