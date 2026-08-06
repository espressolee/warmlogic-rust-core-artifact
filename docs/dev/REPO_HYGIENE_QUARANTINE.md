# Repository Hygiene (Non-Destructive)

Goal: keep the working tree clean without deleting uncertain files.

## Principles

- Never hard-delete as a first step.
- Quarantine high-confidence noise first.
- Keep a manifest for full restore.
- Use local excludes for machine-generated bulk paths.

## Quarantine Commands

Dry run:

```bash
bash scripts/ops/quarantine_untracked_noise.sh --dry-run
```

Apply quarantine:

```bash
bash scripts/ops/quarantine_untracked_noise.sh --apply
```

Quarantined files are moved under:

```text
.repo_hygiene/quarantine/<timestamp>/
```

Manifest is written to:

```text
.repo_hygiene/manifests/<timestamp>.tsv
```

## Restore Commands

Dry run restore:

```bash
bash scripts/ops/restore_quarantine.sh --manifest .repo_hygiene/manifests/<timestamp>.tsv --dry-run
```

Apply restore:

```bash
bash scripts/ops/restore_quarantine.sh --manifest .repo_hygiene/manifests/<timestamp>.tsv --apply
```

## Current Safe Rules

- `.lake/**` artifacts
- `rust_core/target 2/**` artifacts
- numbered duplicates where base file exists, e.g. `file 2.py` with `file.py`
- clear runtime/build artifacts:
  - `*.bak`
  - `docs/papers/**/paper.(aux|log|out|pdf)`
  - `src/cockpit.log`
  - `ultimate_benchmark_*.log`
  - `src/warm_logic/_warm_logic_rs*.so`
  - `data/redb_social/**`, `data/redb_social_db/**`, `data/social.db`
- evidence snapshots with retained latest pointers:
  - `docs/papers/**/evidence/*.YYYYMMDDTHHMMSSZ.(json|md|log)`
  - only when matching `*.latest.<ext>` exists
- explicit local/runtime leftovers:
  - `docs/papers/**/evidence/**/*.log`
  - `docs/papers/10_post_quantum_sovereignty/cross_host_hosts.json`
  - `state/kernel/state.json`
  - `test_list.txt`

## Local Ignore Hygiene

Use `.git/info/exclude` for local-only suppression of high-volume generated paths
that should not be committed accidentally.
