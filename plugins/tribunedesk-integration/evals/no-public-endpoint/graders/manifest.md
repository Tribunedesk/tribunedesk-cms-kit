---
type: regex
target:
  source: file
  path: tribunedesk.json
pattern: '(?=[\s\S]*"delivery": "read")(?=[\s\S]*"levels": \[\s*1\s*\])[\s\S]*"passed": \[\s*1\s*\]'
arm: with-only
---
