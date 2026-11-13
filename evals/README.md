# Trying the Claude Code plugin on real projects

Six scenarios in `evals/scenarios/` describe what the skill must do on a real project: build,
update or only explain an integration. `evals/run.py` runs one of them on this machine, on
Windows as well: no WSL and no `claude plugin eval` (that command refuses runs with a shell on
native Windows).

| Scenario | Project | What it checks |
|---|---|---|
| `django-l12` | Django blog | levels 1+2, webhook, Polish, plan approved up front |
| `drupal-l12` | Drupal 11 | the same in English, with the `tribunedesk/cms-protocol` library (needs PHP 8.3 and Composer on PATH; the site is built once, ~7 min) |
| `photos-only` | Django blog with a photo library | level 4 only: no webhook, a green `tdkit check --levels 4` |
| `no-public-endpoint` | Django blog on an intranet | read mode chosen and tested |
| `update-3.2` | Django blog with an integration for 3.2.0-draft | update mode: change list, new manifest |
| `ghost` | Ghost(Pro) README | bridge or read mode explained, no code written |

## Running one

```
uv run python evals/run.py django-l12 --max-budget-usd 15
```

The runner:

1. builds the project in a new folder under the temp directory (`tribunedesk-evals/<scenario>-<time>/project`) and commits it;
2. runs `claude -p` with the scenario's prompt, this plugin (`--plugin-dir`) and no user
   settings, hooks or CLAUDE.md (`--setting-sources local`), with `TDKIT_CMD` pointing at this
   checkout, and saves the transcript next to the project;
3. prints the cost and the automatic checks: the skill fired, `tdkit check` ran, the report it
   wrote is green, the manifest is right, no signing secret is in a file git would commit, `.env`
   is ignored;
4. prints the files and the final message for the review under "Review" in the scenario file,
   which a person (or the session running it) judges.

The project folder stays, for review and for the reference integrations.

**The agent runs with your user's rights and no sandbox:** it may run any command in Bash. Run
only these scenarios, in the folders the runner creates.
