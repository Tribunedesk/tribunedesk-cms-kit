# Presenting an update

`TDKIT integrators --from <old> --to <new> --levels <levels> --mode <delivery>` prints the
actions the CHANGELOG lists for integrators between the two versions, already filtered to the
levels and mode in `tribunedesk.json`. Each item has `version`, `tags` (`L1`-`L4`, `read`) and
`action`. A warning on stderr about an unknown tag means the CHANGELOG is newer than this kit:
mention it and recommend updating the plugin (`/plugin update`).

## How to show the list

Group by level, oldest version first inside each group (the order the changes were made), and
give every item one line of recommendation:

```
Level 1 (article delivery)
  3.3.0  Verify the signature; X-Webhook-Secret is no longer sent.
         -> Already done: your receiver verifies the signature (td/webhook.py:42).
  3.4.0  Skip a body whose sent_at is older than the one applied last.
         -> To do: store sent_at per article and compare before saving. Small change.
Level 2 (link back)
  3.4.0  Send social_queue_exclude with permalink when the CMS has such a setting.
         -> Not applicable: your CMS has no such setting.
```

For each item:

1. Read the CHANGELOG entry and the guide section it refers to in the new documentation.
2. Look at the code: is it **already done**, **to do**, or **not applicable** to this CMS?
3. For "to do", say the size (small / medium / large) and the files it touches.

Recommend doing every "to do" item of a breaking change (marked **Breaking** in the CHANGELOG)
first. Stop for approval before changing code, unless the user pre-approved.

## After the changes

1. Run the project's tests.
2. Run `TDKIT check --docs <path>` for the manifest's levels and mode, with the `path` that
   `TDKIT docs` printed for the new contract.
3. `TDKIT manifest write` with the new contract and the new report; `TDKIT manifest validate`.
4. Summarise: what changed, what was already done, what did not apply.

An empty list still needs steps 2-3, so the manifest records the new contract.
