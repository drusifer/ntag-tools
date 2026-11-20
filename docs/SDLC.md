# SDLC — ntag-tools

**Repository**: ntag-tools (`git@github.com:drusifer/ntag-tools.git`)
**Owner**: Tank
**Last Verified**: 2026-11-20 (Sprint 2 close: `make test-all`, `make lint`, `make check-versions`, `make dist` pass at 0.4.0)

## 1. Topology
- `shared/` — `UID`, `TagKeys`, `mask_key` (no dependencies).
- `ntag_keys/` — tag key model and key stores: memory, CSV (default), k3s (extra `k3s`).
- `tag_validator_service/` — HTTP validator (CMAC engine); image published to the pi-patch Forgejo.
- `sdm_provisioner/` — NFC provisioner + TUI; writes keys straight into a key store.
- `tests/e2e/` — provision → publish → validate.
One product, one version: `VERSION` + `CHANGELOG.md`; `make check-versions` enforces it.
Coins, heads/tails and game logic are NOT here; they live in GlobalHeadsOrTails (`game_server`).

## 2. Tooling
Python 3.11+, workspace `.venv` (`make venv`). `pyscard` needs system PC/SC headers and is installed separately; tests use the mock HAL. **`make` is the only entry point**: `make help`, `make test-all`, `make lint`, `make dist`, `make check-versions`, `make export-tag-validator-image`, `make deploy-forgejo`.

## 3. Change management
- Work on `main` or a feature branch; TDD; each phase passes UAT (Trin) and review (Morpheus).
- Commit only when tests and lint pass. No keys, `.env` or real key CSVs in git.
- Sprint close: Tank `*devops sdlc-check`, Oracle groom, Smith acceptance.

## 4. Key custody rules
- Key material never leaves the key store over HTTP, in any mode (Sprint 2, ADR 16). The validator has no route that returns a key and `TagSecret.to_dict` cannot include one; keys are shown only as one-way fingerprints. `tests/test_no_key_egress.py` sweeps every route in both modes and must stay green. New routes or response fields need an entry in that sweep.
- `TAG_VALIDATOR_MODE=validate` additionally removes the routes that write keys in.
- The provisioner writes keys with the same store code the validator reads with.
- k3s Secrets: `tag-key-<uid>` (keys) and `tag-ctr-<uid>` (counters); validator credential may be read-only.
