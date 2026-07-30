# Lessons — saintlukes (Portal Templates Group)

## Reference render links (persistent, authenticated)

These `DataCompletionRequest?uid=...` links bypass Login and stay authenticated; the base
domain of each portal redirects to Login without a session. Always use these to
re-verify live rendering instead of the base domain, and re-authenticate through them
if the Chrome session expires.

- **referrals**: https://obfint51518.ir02.obfuscate.xcade.dev/DataCompletionRequest?uid=nOfuJotFEHZxrzWY
- **onboarding**: https://obfint51518.ir02.obfuscate.xcade.dev/DataCompletionRequest?uid=t3xYVYuBv1ZmbQWd
- **internalcareersmarketplace**: https://obfint51518.ir02.obfuscate.xcade.dev/DataCompletionRequest?uid=HS0S7xm9KTc6XwUG
  (confirmado por el usuario 2026-07-29; branch de desarrollo activa para este portal:
  `origin/T1230545_saintlukes_InternalCareersPortalUpdate`, la mas reciente de 3 candidatas
  -T1142206/T1180702/T1230545- por fecha de commit)

## Repo/branch context

- Monorepo `Portal-Templates-Group/saintlukes`, one folder per portal (`referrals/`, `onboarding/`,
  `hiringmanager/`, `careersmarketplace/`, `internalcareersmarketplace/`, `liveinterview/`,
  `timeslots/`). Working branch for the referrals rebrand: `T1051546_saintlukes_ReferrarlsNewStandardPortal`.
- `origin/T1230540_saintlukes_OnboardingRebranding` (remote-only, not checked out) holds an
  already-rebranded onboarding portal (footer icon, social SVGs, etc.) on the **older**
  `--color--`/`--spacer--` token generation. Do not copy variable names from it — port
  values/structure to the current `--t-gs--`/`--t-tc--` tokens used in referrals (confirmed by
  user as the current generation).
- `foundationals/referrals` and `templatesbasecode` do NOT have the rebrand fixes — confirmed
  ad-hoc per-portal work, not upstreamed.
- Figma styleguide exports for referrals live in `referrals_figma_styleguide_images/` (moved out
  of `referrals/` to the monorepo root, previously `referrals/figma styleguide images/`, before
  that `temp/`): subfolders `actions and links`, `example screens`, `navbar, header and footer`.

## Asset diffs onboarding vs referrals (2026-07-22 audit)

- `favicon.ico` and `images/icon--user.svg` differ in content (confirmed by SHA-256) between
  onboarding and referrals — onboarding's are the ones to bring over per user decision.
- `images/logo--default--blue.webp` and `images/logo--default--white.webp` are identical
  (byte-for-byte) between the two portals — no action needed there.
- Assets that exist only in onboarding but are onboarding-flow-specific (no conceptual
  equivalent in referrals) — user decided to EXCLUDE these from any cross-portal copy:
  `pill--status--*`, `pill--type--*`, `subtask__item--completed__icon.svg`,
  `video--placeholder.svg`, `icon--add.svg`, `icon--remove.svg`, `icon--quote--opening.svg`,
  `close.svg`, `banner--home--1920.webp`, `banner--home--tablet.webp`.

## Regla dura del usuario (2026-07-29)

- **Nunca revertir un cambio no reconocido en el working tree sin preguntar primero al usuario**, sin importar el tier que Smith le asigne. El usuario puede estar editando archivos del portal en paralelo a la sesión de Devin (mismo working tree compartido) — un diff "no autorizado por ningún plan" puede simplemente ser trabajo manual del usuario, no scope creep de un subagente. Antes de cualquier `git checkout --`/revert, mostrar el diff exacto y preguntar de quién es. Ya pasó una vez: se revirtieron 2 cambios reales del usuario (`referrals/css/specifics.css` y el token `--t-tc--buttons--font--family` en `library__theme.css`) asumiendo que eran drift de un subagente; ambos se restauraron a pedido del usuario.
- **Los self-reports de subagentes sobre el estado de un archivo NO son confiables** — en la misma sesión, un Smith reportó textualmente "diff después: vacío" para `specifics.css` cuando en realidad el archivo seguía teniendo el contenido completo sin revertir (verificado por Neo leyendo el archivo real después). Siempre re-verificar con `git diff`/lectura directa del archivo, nunca aceptar la palabra de un subagente sobre el estado final de un archivo compartido.

## Process notes

- obfuscate instance caches rendered HTML per page (unlike CSS, which reflects instantly) — if a
  `.nopage`/`.page`/`.tpt` change doesn't show on first load after applying, retry navigation with
  a cache-busting query string before concluding the fix failed.
- **sisifo live-sync params for `referrals`**: run from inside `saintlukes/referrals/` with
  `-oobfint51518 -p22` (confirmed working, 2026-07-29). Use the `sisifo-watch` skill
  (start/status/stop scripts) rather than the raw `sisifo.sh` prompt loop.
