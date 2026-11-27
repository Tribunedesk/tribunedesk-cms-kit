# Trying the Claude Code plugin on real projects

Fourteen scenarios in `evals/scenarios/` describe what the skill must do on a real project: build,
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
| `parity-django` | Django blog with a photo library | clean room: levels 1-4 like the WordPress plugin, Polish |
| `parity-laravel` | Laravel 12 blog with a photo library | the same in English, with `tribunedesk/cms-protocol` (needs PHP 8.3 and Composer) |
| `parity-node` | Express 5 blog on `node:sqlite` | the same in English (needs Node 22.13+) |
| `parity-drupal` | Drupal 11 with core Media | the same in English, with `tribunedesk/cms-protocol` (needs PHP 8.3 and Composer) |
| `custom-php` | hand-written PHP 8.3 site on SQLite, no framework, no Composer | the general case (`generic.md`): levels 1-4, Polish, "build a Tribune Desk plugin" |
| `taxonomy` | Django blog with categories and tags | levels 1-3, `l3-taxonomy-sync` and `l3-taxonomy` passed, not skipped |
| `extend-photos` | the Django reference (levels 1+2, current contract) with a photo library | extend mode: level 4 added, levels 1, 2 and 4 checked together |
| `update-3.6` | the Django reference as on contract 3.6 | update mode from a contract the current tdkit no longer supports |

## Running one

```
uv run python evals/run.py django-l12 --max-budget-usd 15
```

The runner:

1. builds the project in a new folder under the temp directory (`tribunedesk-evals/<scenario>-<time>/project`) and commits it;
2. runs `claude -p` with the scenario's prompt, this plugin (`--plugin-dir`) and no user
   settings, hooks or CLAUDE.md (`--setting-sources local`), with `TDKIT_CMD` pointing at a
   `tdkit` wheel built from this checkout into the run's folder (`uvx --from <wheel> tdkit`),
   and saves the transcript next to the project;
3. prints the cost and the automatic checks: the skill fired, `tdkit check` ran, the report it
   wrote is green, the manifest is right, no signing secret is in a file git would commit, `.env`
   is ignored; for the `parity-*` runs also that the agent read no local source (this kit,
   the WordPress plugin, the PHP library, headlinesforge): a clean room;
4. prints the files and the final message for the review under "Review" in the scenario file,
   which a person (or the session running it) judges.

The project folder stays, for review and for the reference integrations.

**The agent runs with your user's rights and no sandbox:** it may run any command in Bash. Run
only these scenarios, in the folders the runner creates.
