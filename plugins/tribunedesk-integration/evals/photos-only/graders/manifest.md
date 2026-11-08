---
type: regex
target:
  source: file
  path: tribunedesk.json
pattern: '^(?![\s\S]*"conformance")(?=[\s\S]*"delivery": "none")[\s\S]*"levels": \[\s*4\s*\]'
arm: with-only
---
