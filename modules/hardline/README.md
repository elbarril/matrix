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
# <project> must be registered and bound.
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

   The control script expects the secrets file at `~/.config/devin/hardline/telegram.env`. If that file is missing, the script still starts the monitor (which has no Telegram dependency) but refuses to start the bridge and prints the exact path and format to create.

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

   The bridge splits on the first whitespace, checks that `<project>` matches `[A-Za-z0-9._-]+`, and appends `mck|Update the README with a one-line note about Hardline events` to `inbox.log`. Multiline, non-text, missing-task, and invalid-project messages are ignored. The project must already be registered and bound.

The bridge retains only Telegram's non-secret resume cursor in `brain/state/hardline/telegram-offset`. It advances the cursor after every received update, including ignored updates, so a restart does not replay them. Delete that cursor only if you intentionally want Telegram's still-pending updates reconsidered. Telegram's `getUpdates` cannot operate while the bot has an active webhook; this deployment intentionally uses long polling and no webhook.

For parser-only testing without a token, `modules/hardline/telegram-bridge.py --parse-response PATH` reads a saved `getUpdates` JSON response and prints accepted `project|task` lines. It never calls Telegram or writes the inbox.

## Safety

- The token is read only from `MATRIX_HARDLINE_TELEGRAM_BOT_TOKEN` in the bridge process. It is never accepted as a CLI argument, logged, or written by the module.
- Never send secrets in a Telegram task. The monitor rejects secret-looking inbox lines, but that heuristic is not a safe secret-delivery channel.
- The monitor validates malformed lines before dispatch.
- Hardline work must never commit or push; the existing dispatch gate enforces that boundary.
