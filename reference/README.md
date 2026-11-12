# Reference integrations

**Reference to read, not a supported module.** Each folder is what the Claude Code skill
`tribunedesk-integration` built on a sample project (levels 1 and 2, webhook mode), reviewed by a
person and kept as an example. Use them to see what a finished integration looks like; build your
own with the skill, against your CMS and the current contract.

| Folder | CMS | Built in run | Contract |
|---|---|---|---|
| `django/` | a small Django 5.2 blog (the whole project) | `django-l12`, 2026-11-12 | 3.4.1-draft |
| `drupal/` | Drupal 11: the custom module, settings and Composer lines | `drupal-l12`, 2026-11-12 | 3.4.1-draft |

CI checks both with `tdkit check --levels 1,2 --mode webhook` on every pull request that changes
`reference/`, `src/tdkit/` or `plugins/` (jobs `reference-django` and `reference-drupal`).

What a reviewer changed after the run, and why, is listed in each folder's README.
