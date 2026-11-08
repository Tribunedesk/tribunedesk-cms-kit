# Evals of the Claude Code plugin

Six `claude plugin eval` cases in `plugins/tribunedesk-integration/evals/` check that the skill
builds, updates and explains an integration the way its spec says. The integrations it builds are
graded by `tdkit check` (the report it writes) and the manifest; an LLM judge grades what the
skill told the user.

| Case | Project | What it checks |
|---|---|---|
| `django-l12` | Django blog | levels 1+2, webhook, Polish, plan approved up front |
| `drupal-l12` | Drupal 11 | the same in English, with the `tribunedesk/cms-protocol` library |
| `photos-only` | Django blog with a photo library | level 4 only: no webhook, honest about no tdkit test |
| `no-public-endpoint` | Django blog on an intranet | read mode chosen and tested |
| `update-3.2` | Django blog with an integration for 3.2.0-draft | update mode: change list, new manifest |
| `ghost` | Ghost(Pro) README | bridge or read mode explained, no code written |

## Where they run

On native Windows `claude plugin eval` refuses runs that grant Bash, because Windows has no
sandbox. The evals run in WSL2 Ubuntu 24.04, logged in to Claude Code with a subscription.

Once, in PowerShell (a system change; restart if Windows asks):

```
wsl --install -d Ubuntu-24.04
```

Then in the Ubuntu terminal:

```
git clone https://github.com/Tribunedesk/tribunedesk-cms-kit /tmp/kit-setup
bash /tmp/kit-setup/evals/setup.sh e9-evals
claude          # log in with the subscription once, then /exit
```

`setup.sh` installs the tools (uv, PHP 8.3, Composer, Claude Code, the sandbox's bubblewrap and
socat) and fills `/opt/tribunedesk-evals/`, the cache the case scaffolds copy from: a clone of
the kit with `tdkit`, the contract docs, the Django and Drupal projects. It ends by timing the
Drupal scaffold, which must stay under the 120 s scaffold limit.

The cache is outside the home directory because the eval sandbox cannot read the home
directory. The agent gets `tdkit` and the docs through `EVAL_TDKIT_CMD` and
`EVAL_TRIBUNEDESK_DOCS_DIR` (set in each `prompt.md`), so it needs no network for them.

## Running

From the kit clone in the cache:

```
cd /opt/tribunedesk-evals/kit
claude plugin eval plugins/tribunedesk-integration --trust-plugin --scaffold \
  --allow-tools Bash Write Edit --runs 1 --ablation none -j 1 --max-cost-usd 15 \
  --case django-l12
```

The `drupal-l12` case installs the PHP library with Composer from GitHub, so it needs those hosts:

```
  --allow-tools Bash Write Edit "WebFetch(domain:github.com)" "WebFetch(domain:api.github.com)" \
    "WebFetch(domain:codeload.github.com)" "WebFetch(domain:repo.packagist.org)" \
    "WebFetch(domain:packagist.org)" "WebFetch(domain:packages.drupal.org)"
```

The full run, before a release: no `--case`, `--runs 3`, both arms (no `--ablation`), the
Composer hosts above, `--max-cost-usd 100`. Results go to
`plugins/tribunedesk-integration/evals/results/` (git-ignored).

Graders that need `tdkit` (the report, the manifest, "tdkit check ran") are `arm: with-only`:
without the plugin there is no tdkit, and counting them would only inflate the difference
between the arms.
