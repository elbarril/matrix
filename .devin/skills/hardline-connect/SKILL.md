---
name: hardline-connect
description: >
  Levanta el módulo Hardline de Matrix (monitor + Telegram bridge + status
  webapp) con un solo comando y devuelve el link del dashboard de estado.
  Trigger: "conecta hardline", "conectá hardline", "arranca hardline",
  "arrancá hardline", "levanta hardline", "levantá hardline", "hardline up",
  "prendé hardline", "encendé hardline", "dale hardline", "start hardline".
model: adaptive
---

# hardline-connect — Devin Skill

Wrapper de instrucciones sobre el control script existente del módulo
Hardline (`modules/hardline/hardline-ctl.sh`). Esta skill **no** reimplementa
lógica: solo ejecuta el script en el orden correcto, interpreta su salida y
se la muestra al usuario en español simple, junto con el link del status
webapp.

## Cuándo usar esta skill

El usuario quiere que Hardline (monitor + bridge de Telegram + webapp de
estado) esté corriendo, sin tener que acordarse de los comandos manuales del
README del módulo.

## Rutas relevantes

Todas las rutas se resuelven desde `$MATRIX_ROOT` (la raíz del repo Matrix,
donde viven `AGENTS.md` + `brain/`). Los comandos de esta skill corren desde
`$MATRIX_ROOT` (ej. `modules/hardline/hardline-ctl.sh start`). Si `$MATRIX_ROOT`
no está definido en tu shell, entrá a la raíz del repo y corré los comandos
desde ahí, o resolvelo con `readlink -f .` en esa carpeta.

```
MATRIX_ROOT = <raíz del repo Matrix>
CTL         = $MATRIX_ROOT/modules/hardline/hardline-ctl.sh
BRIDGE_LOG  = $MATRIX_ROOT/brain/state/hardline/telegram-bridge.log
SECRETS     = $MATRIX_ROOT/brain/state/hardline/telegram.env
```

Referencia completa del módulo (leer si hace falta más contexto, pero no es
obligatorio releerla en cada corrida de esta skill):
`$MATRIX_ROOT/modules/hardline/README.md`

## Regla dura: nunca tocar el secrets file

Esta skill **lee o verifica la existencia** de `$MATRIX_ROOT/brain/state/hardline/telegram.env`,
nunca lo crea, sobreescribe, ni edita, y nunca inventa ni asume valores de
token o chat ID. Si falta o está mal, se lo decís al usuario tal cual (ver
sección de troubleshooting) y esperás a que lo arregle él.

## Pasos

1. **Arrancar monitor + bridge:**

   ```bash
   modules/hardline/hardline-ctl.sh start
   ```

   Es seguro correrlo aunque ya esté todo arriba: si el monitor o el bridge
   ya están corriendo, el script lo indica en su salida (`"already running.
   Refusing to start"`) y devuelve código de salida distinto de cero para
   ESE proceso, pero eso no es una falla real del flujo — significa que el
   servicio ya estaba en el estado deseado. Tratá ese caso como éxito parcial
   y seguí adelante; no lo reportes como error a menos que el proceso
   correspondiente termine efectivamente parado (ver el `status` del paso 3).

2. **Arrancar el status webapp (idempotente de verdad — devuelve 0 si ya está corriendo):**

   ```bash
   modules/hardline/hardline-ctl.sh webapp-start
   ```

3. **Verificar estado real y mostrárselo al usuario:**

   ```bash
   modules/hardline/hardline-ctl.sh status
   ```

   Mostrale la salida completa (monitor / bridge / webapp) tal cual. Si
   querés el detalle machine-readable para decidir el mensaje de
   troubleshooting del paso 4, también podés correr:

   ```bash
   modules/hardline/hardline-ctl.sh status --json
   ```

4. **Chequear salud del bridge de Telegram** (solo si el bridge figura
   corriendo en el paso 3 — si figura `stopped`, saltá directo a la sección
   de troubleshooting de más abajo, causa más probable: falta el secrets
   file):

   Esperá unos segundos (2-3s) después de arrancar y mirá las últimas
   líneas del log:

   ```bash
   tail -n 20 brain/state/hardline/telegram-bridge.log
   ```

   Si ese log muestra errores repetidos de request fallida contra la API de
   Telegram (por ejemplo `HTTP Error`, `Unauthorized`, `401`, `403`, o el
   mismo error de conexión repitiéndose en bucle cada pocos segundos), es la
   señal típica de un `MATRIX_HARDLINE_TELEGRAM_BOT_TOKEN` o
   `MATRIX_HARDLINE_TELEGRAM_ALLOWED_CHAT_ID` inválido. Andá a la sección de
   troubleshooting.

5. **Devolver el resultado final al usuario**, siempre incluyendo el link:

   ```
   http://127.0.0.1:${MATRIX_HARDLINE_WEBAPP_PORT:-8765}/
   ```

   (si el usuario no seteó `MATRIX_HARDLINE_WEBAPP_PORT`, es `http://127.0.0.1:8765/`).

## Troubleshooting: bridge caído o en loop de error

Si en el paso 3/4 ves que:

- el bridge figura `stopped` porque no existe el secrets file, o
- el bridge figura `running` pero el log muestra requests fallidas en bucle,

decile al usuario **exactamente esto**, sin completar ni inventar valores:

> El bridge de Telegram necesita el archivo `$MATRIX_ROOT/brain/state/hardline/telegram.env`
> con estas dos líneas exactas:
>
> ```bash
> export MATRIX_HARDLINE_TELEGRAM_BOT_TOKEN='...'
> export MATRIX_HARDLINE_TELEGRAM_ALLOWED_CHAT_ID='...'
> ```
>
> Completá `'...'` con tu token real de @BotFather y tu chat ID numérico
> (ver `modules/hardline/README.md`, sección "Telegram bridge setup", para
> cómo obtenerlos). Yo no puedo generar ni adivinar esos valores.

No intentes crear, completar ni "arreglar" ese archivo vos mismo bajo ninguna
circunstancia. El monitor y el webapp pueden seguir funcionando igual sin el
bridge; informá ese estado parcial como válido si es lo que hay.

## Qué NO hace esta skill

- No reimplementa `hardline-ctl.sh`; solo lo invoca.
- No modifica `$MATRIX_ROOT/brain/state/hardline/telegram.env`.
- No corre `stop` ni `restart` a menos que el usuario lo pida explícitamente
  (esta skill es solo el flujo de "conectar/levantar").
