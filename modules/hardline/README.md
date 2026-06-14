# The Hardline — multi-channel / AFK module (opt-in)

> The hardline is the phone exit: the only fixed line in and out of the Matrix. This module is the system's line to the outside world while you are away.

The Hardline reacts to **external events** (a Telegram message, a webhook, a file drop) and wakes Matrix to act — using a persistent monitor over a tailed event stream so it costs **zero tokens while idle**. One poller, no busy-loop.

This is an **opt-in module**: it is fully decoupled from the core. The brain works without it.

## How it works

```text
external event  →  appended to modules/hardline/inbox.log
                        │  (tail -F, blocks until a line arrives)
                        ▼
            hardline-monitor.sh wakes, validates, and
            dispatches the request to Neo (via the host CLI),
            then returns to blocking. Zero tokens while waiting.
```

- The monitor blocks on `tail -F` — no polling interval, no token cost at rest.
- Every wake writes a Link ledger entry (`hardline:event`).
- Commander Lock guards any action the event triggers in unattended mode.

## Usage

```bash
# Start the monitor (foreground; run under your process manager / tmux for AFK)
modules/hardline/hardline-monitor.sh

# Feed it an event from any channel bridge (Telegram bot, webhook receiver, cron):
echo 'develop --headless mck' >> modules/hardline/inbox.log
```

## Channel bridges

The monitor only consumes `inbox.log`. A channel bridge (Telegram bot, webhook
server, email poller) is responsible for writing validated lines into it. Keep
bridges outside the core; they are deployment-specific.

## Safety

- Never write secrets into `inbox.log`.
- The monitor validates each line before dispatch; malformed lines are logged and skipped.
- Destructive actions are gated by Commander Lock (`brain/agents/lock.md`).
