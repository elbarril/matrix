# The Hardline — multi-channel / AFK module (opt-in)

> The hardline is the phone exit: the only fixed line in and out of the Matrix. This module is the system's line to the outside world while you are away.

The Hardline reacts to external events and wakes Matrix to act. It is an **opt-in module**: the brain works without it.

## How it works

```text
Telegram message → telegram-bridge.py → modules/hardline/inbox.log
                                              │ (tail -F blocks on a new line)
                                              ▼
                         hardline-monitor.sh → bin/matrix hardline dispatch
                                              ▼
                            queue / single-flight / adapter / ack / Link trail
```

- The monitor blocks on `tail -F`; it has no polling interval or token cost while idle.
- The Telegram bridge uses Telegram Bot API `getUpdates` long polling only. It opens no inbound port and uses no webhook.
- The monitor writes a Link `hardline:event` entry and dispatches each accepted `<project>|<prompt>` line.
- Commander Lock guards unattended work.

## Local inbox usage

Start the monitor in its own terminal, tmux pane, or process-manager service:

```bash
modules/hardline/hardline-monitor.sh
```

A non-Telegram bridge may append the exact monitor format directly:

```bash
# <project> must be registered, except "matrix" (the workspace root).
echo 'mck|Update the README with a one-line note about Hardline events' >> modules/hardline/inbox.log
```

## Telegram bridge setup

The bridge is a small Python 3 script using only the standard library, matching the repository's existing Python tooling and avoiding a third-party dependency for one HTTPS request loop.

1. In Telegram, open **@BotFather**, send `/newbot`, follow its prompts, and copy the token it returns. Treat the token as a password; do not put it in a command-line argument, source file, `inbox.log`, queue, checkpoint, or Link entry.
2. Set the token in the environment of the bridge process. For an interactive shell session:

   ```bash
   export MATRIX_HARDLINE_TELEGRAM_BOT_TOKEN='paste-the-token-here'
   ```

   For an AFK service, provision the same variable from your OS keychain, service secret store, or a permissions-restricted environment file read by that service. Do not put the token in the process command line. To rotate it, replace the external secret and restart the bridge; no code change is needed.
3. Restrict the bot to your own chat in production. First send any ordinary message to your new bot, then run this one-shot command in the same environment as the token:

   ```bash
   modules/hardline/telegram-bridge.py --show-chat-ids
   ```

   It prints the numeric source chat ID(s) from pending updates and does not write `inbox.log`. It saves the polling cursor, so those displayed updates will not later be dispatched. Set the ID you intend to allow:

   ```bash
   export MATRIX_HARDLINE_TELEGRAM_ALLOWED_CHAT_ID='your-numeric-chat-id'
   ```

   This variable is optional so a user can deliberately operate a multi-chat bot, but it is strongly recommended for a personal AFK bot. When set, every other chat is ignored. You can alternatively obtain your numeric ID by messaging a reputable ID lookup bot such as @userinfobot; the bridge command above verifies the ID against your own bot's actual updates.
4. Start both long-lived processes with the control script:

   ```bash
   modules/hardline/hardline-ctl.sh start
   ```

   It writes PID files and logs to `brain/state/hardline/` and runs each process as a detached background service, so it survives the terminal that launched it. Check status with `modules/hardline/hardline-ctl.sh status` and stop with `modules/hardline/hardline-ctl.sh stop`. `restart` is also available.

   **Ruta canónica del secrets file:** `$MATRIX_ROOT/brain/state/hardline/telegram.env` (resuelto desde `$MATRIX_ROOT`, con la raíz del repo como fallback). Es la **única** fuente de verdad: la usa `hardline-ctl.sh`, la skill `hardline-connect` de Devin y este README. Si el archivo falta, el script igual arranca el monitor (que no depende de Telegram) pero se niega a arrancar el bridge, e imprime la ruta exacta y el formato a crear.

   If you prefer to start the two processes manually (for example, in two tmux panes to watch their logs directly), you can still run them separately:

   ```bash
   modules/hardline/hardline-monitor.sh
   modules/hardline/telegram-bridge.py
   ```

5. Send the bot exactly one single-line text message in this format:

   ```text
   <project> <task text>
   ```

   Example:

   ```text
   mck Update the README with a one-line note about Hardline events
   ```

   The bridge splits on the first whitespace, checks that `<project>` matches `[A-Za-z0-9._-]+`, and appends `mck|Update the README with a one-line note about Hardline events` to `inbox.log`. Multiline, non-text, missing-task, and invalid-project messages are ignored. The project must already be registered; "matrix" (the workspace root) is the exception.

The bridge retains only Telegram's non-secret resume cursor in `brain/state/hardline/telegram-offset`. It advances the cursor after every received update, including ignored updates, so a restart does not replay them. Delete that cursor only if you intentionally want Telegram's still-pending updates reconsidered. Telegram's `getUpdates` cannot operate while the bot has an active webhook; this deployment intentionally uses long polling and no webhook.

For parser-only testing without a token, `modules/hardline/telegram-bridge.py --parse-response PATH` reads a saved `getUpdates` JSON response and prints accepted `project|task` lines. It never calls Telegram or writes the inbox.

## Status webapp (open events)

`modules/hardline/status-webapp.py` is a small read-only, stdlib-only web page that
lists every currently open event (`queued`, `dispatched`, `orphaned`, `resumed`,
`requeued`) across all registered projects — the same set `matrix hardline status` reports,
but browsable and auto-refreshing instead of a one-shot CLI call.

```bash
modules/hardline/status-webapp.py
```

Open `http://127.0.0.1:8765/` in a browser on this machine. The page polls
`/api/events` every few seconds; there is also a plain JSON endpoint at
`/api/events` (optionally `?project=<name>`) for scripting. It never writes to
`queue.jsonl` and binds to `127.0.0.1` only — it is a localhost tool, not meant to
be exposed on the network. Override the port with
`MATRIX_HARDLINE_WEBAPP_PORT` and the poll interval with
`MATRIX_HARDLINE_WEBAPP_POLL_SECONDS`. Run it in its own terminal/tmux pane
(or a process manager) the same way as `hardline-monitor.sh`.

## Connected panel, webapp verbs, and alias

The webapp also shows a small **Connected** panel at the top of the page: it
lists every registered project and whether it is warm (`✓ warm`) or known-only
(`○ known`), plus whether the monitor and Telegram bridge are running. The
data comes from the same CLI sources the rest of the module uses:

```bash
bin/matrix bindings --json
modules/hardline/hardline-ctl.sh status --json
```

`hardline-ctl.sh` gained three new verbs for managing the webapp process:

```bash
modules/hardline/hardline-ctl.sh webapp-start   # idempotent; returns 0 if already running
modules/hardline/hardline-ctl.sh webapp-stop    # clean stop, removes PID file
modules/hardline/hardline-ctl.sh webapp-status  # one-line status
```

Plain `hardline-ctl.sh status` now also reports the webapp line, and
`hardline-ctl.sh status --json` returns machine-readable monitor/bridge state for
the webapp to consume.

For a one-shot "open the dashboard in the browser", source your `~/.bash_aliases`
and run:

```bash
hardlines
```

This starts the webapp (silently, in the background, and surviving the
terminal) and opens `http://127.0.0.1:8765/` in the default browser. Running it
again will not duplicate the webapp process.

## SessionEnd notification (retired)

The `SessionEnd` Telegram message (`adapters/devin/hooks/session_end_notify.py`) and its companion `UserPromptSubmit` timestamp hook (`adapters/devin/hooks/user_prompt_submit_timestamp.py`) were **retired by product decision**: the per-turn `Stop` notification below already tells you the agent finished a turn and is waiting, so the separate close signal was removed. Both scripts remain on disk and importable, but `adapters/devin/install-hooks.sh` no longer wires them; re-wiring is a two-line change if the close signal is ever wanted again. `session_audit.py` still runs on `SessionEnd` for the audit trail, unchanged.

## Stop-hook notification (every turn)

These notifications are governed by the Matrix feature flag `notify.hardline_outbound` (default ON). Setting it OFF and re-running `bin/matrix install --target=devin` un-wires the `Stop` hook (`adapters/devin/hooks/stop_notify.py`) from the Devin config; the script itself is never deleted.

A `Stop` hook sends a Telegram message after **every turn** — there is **no duration threshold**. It fires for sessions inside a registered Matrix project **and** for Matrix workspace mode (the pseudo-project `matrix`).

It fires only when all six of these gates are true; otherwise it no-ops silently and never blocks the agent:

1. The session was **not** started by the Hardline dispatcher (`MATRIX_HARDLINE_DISPATCH` is absent and `/proc` ancestry does not contain `hardline-dispatch.sh`).
2. `DEVIN_PROJECT_DIR` exists and is a directory.
3. `bin/matrix scope` resolves the directory to a registered Matrix project **or** the Matrix workspace root (`mode` `project`/`workspace`).
4. The Hardline Telegram bridge is running (`hardline-ctl.sh status --json` reports `bridge.running == true`).
5. `brain/state/hardline/telegram.env` exists and contains both `MATRIX_HARDLINE_TELEGRAM_BOT_TOKEN` and `MATRIX_HARDLINE_TELEGRAM_ALLOWED_CHAT_ID`.
6. The `Stop` payload carried a usable `last_assistant_message` (when absent, the message still goes out with a "no text" placeholder).

### Message format

```
💬 <project_name>
<output of the turn>
2026-08-01 16:16:32 -0300
```

- `<project_name>` is the registered project name, or `matrix` in workspace mode.
- The output is `last_assistant_message` from the `Stop` payload, truncated to 3800 characters (with a `… (truncado)` suffix when cut).
- A turn with no text sends `(sin texto en este turno)` — the fact that the turn ended is still useful signal.
- There is no duration, no "desde HH:MM", and no double-ping suppression: this is now the single outbound notification, so there is nothing to suppress.

## Reply to a bot message (additive grammar)

The `<project> <task>` grammar above stays **intact** for non-Telegram bridges:
they keep appending `<project>|<line>` to `inbox.log` and the monitor dispatches
them exactly as before. Telegram adds a second, additive grammar on top:

- **Replying to a bot message continues that conversation** instead of sending a
  new `<project> <task>` message. The reply does not touch `inbox.log`; the
  bridge dispatches it directly through the same `hardline dispatch` queue.
- A reply to a per-turn notification (`kind="turn"`) opens a **fresh headless
  run** seeded with the previous turn's output (context, truncated to 1200
  chars). Resuming a live TUI session is not supported by the Devin CLI
  (Spike B, Fase 0), so the first reply is the only one that "cuts" from the
  TUI.
- A reply to an ack notification (`kind="ack"`, the `✅ <project>: listo`
  messages) resumes that **headless session** (`-r <session_id>`), so the
  Telegram thread becomes a continuous conversation after the first reply.
- Every dispatched reply is tracked back to your chat, so its ack notification
  also comes back to Telegram, and that ack is itself a new reply anchor.
- Reply anchors expire after **48 hours** (TTL) and are capped at **1000
  entries**; the bridge sweeps both on every poll. Overrides:
  `MATRIX_HARDLINE_REPLY_TTL_SECONDS` and `MATRIX_HARDLINE_REPLY_MAX_ENTRIES`.
- A reply to a message that is no longer tracked (expired anchor, or a reply to
  a non-bot message) is ignored with a stderr note; resend the request as a
  normal `<project> <task>` message.
- The reply framing is a single line by design: `hardline dispatch` keeps its
  "events must be a single line" validation, so the direct reply channel
  respects the same invariant the inbox contract already enforces.

## Safety

- The token is read only from `MATRIX_HARDLINE_TELEGRAM_BOT_TOKEN` in the bridge process. It is never accepted as a CLI argument, logged, or written by the module.
- Never send secrets in a Telegram task. The monitor rejects secret-looking inbox lines, but that heuristic is not a safe secret-delivery channel.
- The monitor validates malformed lines before dispatch.
- Hardline work must never commit or push; the existing dispatch gate enforces that boundary.
