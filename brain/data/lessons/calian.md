# Lecciones y contexto — proyecto `calian`

Repo: `/home/emiliano/www/Portal-Templates-Group/calian` (GitLab: `Portal-Templates/calian`).
Se carga automáticamente cuando la sesión resuelve el proyecto `calian`.

---

## Ambiente: portal Hiring Manager (caso 1232413)

| Dato | Valor |
|---|---|
| Caso TEG | [1232413](https://teg.avature.net/#Case/1232413) — "Hiring Manager Portal App - Calian" (PAS Team 3, case owner María Bianco) |
| Caso padre | [1228390](https://teg.avature.net/#Case/1228390) — "Calian Group Ltd. :: ATS / CRM / CWM / HM / REF / IM / ONB :: A19623" |
| Instancia (obdbqa) | `obfint55806` → https://obfint55806.ir02.obfuscate.xcade.dev/ |
| **Settings/admin** | https://obfint55806.ir02.obfuscate.xcade.dev/_managerLogin (cuenta avasso — ver lección core #58) |
| Portal ID | **7** ("HM - Hiring Manager", URL path `hiringmanager`) |
| PAR (usuario del portal) | https://obfint55806.ir02.obfuscate.xcade.dev/su/bc05440afc631573 → redirige a `DataCompletionRequest?uid=2pmY3v1XjvlJM1x5` (**son el mismo**, verificado) |
| Portal renderizado | https://obfint55806.ir02.obfuscate.xcade.dev/hiringmanager/Dashboard |
| Branch | `T1232413_calian_NewHiringManagerPortal` |
| Template folder | `hiringmanager` |
| Portal repository | `calian` |
| MR | https://gitlab.xcade.net/Portal-Templates/calian/-/merge_requests/11 |
| Variante base | `hiringmanager4` = **Full + Onboarding** (v25.21.4) |
| Styling Theme asignado | `calian_json_20260616_1111` (Library/Style/400067) |

### Figma
- **Styleguide** (input de `portalStyler`): https://www.figma.com/design/C9oQCzfp4BhCzetYqrQsi8/1232399--Calian--Foundational-Library---Stable-25.18.3--v2-?node-id=9804-8593
  - Archivo: "1232399 [Calian] Foundational Library - Stable 25.18.3 (v2)". 332 tokens al 2026-08-26.
- **Proto/mockup** (referencia visual, no input del styler): mismo archivo, `node-id=7802-26031`, password `Avature-CALIAN-**2026`
- Fuente de marca: `Plus Jakarta Sans`.

### Otros portales del mismo repo/instancia
- `esignature` → portal 55, branch `T1232431_calian_EsignatureNewPortalWithNitroIntegration`
- `Calian Careers` → portal 13
- Branches existentes: timeslots, availability, docusign, FCR theme, email theme, careers marketplace, meeting gateway, offer letter header.

---

## Decisiones y pendientes

- **Variante HM4 (Full + Onboarding), pendiente de confirmación del case owner.** El scope form contractual del caso padre **no incluye ningún ítem de Onboarding** (verificado en las 76 filas de "Solutions in scope" + "Add-on solutions"), pero sí incluye Offer Management. El título del padre dice "ONB" y el portal 7 ya venía apuntado a `hiringmanager4`, así que se clonó HM4 para avanzar.
  - **Revertir a Full es barato y mecánico**: 3 booleanos en `Default.config` (`flowIEnabled`, `flowJEnabled`, `flowKEnabled` → `false`) + 8 flags `"disabled": true` en los constants de Onboarding de `constants.nopage`. Nada más difiere entre `hiringmanager` (Full) y `hiringmanager4`.

---

## Notas operativas específicas de este proyecto

- **El `.git/info/exclude` del harness se comparte por gitdir.** Cada branch nuevo creado con `branch` (que sale de `stable`) ve el mismo `.git/info/exclude` que el repo principal, así que `_brain`/`AGENTS.local.md` ya aparecen ignorados sin pasos manuales. (Incidente original: commit `9f4a1db` en el branch de esignature se llevó puestos esos archivos; con el mecanismo exclude eso no vuelve a pasar.) — **MECANISMO RETIRADO 2026-09-11** (rework no-binding): ya no se escriben esos archivos en proyectos; la lección queda como registro histórico del incidente.
- **Secuencia correcta para pullear un branch en las settings del portal**: cargar los 3 campos con tipeo real → **Pull** → **Ignore** (las advertencias "Leading spaces are not 4x" son de estilo, vienen del código foundational) → **Apply**. Sin el Apply final nada persiste. Ver lección core #59.
- El input "Tag or branch" queda vacío tras un pull exitoso; el valor real vive en "Show portal information". No es un error.
- sisifo para este portal: `scripts/sisifo-start.sh -oobfint55806 -p7` desde `calian/hiringmanager`.
