# Working in this repository (instructions for Claude sessions)

Purpose: make common clients work with our Arrow Flight SQL server (DuckDB over Parquet on HDFS/S3/lakeFS, Iceberg
and Hive catalogs) and prove it in CI — small integrations, configs, docs and end-to-end tests, not big products.
Also: S3-compatible storage backends (Ceph RGW, AWS S3). State, backlog and decisions: `docs/STATUS.md`.

## Session routine

A recurring cloud session works here with zero context each time.

1. **Lock.** `git fetch origin`. If `docs/LOCK` holds a UTC time less than 150 minutes old, stop without changes.
   Otherwise write `date -u +%FT%TZ` to `docs/LOCK`, commit `[skip ci] lock`, push. Empty it in the last commit.
2. Work on `main` (if rejected, `claude/compat-dev`). Never force-push `main`.
3. CI via GitHub Actions; `gh api` works in the session (`gh workflow run` may not — use
   `gh api -X POST repos/<owner>/<repo>/actions/workflows/<file>/dispatches -f ref=main ...`).
4. Take the first open item of "Next steps" in `docs/STATUS.md`; finish it properly.
5. Before ending (≤ ~60 min — tokens are limited, be economical): update `docs/STATUS.md` (dated Log line with
   run ids, Next steps, Open questions), release the lock, commit, push. Nothing may stay only in the session.

## Rules

- Private repo. Release `e2e-assets` holds the maintainer's server build: never make the repo public, never copy
  the assets elsewhere.
- Actions minutes are limited (~2000/month shared): short jobs, cache images/deps, run e2e only when needed.
- Be token-economical: prefer small, finished steps; don't re-read large files needlessly; stop early when
  waiting on CI longer than ~20 min (leave it for the next session).
- No secrets/credentials in the repo; test credentials generated in the job. Cloud credentials (AWS) only via
  GitHub Actions secrets that the maintainer adds — never ask for them in files.
- A client "works" only if results equal the reference (`e2e/reference/sf1`, same normalisation: decimals rounded
  to 4 places, rows sorted unless ORDER BY) — not just "connects".
- Commit/push only to this repository. Anything needing the maintainer's decision → "Open questions".
- Docs and commit messages in English.
