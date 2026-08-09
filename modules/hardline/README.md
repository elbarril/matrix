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
# <project> must be registered and bound, except "matrix" (the workspace root).
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

   The control script expects the secrets file at `brain/state/hardline/telegram.env` (resolved from `$MATRIX_ROOT`, with the repo root as fallback). If that file is missing, the script still starts the monitor (which has no Telegram dependency) but refuses to start the bridge and prints the exact path and format to create.

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

   The bridge splits on the first whitespace, checks that `<project>` matches `[A-Za-z0-9._-]+`, and appends `mck|Update the README with a one-line note about Hardline events` to `inbox.log`. Multiline, non-text, missing-task, and invalid-project messages are ignored. The project must already be registered and bound; "matrix" (the workspace root) is the exception.

The bridge retains only Telegram's non-secret resume cursor in `brain/state/hardline/telegram-offset`. It advances the cursor after every received update, including ignored updates, so a restart does not replay them. Delete that cursor only if you intentionally want Telegram's still-pending updates reconsidered. Telegram's `getUpdates` cannot operate while the bot has an active webhook; this deployment intentionally uses long polling and no webhook.

For parser-only testing without a token, `modules/hardline/telegram-bridge.py --parse-response PATH` reads a saved `getUpdates` JSON response and prints accepted `project|task` lines. It never calls Telegram or writes the inbox.

## Status webapp (open events)

`modules/hardline/status-webapp.py` is a small read-only, stdlib-only web page that
lists every currently open event (`queued`, `dispatched`, `orphaned`, `resumed`,
`requeued`) across all bound projects — the same set `matrix hardline status` reports,
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
lists every registered project and whether it is currently bound (`✓ bound` or
`✗ not bound`), plus whether the monitor and Telegram bridge are running. The
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

## SessionEnd notification for bound projects

When `adapters/devin/install-hooks.sh` runs, it wires a second `SessionEnd` hook (`adapters/devin/hooks/session_end_notify.py`) alongside `session_audit.py`. This hook sends a single "básico" Telegram message when a Devin CLI session ends inside a **Matrix-bound project**:

- `🔔 <project_name>`
- `Sesión finalizada — <reason>`
- `<timestamp>`

It fires only when all four of these gates are true; otherwise it no-ops silently and never blocks session teardown:

1. The session was **not** started by the Hardline dispatcher (`MATRIX_HARDLINE_DISPATCH` is absent and `/proc` ancestry does not contain `hardline-dispatch.sh`).
2. `DEVIN_PROJECT_DIR` resolves to a currently bound Matrix project (`_brain` symlink + `bin/matrix bindings --json` longest-prefix match).
3. The Hardline Telegram bridge is running (`hardline-ctl.sh status --json` reports `bridge.running == true`).
4. `brain/state/hardline/telegram.env` exists and contains both `MATRIX_HARDLINE_TELEGRAM_BOT_TOKEN` and `MATRIX_HARDLINE_TELEGRAM_ALLOWED_CHAT_ID`.

This hook is intentionally separate from `session_audit.py` so a slow or failing Telegram POST cannot delay the audit trail or `bin/matrix session close`. It never duplicates the Hardline ack path; sessions dispatched through `hardline-dispatch.sh` are excluded by construction.

## Stop-hook notification for long unattended turns

A second, independent Telegram notification is fired from a new `Stop` hook (`adapters/devin/hooks/stop_notify.py`), with a companion `UserPromptSubmit` hook (`adapters/devin/hooks/user_prompt_submit_timestamp.py`) that only stamps a clock. Both are wired into the Devin CLI by `adapters/devin/install-hooks.sh`.

This hook notifies you when the agent finishes a turn and is waiting for your input, **but only when the turn was long enough to be worth interrupting you for**. Shorter turns are a silent no-op.

It fires only when all five of these gates are true; otherwise it no-ops silently and never blocks the agent:

1. The session was **not** started by the Hardline dispatcher (`MATRIX_HARDLINE_DISPATCH` is absent and `/proc` ancestry does not contain `hardline-dispatch.sh`).
2. `DEVIN_PROJECT_DIR` resolves to a currently bound Matrix project (`_brain` symlink + `bin/matrix bindings --json` longest-prefix match).
3. The Hardline Telegram bridge is running (`hardline-ctl.sh status --json` reports `bridge.running == true`).
4. `brain/state/hardline/telegram.env` exists and contains both `MATRIX_HARDLINE_TELEGRAM_BOT_TOKEN` and `MATRIX_HARDLINE_TELEGRAM_ALLOWED_CHAT_ID`.
5. The turn's elapsed time (since the last message you sent) exceeds the configured threshold.

### Threshold

The default threshold is **1800 seconds (30 minutes)**. Only turns longer than this trigger a message. You can override it by adding this key to the existing `brain/state/hardline/telegram.env` secrets file (no new file):

```bash
MATRIX_HARDLINE_STOP_NOTIFY_THRESHOLD_SECONDS=900
```

Missing, empty, non-numeric, or non-positive values silently fall back to the 1800s default.

### Double-ping suppression

If `stop_notify.py` already sent a notification within the last **60 seconds** for the same project, the `SessionEnd` message for that session is suppressed — the user was already told "the agent stopped and is waiting" moments ago. The 60s window is fixed and non-configurable.

### Message format

```
⏳ <project_name>
Turno largo terminado — esperando tu respuesta
Duración: 33m (desde 14:02)
2026-08-01 16:16:32 -0300
```

The elapsed duration is shown in whole minutes (e.g. `35m` or `2h 14m`). No summary of the agent's work is included because the `Stop` payload carries no usable turn summary.

## Safety

- The token is read only from `MATRIX_HARDLINE_TELEGRAM_BOT_TOKEN` in the bridge process. It is never accepted as a CLI argument, logged, or written by the module.
- Never send secrets in a Telegram task. The monitor rejects secret-looking inbox lines, but that heuristic is not a safe secret-delivery channel.
- The monitor validates malformed lines before dispatch.
- Hardline work must never commit or push; the existing dispatch gate enforces that boundary.
