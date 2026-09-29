# lessons/homedepot.md — Home Depot (ptpn) — contexto y estado

Se carga solo cuando la sesión bindea al proyecto `homedepot`. Mantener corto; el detalle vive en `brain/output/homedepot/research/`. Append-only.

---

## 1. Proyecto

- **Repo:** `gitlab.xcade.net:Portal-Templates/ptpn` ("path to pro network"). Rama de trabajo `T1266732_ptpn_NewCandidateAndProPortals` (43 commits, todos `ignacio.curto`, 2026-09-14→09-28); base `stable` vacía. **MR !2 en Draft, sin review.**
- **Dos portales en una sola rama:** `candidate/` (candidato) y `pro/` (hiring manager). Derivan de `foundationals/careersmarketplace` y `foundationals/hiringmanager`.
- **Casos TEG:** 1266732 (Candidate, owner S. Mendez, PSP-Design-Review) · 1266716 (Hiring Manager, owner M. Alessandria, PSP-Design-In Progress) · 1266690 (Style Guide, owner M. Alessandria, PSP-Build-Queued).
- **Instancia dev:** `obf70239.ir01.obfuscate.xcade.dev` (PARs en las notas de los casos). Sandbox: `sandboxhomedepot.avature.net`.
- **Equipo:** S. Mendez (analista), M. Santini (diseño), M. Alessandria (PM), I. Curto (dev), E. Desouches (styling). POC cliente: Mateo Barrios (GMT). Chat: Rocket `#HomeDEVot`.

## 2. Artefactos (todos en `brain/output/homedepot/research/`)

| Archivo | Qué es |
|---|---|
| `homedepot-base-research-2026-09-29.md` | Investigación base: casos, rama, features, riesgos |
| `homedepot-delivery-plan.md` | Features × complejidad (negro=fundacional, azul=media, rojo=alta) |
| `homedepot-project-plan-wbs.md` / `.csv` | WBS del PP (Smartsheet, 67 tareas) |
| `homedepot-design-tokens.md` | Resumen de tokens (marca #F96302, neutros, spacing, radius) |
| `figma-styleguide-variables.md` | 638 variables (design tokens) de la Style Guide |
| `figma-styleguide-typography.md` | 62 estilos de texto (Helvetica Neue LT Pro) |
| `figma-styleguide-styles.md` | 79 estilos publicados |
| `figma-{styleguide,candidate,pro}-comments.md` | 1.116 comentarios de Figma (feedback cliente) |
| `screens/candidate-desktop/*.png` | 17 pantallas desktop del Candidate |
| `raw/` | JSONs/XLSX crudos |

## 3. Figma — estado y plan de extracción

- **Token:** en `~/.bash_aliases` como `FIGMA_TOKEN` (`figd_…`). **Nunca imprimirlo.**
- **File keys:** Style Guide `iwsXSWeb4itpugSfTIudL3` · Candidate `YpVYzUBk02ZPYWN6Rftc5R` (ramas wireframe `l603vN9D1k0CA6pUV2Vql5`, mockup `mq5cVROBu7pLrBzHK35UFY`) · Pro `0Wq3ounT5rTptVCpeXMEad` (rama `CfgzrK4oHJT66njcWF89km`).
- **Ya extraído:** Style Guide **completa** (variables + tipografía + estilos). Candidate/Pro: **sólo comentarios** (falta el documento).
- **Páginas:** `WS - Final week` = `14634:41274` · `Mobile` = `35:71132` · `Components` = `14149:39321`.
- **REGLA OPERABLE (error real):** **nunca bajar el documento completo** (`/v1/files/:key`) — la Style Guide pesó **443 MB** y disparó el rate limit del tier `low` (~51 h) en `/files`, `/nodes` e `/images`. Enumerar con `/v1/files/:key?depth=2` (KB) y exportar imágenes por lotes de ~20 (`/v1/images`). `/v1/files/:key/styles` usa otro bucket (no se agota).
- **Estado al cerrar (2026-09-29):** `/files`, `/nodes` e `/images` rate-limited, `retry-after ≈ 51 h` → disponible ~2026-10-01.

## 4. Pendientes

1. Enumerar (`depth=2`) y exportar **todas** las pantallas de Candidate (desktop + mobile) y Pro.
2. MR !2 sin review de código.
3. Pro portal sin brandear (el candidate sí).
4. Feature **Chat** sin datamodel (2ª fase).
5. Links del footer pendientes de que los pase el cliente.
