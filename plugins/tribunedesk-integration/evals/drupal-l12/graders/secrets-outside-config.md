---
type: llm
focus: trace
---

PASS if the signing secret and the token are read from `settings.php` (or an environment
variable it reads), never from Drupal configuration that `drush config:export` would write, and
the assistant says so.
FAIL if a secret or token is stored as configuration (a config form field saved with the config
API, a `config/install` YAML file) or written into a tracked file.
