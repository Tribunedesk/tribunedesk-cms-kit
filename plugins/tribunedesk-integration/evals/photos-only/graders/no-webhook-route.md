---
type: regex
target:
  source: file
  path: blogsite/urls.py
match: not_contains
flags: i
pattern: 'webhook'
arm: both
---
