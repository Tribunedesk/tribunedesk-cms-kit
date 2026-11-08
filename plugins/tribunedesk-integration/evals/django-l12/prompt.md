---
description: "Build levels 1+2 (webhook) into a Django blog; the user answers and approves up front."
tags: [build, django, webhook]
max_turns: 200
timeout_seconds: 3600
allowed_tools: [Read, Glob, Grep, Skill, TodoWrite]
env:
  EVAL_TDKIT_CMD: /opt/tribunedesk-evals/kit/.venv/bin/tdkit
  EVAL_TRIBUNEDESK_DOCS_DIR: /opt/tribunedesk-evals/docs/cms-api@v3.4.1-draft
---

Zbuduj mi integrację naszego bloga z Tribune Desk: artykuły mają trafiać do CMS-a, a po publikacji Tribune Desk ma dostać link zwrotny. Blog działa publicznie przez https pod https://blog.example.com, więc webhook jest dla nas OK. Zdjęć i pełnej treści nie potrzebujemy. Plan zatwierdzam z góry: nie czekaj na moją zgodę, ale wypisz plan i podsumowuj każdy etap. Wiadomość do naszego opiekuna w Tribune Desk zapisz też w pliku `tribunedesk-request.md` w katalogu projektu.
