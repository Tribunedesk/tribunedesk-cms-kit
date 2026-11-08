---
description: "Update an L1+L2 Django integration built for contract 3.2.0-draft to 3.4.1-draft."
tags: [update, django, webhook]
max_turns: 200
timeout_seconds: 3600
allowed_tools: [Read, Glob, Grep, Skill, TodoWrite]
env:
  EVAL_TDKIT_CMD: /opt/tribunedesk-evals/kit/.venv/bin/tdkit
  EVAL_TRIBUNEDESK_DOCS_DIR: /opt/tribunedesk-evals/docs/cms-api@v3.4.1-draft
---

Zaktualizuj naszą integrację z Tribune Desk do najnowszej wersji kontraktu. Zmiany zatwierdzam z góry, ale najpierw wypisz listę zmian z rekomendacją i zapisz ją też w pliku `tribunedesk-update.md`.
