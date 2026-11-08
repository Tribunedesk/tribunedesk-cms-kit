---
type: regex
target: trace
match: not_contains
pattern: '"name":"(?:Write|Edit)","input":\{"file_path":"(?![^"]*(?:\.env|settings\.local\.php|test)[^"]*")[^"]*"[^\n]*whsec_[A-Za-z0-9+/=]{20,}'
arm: both
---
