# Lessons — sandisk (Portal Templates Group)

## Backfill note (2026-07-23)

This file did not exist when the eval phase closed on 2026-07-23 for the
agency/docusign work (T1221203_sandisk_AgencyFoundational) — the durable
info below lived only in a checkpoint and in the project's own
`matrix-output/eval/sandisk-agency-T1221203.md`. Reconstructed from those
sources; see `brain/state/checkpoints.jsonl` (2026-07-23T18:10:12) for the
full narrative if more detail is needed.

## Repo/portal context

- `sandisk` has only 2 real portals: `agency` (base corelayer ~25.9, newer
  but not yet branded) and `docusign` (base ~25.8, older but already
  finished to brand: local Pilat fonts, brand social icons, theme fixes).
  Same brand values (identical swatches) across both.
- External canonical reference for structure/lineage: `foundationals/agency`
  (golden). F0a (lineage chrome) verified with no real diff vs it.
- Working ticket: `T1221203_sandisk_AgencyFoundational`. No commit/push was
  made at close of the 2026-07-23 session — the `agency` working tree was
  left with the changes ready for the user to review visually before
  committing.

## Decisions confirmed by the owner/user (don't re-ask)

- Banner copy: do NOT touch, stays placeholder.
- Footer logo → `logo--default.svg`.
- Job-cards architecture: bounded macro `jobCardValues(job)` for the fields
  block only; shells/banner stay in-place (Option C — rejected both a
  "god-macro" and pure in-place duplication).
- Candidates table (6 columns: Candidate Name / Submitted for /
  Requisition # / Submission status / Submitted on / Last updated) applies
  to BOTH the Dashboard widget and the full `MyReferrals.page`.
- `Requisition #` must read from `person.req` (builtin corelayer field),
  not `person.jobId` (that's the internal ID) — confirmed correct by
  cross-portal pattern in ~10 other portals with the same Library-v3
  architecture.

## Known gaps (declared, non-blocking, pending a future session)

- POST `/agency/ReferCandidate` returns HTTP 500 on real submit. Root cause
  reproduced and confirmed as **backend/instance config**, not this
  session's code: Record Picker field `6326 "Agency Name"` is explicitly
  marked "HIDDEN BECAUSE PAS INTERVENTION IS NEEDED" in the served form.
  Needs PAS/instance-admin intervention — no template fix will resolve it.
- Custom field IDs `220` (Job Type), `135` (Type of Employment), `8`
  (Business Unit) are wired in `Default.config` but not yet validated
  against the instance's real schema — pending a future session with the
  Figma sample screens.
- `Requisition #` appeared empty for one test candidate because that
  specific `JobPerson` record has no `person.req` populated (data gap on
  that record, not a template bug — the field choice itself is correct).

## Process notes

- **Dev-instance render link (agency)**, bypasses Login and stays
  authenticated (same `DataCompletionRequest?uid=...` pattern as
  `saintlukes.md`): `https://obfint54486.ir02.obfuscate.xcade.dev/DataCompletionRequest?uid=ihP4lcEURQ1uXdJ7`.
  Found on 2026-07-24 not saved anywhere in-repo — it lives only on TEG
  case `1221203` notes (`teg-get-notes.sh 1221203`). **Lesson learned the
  hard way (user called it out): as soon as a dev-instance link is found,
  save it here immediately, don't leave it to be re-discovered next
  session.** CSS/template changes reflect on this instance right after a
  `git push` to the branch (no tag-pull wait observed for CSS); new
  binary assets (svg/webp/fonts) may still need the tag pull — not
  confirmed either way yet, this session's new SVG happened to show up
  immediately.
- `config.enableRecommendAFriend` is OFF on this instance → `.banner--extra`
  (recommend-a-friend block, `agency/tpt/recommendAFriend.tpt`) never
  renders here. Any change touching it can only be verified statically,
  not visually, until an instance with that flag enabled is available.

## Decisions confirmed by the owner/user — Actions & Links (buttons/links) task (2026-07-24)

- Scope: `agency` portal only (not `docusign`), same branch `T1221203_sandisk_AgencyFoundational`,
  no push without explicit ask in-session.
- Link mismatch (invisible underline at rest, no hover color change to brand red, no click-focus
  indicator): fix it directly in `agency` (`specifics.css`/`library__theme.css`, consuming the
  already-existing `--t-gs--color--text--link--hover` token) rather than waiting to confirm an
  external/core layer first.
- Figma's "Link S" (breadcrumbs/footer) and "Link M" (general) variants: **superseded 2026-07-24
  after Architect review** — Architect found formalizing this needs 25 markup edits (21 with zero
  visual change today) vs a 4-edit scoped alternative; when asked to choose, the user said **no
  size distinction at all** — do NOT create `.link--s`/`.link--m` classes, keep the existing
  implicit context-based sizing (`.footer .link` 14px vs general `.link` 16px) exactly as-is.
  Only the link *state* fixes (underline/hover-color/click-focus) apply, not sizing.
- Tertiary button / Disabled button / link "Selected" state: user wants these actively found and
  tested live (not left as declared gaps) before implementing.
- Breakpoints: include mobile and tablet in this pass, not just desktop.
- **Smith gate found footer `.link:hover` never reaches brand red** (a more specific core rule,
  `.footer .link:hover` via `--t-tc--footer--link--color--hover`, wins over the portal's new
  `.link:hover` rule) — root cause is real, but the fix was **declined on purpose**: brand red
  `#E10600` on the footer's black background is 4.23:1, below WCAG AA (4.5:1) for 14px text. User
  chose to keep footer hover white (compliant) over exact brand-color fidelity in that one
  dark-background context. Don't silently "complete" this later without re-raising the trade-off.
- Same contrast shortfall on the breadcrumb Selected color (also landed on a black background from
  unrelated in-flight work) was accepted as shipped anyway — real improvement over the previous
  near-invisible `#333`-on-black (1.66:1), even though it doesn't clear AA either. Both are
  documented as known, accepted gaps in
  `sandisk/matrix-output/eval/sandisk-agency-actions-links-GATE.md`.
- **Working tree contamination discovered by Smith**: `agency/css/library__theme.css` and
  `specifics.css` carry ~10 unrelated uncommitted changes from a parallel styleguide task (new
  font-size tokens, banner/hero retargeting, `.menu__link` hover, 2 extra `specifics.css` rules)
  mixed into the same dirty tree as this ticket's 3 edits, with identical mtimes — unattributable
  without git history. When it's time to commit, split this ticket's `.link`/breadcrumb changes
  from the rest; don't commit the whole dirty tree as one blob.

## User's manual edits on top of the Actions & Links fix (2026-07-24) — INTENTIONAL, not a regression

After the Trinity implementation + Smith gate above, the user manually edited the working tree
further. **User explicitly confirmed these are deliberate final decisions, not errors to flag or
revert:**

- `agency/css/specifics.css`: removed the `.link { text-decoration-color: currentColor; }` rule
  (fix #5) and the `.breadcrumbs .list__item--active`/`> span` red-color rule (fix #10) that
  Trinity/Smith had verified. Added instead: `.list--links--top .list__item:not(:last-of-type):after
  { border-inline-start-color: var(--t-gs--swatch--neutral--100); }` (breadcrumb divider color).
- `agency/css/library__theme.css`: kept both link-hover token rewires
  (`--t-gs--color--text--link--hover` and `--t-gs--color--text--on--fill--link--hover`, both now
  `var(--t-gs--color--text--brand)`) — these are unchanged from the Trinity/Smith-verified state.
  Added a new `.breadcrumbs .link { ... }` block scoping all link-state tokens
  (`text-link`, `--hover`, `--focus`, `--active`, `--selected`, `--disabled`) to
  `var(--t-gs--swatch--neutral--100)` (white) — this covers the two non-current breadcrumb
  `<a class="link">` items, NOT the current/active `<span>` step (which has no `.link` class and is
  therefore not reached by this rule).
- **Net effect**: the breadcrumb "Selected" (current step) element no longer has an explicit color
  rule after these edits — the earlier session's red (`#E10600`) fix for it was removed. This is a
  known, deliberate change per the user, not something to "fix back" without being asked again.
- `agency/BaseTemplate.nopage`: removed the `footer__rights__copy` (copyright) span entirely, and
  wrapped the 3 social link URLs (LinkedIn/YouTube/Instagram) in `url('footerSocialItem*Link', ...)`
  builder calls (CMS-configurable URLs) instead of hardcoded hrefs.
- `agency/images/logo--small.svg` and `agency/images/social-media.svg` deleted — confirmed
  (grep, zero hits) that nothing in `.page`/`.nopage`/`.tpt`/`.css` references either file, so this
  is a safe, intentional cleanup of unused assets.
- Also present in the same dirty working tree (pre-existing, from a parallel in-flight styleguide
  task, per Smith's contamination note in the eval report — not part of this link/breadcrumb
  ticket specifically, but shipped together in the same commit per the user's request): new
  `--t-gs--font--size--14/20/22/24` tokens, `.submitButton` reclassified from Secondary to Primary
  style globally (previously only inside `.article--alert`), `.menu__link:hover` background token
  swapped for the literal `Transparent`, banner height/background-image position+size converted
  from `px` to `rem`, strip background/font tokens repointed to raw `neutral--000`/`neutral--100`
  swatches instead of the semantic `surface--tertiary`/`text--default` tokens, and 2 more
  `specifics.css` rules (`.article--result .article__content__values` flex-wrap,
  `.list--links--top` divider — the divider rule doubles as this ticket's breadcrumb-related fix
  too, see above).

## careersmarketplace — sandbox desactualizado vs. branch en desarrollo (2026-08-12)

- El render en vivo `https://sandbox-avature.sandisk.com/careersmarketplace` (sin login)
  **no sirve `stable` ni el HEAD de `T1221196_sandisk_NewExternalCareersPortal`** — sirve un
  punto intermedio exacto de esa misma rama, equivalente al commit `f7765c8` ("feat(careers):
  add area-specific billboard styling with CSS custom properties"), **5 commits detrás de HEAD**
  (`ccfe316`). Confirmado byte-a-byte (`curl` a HTML/CSS servidos vs. `git show` del branch) por
  el subagente `figma-audit`.
- Alcance auditado: navbar/header/footer/BaseTemplate únicamente (pedido explícito del usuario).
  `headerLogo.tpt`/`headerMenu.tpt` son byte-idénticos entre el commit servido y HEAD — el markup
  del navbar no cambió en los 28 commits de la rama; solo cambiaron `Config.nopage` (`companyName`
  de `'SanDisk'` a `'Sandisk'`, commit `4883998`) y `specifics.css`/`library__theme.css` (estilos
  de footer link hover, banner height, logo estático de banner — commits `ccb0710`/`3b6cc28`).
- **Todas** las discrepancias reales encontradas van en una sola dirección: el código local en
  `T1221196` (HEAD) ya tiene el estado correcto; el sandbox está desactualizado. Ninguna encontrada
  al revés dentro del alcance navbar/header/footer. Acción: confirmar con el equipo de deploy si el
  sandbox está pendiente de sync con HEAD, no tocar código por esto.
- **Gap de tooling real, no específico de este caso:** `mcp__chrome-devtools__*` no estuvo
  disponible para el subagente `figma-audit` corrido en foreground (declarado en su
  `allowed-tools` pero ausente de su lista real de funciones) — mismo síntoma que la lección 27
  (core) tuvo con `mcp__chrome-browser__*`. Por eso la tabla de discrepancias usa HTML/CSS servidos
  vía `curl` como fallback explícito (Pattern 4/6d del skill), no `getComputedStyle()` real —
  válido para lo que se pudo confirmar (todo MATCH salvo el lag de deploy), pero deja sin cerrar:
  computed style real de `:hover`/`:focus` del footer, y el comportamiento real de colapso del
  menú en breakpoints tablet/mobile. Ver `brain/data/lessons.md` lección 55 para el detalle
  general del gap de MCP en subagentes.
- Próxima sesión, si se necesita cerrar ese último gap con certeza total: correr `figma-audit`
  de nuevo, o que la sesión raíz (Neo) haga la verificación en vivo directamente con su propio
  acceso a `chrome-devtools` (confirmado disponible ahí vía `mcp_list_tools`), en vez de re-lanzar
  el subagente esperando que esta vez sí tenga el tool.

### Cierre del gap — verificación en vivo real hecha por Neo (2026-08-12), `figma-audit` retirado del roster

El usuario pidió borrar el skill/agente `figma-audit`
(`~/.config/devin/skills/figma-styleguide-to-portal-templates/` +
`~/.config/devin/agents/figma-audit/`, eliminados por completo — no era parte del roster de
Matrix, no afecta `bin/matrix build/install`) y que Neo hiciera la revisión en vivo directamente
con su propio acceso a `chrome-devtools` (confirmado disponible en la sesión raíz, a diferencia
del subagente). Resultado, con `getComputedStyle()`/`hover` reales, no `curl`:

- **Menu link hover (desktop, `Open Positions`):** `color`/`border-block-end-color` reales
  = `rgb(225, 6, 0)` (`#E10600`, brand red), `border-block-end-width: 3px` — **MATCH confirmado en
  vivo** con la predicción de fuente.
- **Footer link hover (`Applicant Privacy Notice`):** `color`/`text-decoration-color` reales
  = `rgb(225, 6, 0)` sobre `footer background-color: rgb(0, 0, 0)` (negro) — **confirma en vivo,
  con evidencia real, el estado viejo/sandbox** (rojo brand sobre negro) que la auditoría de
  fuente ya había marcado como desactualizado frente al HEAD de `T1221196` (que reescribe a
  `neutral--100`/blanco por contraste). Con contraste real medido (`#E10600` sobre `#000000` ≈
  4.23:1) sigue por debajo de WCAG AA texto normal (4.5:1) — el mismo hallazgo de contraste ya
  documentado para `agency` (ver más abajo en este archivo, sección Actions & Links) se repite
  acá; deploy pendiente aparte, si se lleva el sandbox a HEAD conviene reconfirmar el contraste
  del nuevo valor blanco-sobre-negro también.
- **Colapso del menú (breakpoint real):** a 768px y a 375px, `document.documentElement`
  tiene `menu-type="toggleable"` (confirma el breakpoint 1025 de `Config.nopage`), el botón
  "Main menu toggle" es real y visible (`display: flex`), y un **click real** sobre él revela los
  5 links del nav (antes ocultos en el árbol de accesibilidad) — **colapso/expansión confirmado
  funcional en vivo**, no solo por CSS fuente.
- Con esto, las únicas filas que habían quedado "NO DETERMINABLE (fuente only)" en el reporte de
  `figma-audit` para navbar/footer quedan cerradas: todo MATCH salvo el hover del footer, que
  sigue siendo MISMATCH por el mismo motivo ya conocido (deploy pendiente de `T1221196` HEAD al
  sandbox), ahora con el valor real confirmado en vez de inferido.

## internalcareers (PAB) — bug real de Page Builder en menú móvil/tablet (2026-08-12)

Comparación en vivo (Neo, `chrome-devtools`, 3 viewports) del menú de navegación entre `careersmarketplace`
(branch `T1221196_sandisk_NewExternalCareersPortal`, confirmado; usuario avisa que el sandbox ya está
actualizado a una tag más reciente que la commit `f7765c8` documentada arriba — pendiente re-confirmar
commit exacto si hace falta) y `internalcareers` (portal 35, PAB, vía user preview link
`https://sandbox-avature.sandisk.com/su/2850be27cf6d1403`). Desktop sin discrepancias (diferencia de
items es esperada: externo/anónimo vs interno/autenticado). En **tablet (768) y mobile (375)**, el link
"Open Positions" del menú abierto de internalcareers tiene `height: 100%` seteado por Page Builder
(`customTemplateBuilderStyles.css`, selector `#Link_ie689cgjjx_1778007189`) dentro de un contenedor
flex-column, lo que lo hace ocupar ~770px de los ~862px del menú y empuja "Referrals Portal"/"My account"
fuera de la vista — bug real de configuración de tamaño de elemento en Page Builder (no template code),
fixable ahí mismo reseteando el alto a `auto`. Detalle completo, capturas y evidencia DOM:
`brain/output/sandisk/research/sandisk-navmenu-comparison-careersmarketplace-vs-internalcareers.md`.

## internalcareers (PAB) — cómo se bindea realmente un campo dinámico de record en el banner (2026-08-14)

Caso real: banner del JobDetail de `internalcareers` (portal 35, PAB) con un Heading vacío donde
debía mostrarse el nombre del job. **Primera hipótesis de Neo (INCORRECTA, corregida por el
usuario en la misma sesión):** que los elementos Static Content de Page Builder (Heading/Free
text) no tienen ningún mecanismo de binding a un campo de record — verificado solo a medias contra
"Work with Portal Page, Page Template, and Component Elements" (Help id 778), que describe Heading
como "Type a text... choose what level it represents" sin mencionar variables. Esa doc es
incompleta: **sí existe** un mecanismo real, vía un dependency compartido, y el usuario ya lo usó
para resolver el caso.

**Mecanismo verificado contra la fuente** (`~/www/.templatesfeatures/pab-commonfeatures/`):
- `viewRecord/viewRecord.code` y `viewPerson/viewPerson.code` son archivos `.code` (Twig backend)
  que respaldan un elemento **Embed Code** de Page Builder (confirmado en el DOM real: un
  `<div class="portal_builder_element_EmbeddedCodeFile">` aparece justo antes del Heading vacío
  en el banner).
- Toman una View del core app vía `getJobView(configCode.constantView, ...)` /
  `getPersonView(...)` — la constante se define por portal en `Default.config`
  (`config.viewRecord.constantView`, ej. `rv_recordData` en sandisk/pabinternalcareers;
  `config.viewPerson.constantView`, ej. `pv_personData`).
- Recorren `viewRecordData.getViewFields()` / `viewPersonData.getViewFields()` y **filtran solo
  los campos cuyo CSS Class matchea el patrón `PAB_*`** (macro `filterString(field.cssClassName,
  "/PAB_/")`) — ese sufijo (ej. `PAB_jobName`) pasa a ser la key expuesta.
- Arman un mapa `{ jobName: "valor real del record", ... }` y lo exportan con
  `prepareOutput(recordData)` — función `EmbeddedCodeFile.prepareOutput`, confirmada en
  `aidocs/portalDocs/Twig-Extensions.md`: "Process the embedded code file output to prepare it to
  be exported."
- El fix real para este tipo de caso: la View apuntada por `constantView` (ej. `rv_recordData`)
  necesita el campo deseado (ej. Name) con el **CSS Class `PAB_<key>`** seteado y con el valor
  correcto — no se edita el Heading ni se le tipea una variable Twig directamente (eso nunca
  funciona, esa parte del diagnóstico original sí era correcta).
- **No verificado en esta sesión** (pendiente si hace falta detalle exacto a futuro): el paso
  final de cómo el Heading nativo específicamente consume ese output exportado — si es un binding
  nativo del Builder ("Dynamic value" → salida de un Custom Component) o requiere JS adicional
  con `importOutput()` en el mismo Embed Code. No se encontró uso de `importOutput` en este repo.
  El usuario resolvió este tramo directamente en el Builder del instance.
- Otros `.code` con `prepareOutput` en el repo (mismo patrón, útil como referencia futura):
  `portalsblueprints/careersmarketplace/viewJob.code` (exporta el objeto `job` completo, sin
  filtro `PAB_*`), `portalsblueprints/docusign/SuccessView.code`.

## Roster-discipline fix applied (2026-07-24), per the pending gap from the banner text-size session

`figma-audit` subagent is used strictly in its intended read-only role (produces a discrepancy
table only, per its own AGENT.md — never implements/commits/pushes). The actual flow for this
task: figma-audit (audit) -> Architect (reviews the discrepancy table, classifies CODE/EXTERNAL-
BRAND/CONTENT/ASSET-MISSING) -> Trinity (implements) -> Smith (gate, re-audit against the same
cited sources). No commit/push without the user asking for it explicitly in-session — this was
the exact gap flagged by the user in the previous session (unauthorized push after a banner fix).

- Client styleguide (Figma export) lives at
  `sandisk/1221191 - [Sandisk] - Style Guide/07 Stylesheet - Layout.svg`
  (+ a broken/huge companion `.png` — use the `.svg`, crop it with
  `convert -crop WxH+X+Y` and resize down, the raw file is 1920x9981 and
  too big to read directly). Confirmed banner spec found there: solid
  brand-red background + "SANDISK" wordmark SVG top-right + white heading
  text, exact min-heights per breakpoint: Desktop Large/Small 300px,
  Tablet 350px, Mobile 375px (agency's pre-existing height tokens didn't
  match this and caused a real heading/logo overlap bug on mobile — see
  2026-07-24 checkpoint).
