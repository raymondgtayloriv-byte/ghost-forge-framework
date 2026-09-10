"""Build the Harborlight worked example by running the real pipeline.

Everything under docs/worked-example/artifacts/ is produced by the
shipped `gf` CLI against synthetic Harborlight data — no hand-written
outputs. Re-run this script to regenerate.
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

BUILD = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BUILD))
DEMO = Path("/tmp/hf-demo")
OUT = BUILD / "docs" / "worked-example" / "artifacts"
SECRET = os.environ.get("GHOST_FORGE_PROMOTION_SECRET")
if not SECRET:
    raise SystemExit("set GHOST_FORGE_PROMOTION_SECRET to a demo value before regenerating")

env = dict(os.environ, GHOST_FORGE_PROMOTION_SECRET=SECRET,
           PYTHONPATH=str(BUILD))

def gf(*args):
    r = subprocess.run([sys.executable, "-m", "ghostforge", "--vault", str(DEMO), *args],
                       capture_output=True, text=True, env=env, cwd=BUILD)
    print("$ gf", *args)
    print(r.stdout.strip())
    if r.returncode != 0:
        print(r.stderr.strip(), file=sys.stderr)
        raise SystemExit(1)
    return r.stdout.strip()

if DEMO.exists():
    shutil.rmtree(DEMO)
if OUT.exists():
    shutil.rmtree(OUT)
OUT.mkdir(parents=True)

# 1. init
gf("init")

# 2. raw capture: beacon observation
gf("capture", "--project", "harborlight", "--title", "Beacon latency observation",
   "--body", "Relay beacon p99 latency measured at 840ms during the synthetic load run. "
              "Suspected cause: retry storms on the north relay. Needs validation before it becomes a claim.")

# 3. raw capture: dubious rumor (will go down the quarantine branch)
gf("capture", "--project", "harborlight", "--title", "Rumor: north relay hardware fault",
   "--body", "Unverified hallway rumor that the north relay has a hardware fault. No evidence. Do not treat as fact.")

# 4. a note that *claims* canonical status without promotion -> exception queue
cheat = DEMO / "010 Inbox" / "Raw Captures" / f"{__import__('datetime').date.today()} - fake-canonical.md"
cheat.write_text("---\ntitle: Fake canonical claim\nproject: harborlight\ncanonical_truth: true\n---\n"
                 "This note claims to be canonical without going through promotion.\n")

# 5. valid agent update: the beacon retry policy
from ghostforge.intake import REQUIRED_SECTIONS
date = __import__("datetime").date.today().isoformat()
body = "".join(f"## {s}\n{'Beacon retries are capped at three attempts with exponential backoff (1s/2s/4s).' if s=='Summary' else 'Validated the retry cap against the relay simulator.' if s=='Work completed' else 'Simulator run passed: 3 attempts, backoff 1s/2s/4s.' if s=='Validation' else 'Simulator is synthetic; production behavior unverified.' if s=='Truth / risk notes' else 'Harborlight relay policy only.' if s=='Scope' else 'Record the agreed Harborlight beacon retry policy.' if s=='Intent' else 'None.'}\n\n" for s in REQUIRED_SECTIONS)
fm = (f"---\naction_id: GF-HL-0001\nproject: harborlight\nlane: harborlight\nstatus: complete\n"
      f"intent: Record the agreed Harborlight beacon retry policy.\nagent: harborlight-relay\nmodel: Demo Model\n"
      f"effort: low\ninterface: cli\ndate: {date}\neffective_timestamp: {date}T12:00:00+00:00\nsensitive: false\n---\n")
draft = Path(f"/tmp/{date} 1200 - harborlight - harborlight - harborlight-relay.md")
draft.write_text(fm + body + f"**Signed, Demo Model — low — cli — {date}**\n")
gf("intake-update", "--file", str(draft))

# 6. the non-canonical loop
gf("loop")

# 7. inspect the slate, pick candidates
slate = (DEMO / "010 Inbox" / "Review Packets" / "_slate.md").read_text()
print(slate)
review_dir = DEMO / "010 Inbox" / "Review Packets"
cands = {}
for rp in review_dir.glob("*.md"):
    if rp.name == "_slate.md":
        continue
    import yaml
    m = rp.read_text()
    d = yaml.safe_load(m.split("---")[1])
    cands[d.get("source_class", "?") + "|" + d.get("title", rp.stem)[:40]] = d["candidate_id"]
print("candidates:", cands)
beacon_cid = next(v for k, v in cands.items() if "agreed-harborlight-beacon-retry-policy" in v)
rumor_cid = next(v for k, v in cands.items() if "rumor-north-relay-hardware-fault" in v)

# 8. decide: promote the beacon policy
out = gf("decide", "--candidate", beacon_cid)
dpath = DEMO / out.split("decision scaffold: ", 1)[1].splitlines()[0].strip()
d = json.loads(dpath.read_text())
d.update(action="promote",
         title="Harborlight beacon retry policy",
         body="Beacon retries are capped at three attempts with exponential backoff (1s/2s/4s). Validated in the relay simulator.",
         rationale="Contract-valid signed agent update; source hash verified; simulator evidence attached.")
dpath.write_text(json.dumps(d, indent=2))
out = gf("propose", "--decision", str(dpath))
token = [l for l in out.splitlines() if l.startswith("APPROVAL TOKEN")][0].split(": ", 1)[1]
ppath = DEMO / "00_System" / "Proposals" / f"PROP-{d['decision_id']}" / "proposal.json"
gf("apply", "--proposal", str(ppath), "--token", token)

# 9. decide: quarantine the rumor
out = gf("decide", "--candidate", rumor_cid)
dpath2 = DEMO / out.split("decision scaffold: ", 1)[1].splitlines()[0].strip()
d2 = json.loads(dpath2.read_text())
d2.update(action="quarantine", title="Rumor: north relay hardware fault",
          body="n/a", rationale="Unverified rumor; no evidence. Quarantined, not deleted.")
dpath2.write_text(json.dumps(d2, indent=2))
out2 = gf("propose", "--decision", str(dpath2))
token2 = [l for l in out2.splitlines() if l.startswith("APPROVAL TOKEN")][0].split(": ", 1)[1]
ppath2 = DEMO / "00_System" / "Proposals" / f"PROP-{d2['decision_id']}" / "proposal.json"
gf("apply", "--proposal", str(ppath2), "--token", token2)

gf("status")

# 10. collect artifacts for the doc
def snap(src: Path, dest_name: str):
    dest = OUT / dest_name
    if src.is_dir():
        shutil.copytree(src, dest)
    else:
        shutil.copy2(src, dest)

packets = sorted((DEMO / "00_System" / "Packets").iterdir())
snap(packets[0] / "packet.md", "03-steward-packet.md")
snap(DEMO / "010 Inbox" / "02_Digests", "02-triage-digest")
snap(DEMO / "010 Inbox" / "Review Packets" / "_slate.md", "04-approval-slate.md")
snap(DEMO / "010 Inbox" / "Review Packets" / f"{beacon_cid}.md", "05-review-packet-beacon.md")
exc = list((DEMO / "010 Inbox" / "Exception Queue").glob("*.md"))
snap(exc[0], "06-exception-fake-canonical.md")
snap(dpath, "07-decision-promote.json")
snap(ppath.parent / "proposal.md", "08-proposal-beacon.md")
notes = list((DEMO / "030 Projects" / "harborlight" / "Notes").glob("*.md"))
snap(notes[0], "09-canonical-note.md")
q = list((DEMO / "070 Archive" / "Quarantine").glob("*.md"))
snap(q[0], "10-quarantine-rumor.md")
snap(draft, "01-agent-update-beacon.md")
caps = sorted((DEMO / "010 Inbox" / "Raw Captures").glob("*beacon-latency*"))
# raw capture for beacon was consumed? no — only rumor source was quarantined (moved).
print("artifacts:", sorted(p.name for p in OUT.iterdir()))
