---
type: regex
target:
  source: file
  path: .tribunedesk/tdkit-report.json
pattern: '^(?![\s\S]*"passed": false)(?=[\s\S]*"tdkit": "1\.)(?=[\s\S]*"levels": \[\s*1,\s*2\s*\])(?=[\s\S]*"mode": "webhook")[\s\S]*"passed": true'
arm: with-only
---
