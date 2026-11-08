---
type: regex
target:
  source: file
  path: tribunedesk.json
pattern: '(?=[\s\S]*"contract": "3\.4\.1-draft")(?=[\s\S]*"delivery": "webhook")[\s\S]*"passed": \[\s*1,\s*2\s*\]'
arm: with-only
---
