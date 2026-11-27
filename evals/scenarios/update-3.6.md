# update-3.6

Update mode from a contract the current tdkit no longer supports (audit 2026-11-27: the last
update eval ran on 2026-11-12, and an integrator on 3.6 got "update the plugin"). The Django blog
has the kit's Django reference as it was on contract 3.6 (the embed filter of 3.5, no
publication mode of 3.7), with its manifest on 3.6.0-draft.

## Prompt

Zaktualizuj naszą integrację z Tribune Desk do najnowszej wersji kontraktu. Listę zmian z rekomendacjami zapisz w pliku `tribunedesk-update.md` w katalogu projektu. Zmiany zatwierdzam z góry: nie czekaj na moją zgodę, ale wypisz plan i podsumowuj każdy etap.

## Review

Judged by reading the run (the runner prints the files and the final message).

### conduct (the whole session)

PASS if all of these hold in the session:
- it listed the CHANGELOG actions between 3.6 and the newest contract from `TDKIT integrators`,
  grouped by level, each with "already done", "to do" or "not applicable" and a reason;
- plan before code (SKILL.md, "The plan before code");
- it wrote to the user in Polish.
FAIL if any of them is missing, or if it told the user to update the plugin to get past the
unsupported contract.

### update-list (file tribunedesk-update.md)

PASS if the list names the publication mode (3.7, level 1) as to do, with the files it touches,
and the taxonomy route (3.8, level 3) as not applicable to levels 1-2.
FAIL if a level 3 or 4 item is marked "to do".

### final-summary (the final message)

PASS if the final message, in Polish, says what changed, that `tdkit check` passed for levels 1
and 2 on the new contract, and that `tribunedesk.json` now names it.
FAIL if it does not say whether the check passed.
