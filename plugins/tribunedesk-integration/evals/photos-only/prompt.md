---
description: "Level 4 only on a Django site with a photo model: no webhook, no tdkit check."
tags: [build, django, level4]
max_turns: 200
timeout_seconds: 3600
allowed_tools: [Read, Glob, Grep, Skill, TodoWrite]
env:
  EVAL_TDKIT_CMD: /opt/tribunedesk-evals/kit/.venv/bin/tdkit
  EVAL_TRIBUNEDESK_DOCS_DIR: /opt/tribunedesk-evals/docs/cms-api@v3.4.1-draft
---

Chcę tylko, żeby nasza biblioteka zdjęć (aplikacja `library`) była zsynchronizowana z biblioteką mediów Tribune Desk. Artykułów z Tribune Desk do CMS-a nie wysyłamy. Plan zatwierdzam z góry: nie czekaj na moją zgodę, ale wypisz plan i podsumowuj każdy etap. Wiadomość do naszego opiekuna w Tribune Desk zapisz też w pliku `tribunedesk-request.md` w katalogu projektu.
