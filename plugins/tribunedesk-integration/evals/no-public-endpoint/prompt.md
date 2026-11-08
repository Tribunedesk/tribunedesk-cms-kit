---
description: "Django blog behind a firewall: the skill must choose read mode."
tags: [build, django, read]
max_turns: 200
timeout_seconds: 3600
allowed_tools: [Read, Glob, Grep, Skill, TodoWrite]
env:
  EVAL_TDKIT_CMD: /opt/tribunedesk-evals/kit/.venv/bin/tdkit
  EVAL_TRIBUNEDESK_DOCS_DIR: /opt/tribunedesk-evals/docs/cms-api@v3.4.1-draft
---

Chcę, żeby artykuły z Tribune Desk trafiały do naszego CMS-a. Plan zatwierdzam z góry: nie czekaj na moją zgodę, ale wypisz plan i podsumowuj każdy etap. Wiadomość do naszego opiekuna w Tribune Desk zapisz też w pliku `tribunedesk-request.md` w katalogu projektu.
