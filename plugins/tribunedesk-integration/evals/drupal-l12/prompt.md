---
description: "Build levels 1+2 (webhook) into Drupal 11 with the PHP library; English."
tags: [build, drupal, webhook]
max_turns: 200
timeout_seconds: 3600
allowed_tools: [Read, Glob, Grep, Skill, TodoWrite]
env:
  EVAL_TDKIT_CMD: /opt/tribunedesk-evals/kit/.venv/bin/tdkit
  EVAL_TRIBUNEDESK_DOCS_DIR: /opt/tribunedesk-evals/docs/cms-api@v3.4.1-draft
---

Build our Drupal site's integration with Tribune Desk: articles should land in the CMS, and after we publish one Tribune Desk should get the link back. The site is public over https at https://news.example.com, so a webhook is fine. We need neither photos nor full content. I approve the plan in advance: do not wait for my go-ahead, but print the plan and sum up every stage. Also save the message for our Tribune Desk contact as `tribunedesk-request.md` in the project folder.
