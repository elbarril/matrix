# Matrix - Fuente de la Verdad Absoluta

**Ultima actualizacion**: 2026-06-02
**Estado**: Verificado contra codigo fuente real

---

## 1. Descripcion General del Sistema

Matrix es un motor de inteligencia personal para gestion de proyectos. Implementa un patron de coordinador maestro con agentes especialistas, donde toda la orquestacion es dirigida por prompts que un LLM interpreta.

### Principios fundamentales

- **Agente maestro unico**: Deus Ex Machina es la unica interfaz de usuario
- **Estado basado en archivos**: YAML, JSON y JSONL. No hay bases de datos
- **Puente Symlink**: Proyectos activos reciben symlink `_brain` -> `brain/`
- **Orquestacion por prompts**: Flujo de control como instrucciones en lenguaje natural
- **Silencio operativo**: Solo muestra resultados finales

### Flujo completo de operacion

1. Usuario registra proyectos con `matrix add` y selecciona con `matrix select` (crea `_brain`)
2. Invoca agente maestro con `/deus-ex-machina`
3. Agente ejecuta scripts de validacion (config, contexto, routing, brain state)
4. Carga configuracion, contexto, y recursos de routing
5. Analiza solicitud contra keywords de cada especialista
6. Enruta silenciosamente al especialista via `run_subagent`
7. Especialista ejecuta y devuelve resultados
8. Agente maestro sintetiza, registra logs, y escribe checkpoints

---

## 2. Estructura de Archivos Verificada

```
matrix/
├── .context.yaml               # Contexto del proyecto activo
├── .registry.json              # Registro de proyectos (12 actualmente)
├── .gitignore
├── AGENTS.md                   # Contrato operativo canonico (431 lineas)
├── DEVIN.md                    # Notas integracion Devin (195 lineas)
├── README.md                   # Documentacion general (235 lineas)
├── onboarding.html             # Pagina onboarding visual (1590 lineas)
├── bin/matrix                  # CLI principal (467 lineas, bash)
├── .agents/
│   ├── skills/deus-ex-machina/ # Agente maestro (Skill)
│   │   ├── SKILL.md            # Definicion (217 lineas)
│   │   ├── scripts/            # 9 scripts validacion/logging
│   │   └── resources/assets/
│   │       ├── logging/log-entry-structure.md
│   │       └── routing/        # 4 archivos de routing
│   └── agents/                 # 9 especialistas (Subagents)
│       ├── smith/AGENT.md      morpheus/  oracle/  trinity/
│       ├── architect/AGENT.md  sentinel/  sion/
│       ├── wachowski/AGENT.md  keymaker/
├── brain/
│   ├── config.yaml             # Config usuario (17 lineas)
│   ├── config/global-skills.yaml
│   ├── config/projects/        # chronicle.yaml, pas.yaml
│   ├── workflows/README.md     # Solo placeholder
│   └── state/                  # Estado runtime
│       ├── work-process-log.jsonl    # Log activo (JSONL)
│       ├── validation-report.json
│       ├── checkpoints.jsonl
│       ├── workspace.yaml
│       ├── pas-tools-index.yaml
│       └── work-process-log-archive/
├── clients/                    # GITIGNORED
└── docs/                       # Analisis (ver seccion 10)
```

---

## 3. CLI - bin/matrix

Script bash (467 lineas). Requiere `jq`.

| Comando | Funcion |
|---------|---------|
| `list` | Lee `.registry.json`, marca el activo |
| `add <nombre> [ruta]` | Registra proyecto, detecta local/remoto |
| `select <nombre>` | Deselecciona previo, crea `_brain` symlink, actualiza `.context.yaml` y `workspace.yaml` |
| `deselect` | Elimina `_brain`, resetea contexto a null |
| `status` | Muestra proyecto activo, estado symlink, ultimos 3 checkpoints |
| `checkpoint "<nota>"` | Escribe a `checkpoints.jsonl` + intenta log via `matrix-log-entry.sh` |

Resuelve MATRIX_DIR desde ubicacion del script. Elimina trailing slashes. Expande tildes. Para remotos, clona a `clients/`.

---

## 4. Agente Maestro - Deus Ex Machina

- **Archivo**: `.agents/skills/deus-ex-machina/SKILL.md` (217 lineas)
- **Tipo**: Devin Skill, modelo swe-1-5
- **Invocacion**: `/deus-ex-machina` o `skill invoke deus-ex-machina`

### Resolucion MATRIX_ROOT
1. Si existe `_brain` symlink -> resuelve y sube un nivel
2. Si existe `brain/` + `.agents/` en cwd -> usa cwd
3. Sino -> error

### Pre-activacion: 4 scripts secuenciales (falla = halt)
### Activacion: 12 pasos (config -> workspace mode -> contexto -> routing -> saludo -> log -> wachowski check -> context prep -> analisis -> route -> log specialist -> checkpoint)
### Post-activacion: validation-report.json
### 18 reglas operativas (silencio, igualdad de especialistas, espanol coloquial)

---

## 5. Especialistas (9 agentes)

| Agente | Dominio | Permisos Write | Herramientas especiales |
|--------|---------|----------------|------------------------|
| **Smith** | Bugs, debugging | Write(*) | exec, edit, todo_write |
| **Morpheus** | Planificacion | Write(matrix/*) | exec, todo_write |
| **Oracle** | Investigacion | Write(matrix/*) | web_search, webfetch |
| **Trinity** | Codigo, arquitectura | Write(*) | exec, edit, todo_write |
| **Architect** | Code review | Write(matrix/*) | exec |
| **Sentinel** | Seguridad | Write(matrix/*) | exec |
| **Sion** | Documentacion | Write(*) | edit |
| **Wachowski** | Integral Matrix | Write(matrix/*) | skill, run_subagent |
| **Keymaker** | Git | Write(*) | exec, find_file_by_name |

**Wachowski**: Autosuficiente, flujo integrado (analizar->planear->implementar->verificar->documentar). Multi-call solo si: >300 chars AND 3+ verbos AND keyword "fases/etapas" AND >5 archivos.

**Keymaker**: Solo con pedido EXPLICITO del usuario. Keywords git solas no activan.

---

## 6. Sistema de Routing (orden de prioridad)

1. Matrix Workspace Mode (cwd == MATRIX_ROOT) -> todo a Wachowski
2. Keywords Matrix -> Wachowski
3. Git explicito -> Keymaker
4. Skill priority del proyecto (local_first / matrix_first / hybrid)
5. Single specialist (una keyword domain)
6. Multi-specialist (patron de coordinacion)

### 7 patrones de coordinacion
1. Desarrollo Seguro: Trinity->Sentinel->Trinity->Architect
2. Investigacion+Accion: Oracle->Especialista
3. Planificacion+Ejecucion: Morpheus->Multiples
4. Debug+Fix: Smith->Trinity
5. Documentacion+Implementacion: Trinity->Sion
6. Planificacion+Documentacion: Morpheus->Sion
7. Implementacion+Git: Trinity/Smith->Keymaker (solo si git pedido)

---

## 7. Scripts (todos _brain-aware)

| Script | Funcion | Lineas |
|--------|---------|--------|
| `matrix-pre-activation-checks.sh` | Orquesta los 4 scripts de validacion | 122 |
| `matrix-validate-config.sh` | Verifica brain/config.yaml (existencia + YAML valido) | 84 |
| `matrix-validate-context.sh` | Verifica .context.yaml (o Matrix Workspace Mode) | 77 |
| `matrix-validate-routing-resources.sh` | Verifica 4 archivos routing existen | 90 |
| `matrix-init-brain-state.sh` | Crea directorios/archivos de estado si faltan | 91 |
| `matrix-log-entry.sh` | Escribe a work-process-log.jsonl. Filtrado agresivo (descarta activaciones exitosas). File locking. Rotacion a 1000 lineas | 188 |
| `matrix-validate-activation.sh` | Verifica compliance post-activacion -> validation-report.json | 148 |
| `matrix-log-metrics.sh` | Calcula metricas de calidad del log | 128 |
| `matrix-execute-with-error-logging.sh` | Wrapper con reintentos y error logging a system-errors.log (archivo inexistente) | 292 |

---

## 8. Archivos de Configuracion

- **brain/config.yaml**: user, language, timezone, log_level, umbrales de metricas
- **.context.yaml**: active_project, active_project_path, last_updated, session_id
- **.registry.json**: 12 proyectos registrados (name, path, type, added)
- **brain/config/global-skills.yaml**: Skills externos, patrones de uso por contexto
- **brain/config/projects/*.yaml**: Config por proyecto (skills, prioridad, integracion Matrix)

---

## 9. Archivos de Estado

- **work-process-log.jsonl**: Log principal (JSONL)
- **validation-report.json**: Ultimo reporte validacion (JSON)
- **checkpoints.jsonl**: Checkpoints registrados
- **workspace.yaml**: Refleja proyecto activo
- **work-process-log-archive/**: Archivos rotados
- **pas-tools-index.yaml**: Indice herramientas PAS (17KB)

---

## 10. Documentos de Analisis (docs/)

Artefactos de ingenieria inversa del sistema. 9 subdirectorios vacios eliminados (2026-06-02). 21 archivos en la raiz de docs/.

---

## 11. Seguros para Eliminar

### Archivos/directorios eliminados (2026-06-02)

| Item | Estado |
|------|--------|
| `brain/agents/` (completo, ~20 dirs vacios) | ELIMINADO |
| `brain/state/work-process-log.yaml` | ELIMINADO |
| `brain/state/validation-report.yaml` | ELIMINADO |
| `brain/state/work-process-log-legacy.jsonl` | ELIMINADO |
| `docs/agent-system/` y 8 subdirs vacios mas | ELIMINADOS |
| `.agents/skills/deus-ex-machina/resources/references/` | ELIMINADO |
| `brain/state/sessions/` | ELIMINADO |
| `brain/state/checkpoints/` | ELIMINADO |

### Contenido corregido en archivos

- **`repository_mapping.md`**: Eliminadas refs a `.matrix-root`, `docs/ (removed)`, `analysis/`, `matrix-run-script.sh`

---

## 12. Errores e Inconsistencias

### Errores claros

1. **Log YAML activo**: RESUELTO (2026-06-02) - archivo eliminado
2. **Doble validation report**: RESUELTO (2026-06-02) - validation-report.yaml eliminado
3. **Filtrado silencioso mata metricas**: RESUELTO (2026-06-02) - bloque L60-62 eliminado de matrix-log-entry.sh
4. **Scripts inexistentes en docs**: RESUELTO (2026-06-02) - refs eliminadas de repository_mapping.md
5. **system-errors.log inexistente**: Pendiente - matrix-execute-with-error-logging.sh obsoleto pero no eliminado
6. **Rotacion documentada vs real**: Parcial - codigo usa 1000, no documentado explicitamente en README (sin referencias incorrectas tampoco)
7. **brain/data/ no existe**: Solo referenciado en SYSTEM_TRUTH.md (este archivo); no hay refs activas en scripts o agentes
8. **Checkpoint con project "null"**: Sin cambios
9. **Shell variable persistence en SKILL.md**: RESUELTO (2026-06-13) - `<pre-activation-checks>` usaba `$MATRIX_ROOT` de un bloque bash previo. En Devin cada bloque bash corre en shell separada, variable no persiste. Fix: bloque `<pre-activation-checks>` ahora auto-contenido con resolucion de MATRIX_ROOT inline. Nota critica agregada a `<environment-setup>`.
10. **Routing usa subagents genericos en vez de especialistas**: RESUELTO (2026-06-13) - SKILL.md step 10 solo decia "siguiendo routing-rules.md" sin especificar mecanismo exacto. Agente usaba `explore subagent` y `general subagent` (tipos genericos Devin) en lugar de agentes especializados (`oracle`, `sion`). Fix: nueva seccion `<specialist-invocation>` en SKILL.md con mecanismo exacto de invocacion via `run_subagent` con agent name. Step 10 actualizado para referenciar esta seccion.
11. **Validacion routing no verifica AGENT.md de especialistas**: RESUELTO (2026-06-13) - `matrix-validate-routing-resources.sh` solo validaba 4 archivos MD de routing. No verificaba existencia de archivos AGENT.md en `.agents/agents/`. Fix: agregada validacion de los 9 AGENT.md de especialistas al script. Pre-activation ahora falla correctamente si faltan archivos de agente.

### Inconsistencias

1. **Prioridad de skills contradictoria**: RESUELTO en sesion anterior - ambas lineas dicen `local > global > Matrix`
2. **Multi-call threshold**: RESUELTO (2026-06-02) - wachowski/AGENT.md regla 16 actualizada a >300 chars AND (logica AND, igual que specialist-specific-rules.md)
3. **Referencias a .yaml vs .jsonl**: Sin refs incorrectas en AGENTS.md/README.md (ya usaban .jsonl)
4. **Neo/Cypher como agentes vs protocolos**: Sin cambios - protocolos de comunicacion sin AGENT.md
5. **Wachowski Exec path relativo**: Sin cambios - pendiente analisis separado
6. **Verbosity threshold**: Sin cambios

---

## 13. Problemas de Uso desde Diferentes Directorios

### Desde Matrix root (`~/www/emisrepos/matrix/`)
- Matrix Workspace Mode activado. Todo a Wachowski. Correcto por diseno.

### Desde proyecto activo con `_brain`
- Funciona correctamente. Si symlink roto: `matrix deselect` + `matrix select`.

### Desde subdirectorio de proyecto activo
- RESUELTO (2026-06-02): SKILL.md usa traversal hacia arriba buscando `_brain` o `brain/+.agents/` en cualquier directorio ancestro.

### Desde directorio no registrado sin `_brain`
- Scripts de validacion hacen fallback a ubicacion del script (funciona). Pero SKILL.md falla. **Solucion**: registrar y seleccionar proyecto primero.

### Skill no descubrible
- DOCUMENTADO (2026-06-02) en README.md Quick Start > Initial Setup. Comando: `ln -s ~/www/emisrepos/matrix/.agents/skills/deus-ex-machina ~/.agents/skills/deus-ex-machina`

### Contenedor Docker / CI
- Symlinks, jq, flock, python3 pueden no estar disponibles. No soportado en v1.

### Paths con espacios
- Mayoria de variables estan bien entrecomilladas. Riesgo bajo pero no testeado.

---

## 14. Mejoras Recomendadas

1. ✓ DONE Eliminar `work-process-log.yaml` (2026-06-02)
2. ✓ DONE Eliminar `validation-report.yaml` (2026-06-02)
3. ✓ DONE Corregir filtrado de activacion en `matrix-log-entry.sh` (2026-06-02)
4. ✓ DONE Resolver contradiccion de prioridad de skills en `routing-rules.md` (sesion anterior)
5. ✓ DONE Unificar threshold multi-call en Wachowski regla 16 (2026-06-02)
6. ✓ DONE Sin refs incorrectas a .yaml en AGENTS.md/README.md
7. ✓ DONE Eliminar `brain/agents/` (2026-06-02)
8. ✓ DONE Limpiar 9 subdirectorios vacios en docs/ (2026-06-02)
9. ✓ DONE No hay refs activas a brain/data/ en scripts o agentes
10. Pendiente - rotation=1000 no documentada explicitamente (sin docs incorrectas tampoco)
11. ✓ DONE Shell variable persistence en pre-activation-checks (2026-06-13)
12. ✓ DONE Routing: agregar seccion `<specialist-invocation>` con mecanismo exacto (2026-06-13)
13. ✓ DONE matrix-validate-routing-resources.sh: validar AGENT.md de especialistas (2026-06-13)
