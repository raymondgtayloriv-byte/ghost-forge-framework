# Config

`ghostforge.json` holds non-secret framework configuration:

- `canonical_targets`: directories the promotion engine may write to.
  Anything else is refused at apply time.
- `promotion.secret_env`: name of the environment variable holding the
  approval-token secret. **The secret itself is never stored here, in the
  vault, or in the repo.** Export it in your shell profile or secret manager:
  `export GHOST_FORGE_PROMOTION_SECRET="$(openssl rand -hex 32)"`
- `autonomous`: the experimental lane. `enabled: false` and `dry_run: true`
  by default. Enable explicitly if you want it.

Keep a backup of your secret outside the vault. If you lose it, old tokens
stop verifying (they expire anyway) and you issue a new secret.
