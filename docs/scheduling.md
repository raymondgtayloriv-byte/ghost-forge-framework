# Scheduling

Stages 01–04 and 06 of the pipeline are headless-safe: capture, triage,
steward collection, review bridging, and proposal building never write
canonical truth. Schedule them freely. Stages 05 (decide) and 07 (apply)
require the human.

## Reference: macOS launchd

The proven reference scheduler is launchd. An example agent that runs the
non-canonical loop every 30 minutes:

```xml
<!-- ~/Library/LaunchAgents/com.ghostforge.loop.plist -->
<plist version="1.0">
<dict>
  <key>Label</key><string>com.ghostforge.loop</string>
  <key>ProgramArguments</key>
  <array>
    <string>/usr/local/bin/gf</string>
    <string>--vault</string><string>/path/to/vault</string>
    <string>loop</string>
  </array>
  <key>StartInterval</key><integer>1800</integer>
  <key>StandardOutPath</key><string>/tmp/gf-loop.log</string>
  <key>StandardErrorPath</key><string>/tmp/gf-loop.err</string>
</dict>
</plist>
```

## Adapter boundary: cron / systemd

The framework only needs "run `gf loop` on a schedule and keep logs":

- **cron**: `*/30 * * * * /usr/local/bin/gf --vault /path/to/vault loop >> /tmp/gf-loop.log 2>&1`
- **systemd**: a `.timer` unit invoking the same command.

Full scheduler parity is not required to adopt the framework — any
scheduler that can run a command on an interval works.

## What the schedule must never do

- Never run `gf apply` unattended with a standing token. Tokens are
  issued per proposal and expire; unattended apply defeats the gate.
- Never point the loop at a vault you haven't backed up. The loop only
  *adds* files (packets, digests, review packets), but backups are still
  cheap insurance.

## Triage cadence

Triage is the cheapest stage (deterministic, no model calls by default).
Running it on every loop is fine. If you plug a cheap model into the
triage adapter, consider a slower cadence or a change-triggered run to
control cost.
