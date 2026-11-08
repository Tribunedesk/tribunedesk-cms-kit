---
description: "Ghost(Pro): explain bridge or read mode and no level 4 before building."
tags: [conversation, ghost]
max_turns: 30
timeout_seconds: 900
allowed_tools: [Read, Glob, Grep, Skill, TodoWrite]
env:
  EVAL_TDKIT_CMD: /opt/tribunedesk-evals/kit/.venv/bin/tdkit
  EVAL_TRIBUNEDESK_DOCS_DIR: /opt/tribunedesk-evals/docs/cms-api@v3.4.1-draft
---

Zbuduj integrację naszego serwisu z Tribune Desk.
