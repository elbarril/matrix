---
name: harness-health-report
description: >
  Genera un reporte + dashboard HTML del funcionamiento del harness Matrix
  (commits, checkpoints, activity log, lessons, validation reports, routing
  signals, orphan-close attempts) a partir de una única extracción
  determinística de métricas, reusable por Oracle, Neo, Trinity, Smith y
  Architect sin que cada uno reinvente los comandos. Trigger: "reporte de
  funcionamiento del harness", "cómo está funcionando el harness",
  "dashboard del harness", "métricas del harness", "salud del sistema
  Matrix", "harness health report", "generá el dashboard de nuevo".
model: adaptive
---

# harness-health-report — Devin Skill

Wrapper de una única extracción determinística de métricas del harness
Matrix. Esta skill **no** reimplementa el diseño de cada dataset en la
cabeza de cada agente: corre un único script (`extract_metrics.py`), guarda
su salida, y todo agente posterior lee esa misma salida.

## Cuándo usar esta skill

El usuario (o Oracle/Neo/Trinity/Smith/Architect en el curso de otro
trabajo) necesita un reporte o dashboard de salud/funcionamiento del
harness Matrix: commits, checkpoints, activity log, lecciones, último
`validation-report.json`, costos del harness (bytes del contrato,
artefactos, ratio BLOCK de `phase:close`, tamaño del audit log,
estado del throttling de activación), historial de señales de ruteo,
intentos de cierre huérfano. Ver el trigger completo en el frontmatter
de arriba.

## Rutas relevantes

```
MATRIX_ROOT = <raíz del repo Matrix>  (resolvela desde la ubicación de este SKILL.md o con $MATRIX_ROOT)
SCRIPT      = $MATRIX_ROOT/.devin/skills/harness-health-report/scripts/extract_metrics.py
TEMPLATE    = $MATRIX_ROOT/.devin/skills/harness-health-report/templates/dashboard.html.tmpl
SCHEMA      = $MATRIX_ROOT/.devin/skills/harness-health-report/contracts/metrics-schema.json
```

Convención de salida (una corrida = un snapshot con su propio epoch en el
nombre de archivo, para no pisar corridas anteriores):

```
brain/output/research/harness-metrics-<epoch>.json
brain/output/research/harness-dashboard-<epoch>.html
```

(`<epoch>` = `snapshot.generated_at_epoch` del propio JSON producido por
esa corrida.)

## Paso a paso

1. **Correr el script una vez** (con la capability `run-command`):

   ```bash
   python3 .devin/skills/harness-health-report/scripts/extract_metrics.py \
     --out brain/output/research/harness-metrics-<epoch>.json \
     --pretty \
     --out-md brain/output/research/harness-metrics-<epoch>.md \
     --emit-ledger-event
   ```

   Añadí `--emit-ledger-event` solo cuando se quiere que esta corrida se
   registre en el ledger (`metrics:snapshot matrix "epoch=<epoch>
   path=<--out>"`). Para validaciones o re-lecturas que no deben ensuciar
   el ledger, omití el flag.

   Esta es **LA extracción autoritativa de la sesión**. Todo agente
   posterior en la misma sesión (Oracle para narrar hallazgos, Trinity/
   Architect para construir o revisar el dashboard, Smith para gatear)
   **lee ese mismo archivo** — no vuelve a correr el script salvo que el
   propósito explícito sea comparar drift entre dos snapshots.

   Ejemplo real de esta sesión de por qué "correr de nuevo" puede ser
   legítimo y no un error de medición: `routing_signal_history.total_lines`
   pasó de 11 a 12 líneas entre dos lecturas de la misma sesión porque el
   propio `validate_routing_signal` seguía disparándose en vivo mientras
   se trabajaba — actividad genuina del sistema en tiempo real, no un bug
   del extractor. Si el propósito es medir ese tipo de drift, correr el
   script de nuevo es correcto; si el propósito es simplemente "leer el
   estado", una sola corrida basta y las demás lecturas reusan su salida.

2. **Validar la salida contra el contrato** (`contracts/metrics-schema.json`):

   ```bash
   python3 -m jsonschema -i brain/output/research/harness-metrics-<epoch>.json \
     .devin/skills/harness-health-report/contracts/metrics-schema.json
   ```

   `jsonschema` ya está disponible en el entorno de build; si en otro
   entorno no lo estuviera, este paso cae al validador stdlib puro
   `scripts/validate_metrics.py` (a crear bajo demanda), pero hoy el
   done-criterion se cierra con el comando de arriba.

3. **Construir el dashboard HTML** (si se pidió) usando
   `templates/dashboard.html.tmpl` como referencia de estructura/estética,
   reemplazando cada `{{dataset.campo}}` con el valor real del JSON de la
   corrida (ver nota al pie dentro del propio template: no hay motor de
   reemplazo automático en esta pasada).

4. **Gatear con Smith** si el dashboard/script fue tocado o generado como
   parte de un fix — ver la sección de la lección 50 más abajo.

## Si Architect necesita los datos y no tiene `run-command`

Al Architect **nunca se le pide que ejecute nada**. Se le pasa la ruta del
`.json` (o del `.md` espejo) de salida de la corrida ya hecha, para que lo
lea con su capability `read`. La extracción la corre quien tenga
`run-command` disponible en esa sesión (típicamente Neo, Trinity o Smith);
Architect trabaja siempre sobre el archivo ya persistido.

## Recordatorio explícito — lección 50 del Zion Archive

`brain/data/lessons.md`, lección 50, cita textual del hallazgo central:

> El gate mecánico de `post_run_audit` sobre remediaciones de Smith ya
> funciona en la práctica — atrapó, en vivo, exactamente el defecto que la
> lección 23 predice. [...] Smith nunca escribió su propio artefacto de
> eval obligatorio (`brain/output/eval/<target>.md` con el bloque
> `<!-- MATRIX:EVAL-PREREG v1 -->`) — solo lo narró en su respuesta.
> `bin/matrix hooks post_run_audit` [...] lo marcó correctamente como
> `compliant: false` / `eval_artifact_not_found`.

Si, en el curso de esta skill, **Smith aplica un fix Tier 1/2** sobre el
dashboard o sobre `extract_metrics.py` (por ejemplo, corrigiendo un dataset
mal calculado que él mismo detectó al gatear), tiene que:

1. **Pre-registrar en `brain/output/eval/<target>.md`** el bloque
   `<!-- MATRIX:EVAL-PREREG v1 -->` **ANTES** de tocar cualquier archivo.
2. **Cerrar corriendo `bin/matrix hooks post_run_audit`** sobre su propio
   artefacto **antes** de reportar el fix como terminado — no alcanza con
   narrarlo en texto, como ya se probó en vivo que el gate detecta esa
   omisión.

## Qué NO hace esta skill

- No reemplaza el ruteo de Neo — Neo sigue decidiendo cuándo se usa esta
  skill, esta skill no se auto-invoca.
- No decide a quién delegar (Morpheus/Architect siguen siendo quienes
  deciden asignación de trabajo).
- No reemplaza el juicio narrativo de Oracle — el script produce números
  crudos, no un análisis ni una narrativa de hallazgos.
- No reemplaza el diseño visual de Trinity para gráficos nuevos — el
  template es un punto de partida estético, no un generador de
  visualizaciones nuevas.
- No mecaniza el pre-registro de Smith — el paso de `MATRIX:EVAL-PREREG
  v1` sigue siendo manual, esta skill solo lo recuerda explícitamente.
- No gestiona retención de snapshots viejos — no borra, rota ni archiva
  corridas anteriores de `harness-metrics-<epoch>.json`/`.html`.
- No es un dashboard en vivo — cada corrida es una foto fija al momento en
  que se ejecutó el script, no una vista que se actualiza sola.
