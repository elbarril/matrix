# Instalación de Matrix

Guía paso a paso para dejar Matrix instalado de cero en otra máquina o cuenta.
Cada paso indica qué deja de andar si se salta. Si algo falla, los comandos
reportan el problema y no dejan la instalación a medias.

> **Nota de fase:** este documento se armó por fases (plan "instalación y
> portabilidad de Matrix", fases 1–7). El documento está completo.

---

## 1. Prerrequisitos — `bin/check-prereqs.sh`

Corré primero el detector de prerrequisitos. Es un script autónomo que **no**
depende de `bin/matrix`, `jq` ni `python3` para correr, así que sirve
exactamente para el caso "máquina nueva":

```bash
bin/check-prereqs.sh; echo "exit=$?"
```

- **Exit 0:** todo lo esencial está.
- **Exit 1:** falta algo esencial (bloquea el flujo completo). Instalá lo que
  indica y volvé a correr el detector.
- **Exit 2:** solo faltan opcionales. Matrix arranca, pero la capacidad
  correspondiente no va a andar (lock global, Hardline, MCP `chrome-browser`,
  o el alias `hardlines`).

Esenciales: `bash >= 4`, `python3`, `jq`, `git`, `realpath` o `readlink -f`,
PyYAML (`import yaml`). Opcionales: `flock`, `setsid`, `nohup`, `pgrep`,
`/proc`, `npx`, `xdg-open`.

**macOS:** `readlink -f` no viene por defecto; instalá coreutils con
`brew install coreutils` (el detector lo explica).

**Seguridad:** el detector avisa (sin bloquear) si
`brain/state/hardline/telegram.env` existe y es world-readable; recomendado
`chmod 600`.

---

## 2. Clonar el repositorio

```bash
git clone <url-del-repo-matrix> matrix
cd matrix
```

---

## 3. Crear `brain/config.yaml`

`brain/config.yaml` es **gitignored** (per-machine). Crearlo con tu identidad:

```yaml
user: <tu-nombre>
language: es
timezone: America/Argentina/Buenos_Aires
```

Si no existe, Matrix usa defaults; pero el primer `build`/`install` espera
poder leerlo.

---

## 4. Build + install

```bash
bin/matrix build   --target=devin
bin/matrix install --target=devin
```

- `build` genera los artefactos thin-pointer en `adapters/devin/generated/`
  (gitignored, efímero).
- `install` los **copia** (no symlinks) a `~/.config/devin/` (skills + agents
  globales), wirea los hooks de Seraph en `~/.config/devin/config.json` y
  prepara la config de MCPs (`mcp_config.json`).
- El instalador no falla por piezas opcionales: corre un self-check de
  integridad al final y, si algo esencial falta, imprime
  `ATENCIÓN: faltan piezas esenciales de la instalación — …` y termina con
  exit 0 para que el resto del flujo siga. Si todo está, imprime
  `Integridad de instalación: OK`.
- El install también gestiona `~/.config/devin/mcp_config.json` (ver sección 7).

---

## 5. Verificar la instalación

```bash
bin/matrix hooks install_integrity_check | jq -e '.ok'
```

Debe devolver `true`. Si da `false`, el install ya imprimió qué pieza falta.

---

## 6. Registrar y activar proyectos

```bash
bin/matrix add <nombre> <ruta>
bin/matrix select <nombre>
```

- **`known`** = registrado en `.registry.json`. **`warm`** = en el set activo
  (`brain/state/workspace.yaml`). Siempre `warm ⊆ known`.
- `select` también clona el proyecto si es `type: remote`.
- **Nada se escribe dentro del proyecto:** no hay symlink `_brain` ni
  `AGENTS.local.md`. Un proyecto está en scope cuando su ruta registrada es
  ancestro de la carpeta actual.
- Ver el estado con `bin/matrix bindings` y la resolución de scope con
  `bin/matrix scope --tree`.

### Reconstruir la registry en otra máquina

`bin/matrix registry validate` lista cada proyecto registrado con el estado
de su path resuelto (`ok` / `missing` / `unreadable`), usando `get_project_path()`
(no el `.path` crudo), de modo que un proyecto `remote` nunca se marca inválido
espurio — si no está clonado, figura como `missing` pero es esperable hasta que
corras `matrix select` para clonarlo.

```bash
bin/matrix registry validate
bin/matrix registry validate --json
```

Para reconstruir en otra máquina: clonar el repo Matrix, crear
`brain/config.yaml`, y volver a agregar cada proyecto con `bin/matrix add`
(para `remote`, `matrix select` hace el clone). La registry no se migra como
archivo: los paths son per-machine.

---

## 7. MCPs (chrome-browser y context7)

El install gestiona `~/.config/devin/mcp_config.json` automáticamente:
- Si no existe, lo crea con `chrome-browser` y `context7`.
- Si existe y parsea, hace merge idempotente (agrega solo los servers que
  faltan, no toca servers ajenos).
- Si existe pero está corrupto, hace backup
  (`mcp_config.json.bak-<timestamp>`), crea uno limpio y lo reporta.

Estos MCPs son **opcionales** por contrato: si no están configurados, la
capacidad (`browser` / `docs-lookup`) simplemente no está disponible y el
agente lo dice.

**Grants MCP (`config.json permissions.allow`) — sin tocar.** `ensure-mcp-config.sh`
NO escribe en `~/.config/devin/config.json` `permissions.allow`. Evidencia
observada en la máquina de origen: `context7` está en `mcp_config.json` sin
ningún grant `mcp__context7__*` en `permissions.allow` y funciona (lo usa
Oracle vía el `allowed-tools` del `AGENT.md` generado, que sí lleva
`mcp__context7__*`). Los grants `mcp__chrome-browser__*` presentes en
`permissions.allow` son legacy/manuales y no se requieren para los servers de
`mcp_config.json`. <!-- TODO (R3, gate de Smith): confirmar que el MCP es *utilizable* en una instalación limpia, no solo presente en el JSON -->

---

## 8. Hardline (opcional)

```bash
modules/hardline/hardline-ctl.sh start
```

- Arranca el monitor (siempre) y el Telegram bridge (solo si existe el
  secrets file).
- **Secrets file canónico:** `brain/state/hardline/telegram.env` (resuelto
  desde `$MATRIX_ROOT`). Si falta, el script igual arranca el monitor, imprime
  la ruta exacta y el formato a crear, y no arranca el bridge.
- Al login: corré el mismo comando (o el alias `hardlines` de la sección 10
  para el webapp + dashboard).
- Estado y parada: `modules/hardline/hardline-ctl.sh status` / `stop`.

La ruta canónica `$MATRIX_ROOT/brain/state/hardline/telegram.env` está alineada
en los tres lugares que la referencian: `hardline-ctl.sh`, este README y la
skill `hardline-connect` de Devin (`.devin/skills/hardline-connect/SKILL.md`).
Si alguna otra doc habla de una ruta vieja (`~/.config/devin/hardline/...`),
ignorala: la fuente de verdad es la de arriba.

---

## 9. Modelos y costos

```bash
bin/matrix build --target=devin --template=gratis|barato|equilibrado|caro|veloz
```

- Default: `equilibrado`. La elección se persiste en
  `brain/state/adapter-templates.json`.
- `--template` cambia el `model:` de los **artefactos generados**
  (`adapters/devin/generated/.agents/**` → instalados en `~/.config/devin/`).
- **No** cambia el `agent.model` global de `~/.config/devin/config.json`
  (eso se edita aparte, si querés el modelo por defecto de tus sesiones).

---

## 10. Variables y aliases de tu cuenta

Matrix separa lo portátil (esta guía + repo) de lo específico de tu cuenta.
La plantilla de referencia es [`matrix.env.example`](matrix.env.example):
define `MATRIX_ROOT` con fallback a la ubicación del archivo y los aliases
`matrix` y `hardlines` de forma portable.

**Paso manual (requerido, el instalador NO toca tu `~/.bash_aliases`):**

```bash
cp matrix.env.example ~/.matrix.env
# editá ~/.matrix.env y agregá al final de ~/.bash_aliases:
echo 'source ~/.matrix.env' >> ~/.bash_aliases
```

> **ADVERTENCIA:** si ya tenés un `~/.bash_aliases` con templatesTools, **no lo
> pises**. Agregá lo de Matrix al final (o sourceá `~/.matrix.env` desde tu
> archivo de shell), sin borrar ni reordenar las entradas existentes.

- `matrix.env.example` es **solo referencia**: no incluye secretos ni tokens
  de la cuenta; si necesitás variables específicas (tokens de repos, rutas de
  tu cuenta), agregalas vos con comentarios `# REEMPLAZÁ con tu valor`, y
  nunca las commitees.
- Los tokens del bot de Telegram NO van acá: van en
  `brain/state/hardline/telegram.env` (ver sección 8).
- Si no sourceás el archivo, Matrix sigue funcionando: el alias/env es
  comodidad, no requisito.

---

## 11. Archivo global de Devin y los dos contratos

En tu cuenta coexisten **dos inyecciones de reglas distintas**; no se pisan y
Matrix no toca la que no le pertenece.

1. **`~/.config/devin/AGENTS.md` → reglas globales de tu cuenta (hoy:
   templatesTools).** Es **externo a Matrix**. En la máquina de origen es un
   **symlink** (no una copia):

   ```text
   ls -l ~/.config/devin/AGENTS.md
   → lrwxrwxrwx ... ~/.config/devin/AGENTS.md -> .../templatesTools/aiScripts/cognition/AGENTS.md
   readlink -f ~/.config/devin/AGENTS.md
   → .../templatesTools/aiScripts/cognition/AGENTS.md
   ```

   Matrix **no lo edita ni lo repunta**: es territorio de templatesTools.

2. **El contrato de Matrix se inyecta por otro canal:** la skill global de Neo
   (`~/.config/devin/skills/neo/SKILL.md`, instalada por `bin/matrix install`)
   + el activation preamble (`brain/data/activation-preamble.tmpl`, inyectado
   por los hooks de Seraph). No depende de `~/.config/devin/AGENTS.md`.

Si en otra máquina/cuenta querés el mismo comportamiento que acá, instalá
Matrix (secciones 1–9) y, aparte, mantené el `AGENTS.md` global de tu cuenta
como corresponda — son dos sistemas independientes.

---

## 12. Nota final

Este documento se inició en la Fase 2 del plan; cada fase posterior (3–7)
agrega su propia sección. Al cierre del plan, este documento queda completo.
