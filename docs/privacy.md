# Privacy & Security

Ghost Forge is designed for vaults that contain real work: client names,
business details, credentials-adjacent material. The framework treats
privacy as a structural property, not a checklist.

## Structural guarantees

- **Secrets never enter the vault.** The promotion secret lives in an
  environment variable (`GHOST_FORGE_PROMOTION_SECRET`). Tokens are
  HMACs, not secrets. There is no config field, note template, or code
  path that stores a credential.
- **The observer is read-only.** The steward cannot exfiltrate beyond
  writing packet files into `00_System/Packets/` — and packets contain
  hashes and frontmatter metadata, not a second copy of your vault.
- **No network.** Every module works on local files. There is no
  telemetry, no provider call, no update check.
- **Sensitive notes are quarantined from automation.** Any note with
  `sensitive` set to anything other than `false` is routed to the
  exception queue and is ineligible for autonomous promotion.
- **Append-only canonical history.** Nothing is silently overwritten, so
  a bad promotion is visible and reversible via its manifest.

## What you must still do

- **Back up your vault** before scheduling the loop. The loop only adds
  files, but backups are non-negotiable for anything you care about.
- **Protect the secret.** Anyone with the promotion secret can issue
  approval tokens. Keep it in your shell profile or secret manager, back
  it up offline, rotate it if exposed. Old tokens expire on their own.
- **Review the slate.** The pipeline shrinks what needs your eyes; it
  doesn't replace them. The approval slate is the whole point — use it.
- **Don't commit a live vault.** This repo ships a *starter* vault. Your
  working vault contains your life; keep it out of git (the starter's
  `.gitignore` pattern and the repo's own `.gitignore` both assume this).

## What's excluded from the public framework

The public repository contains no real agent updates, no customer or
business data, no credentials, no machine paths, no provider payloads,
and no historical git data. The worked example is synthetic
(Harborlight). If you adapt this framework, apply the same rule to your
public artifacts: **expose the methodology, never the memories.**
