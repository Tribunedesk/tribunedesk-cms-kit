---
type: regex
target:
  source: file
  path: .tribunedesk/tdkit-report.json
pattern: '^(?![\s\S]*"passed": false)(?=[\s\S]*"tdkit": "1\.)(?=[\s\S]*"levels": \[\s*1\s*\])(?=[\s\S]*"mode": "read")[\s\S]*"passed": true'
arm: with-only
---
