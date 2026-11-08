---
type: regex
target:
  source: file
  path: tribunedesk.json
pattern: '(?=[\s\S]*"contract": "3\.4\.1-draft")(?=[\s\S]*"delivery": "webhook")(?=[\s\S]*"protocol": "1\.0\.0")(?=[\s\S]*"levels": \[\s*1,\s*2\s*\])[\s\S]*"passed": \[\s*1,\s*2\s*\]'
arm: with-only
---
