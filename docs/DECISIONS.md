# Decisions

Earlier decisions (1-14) live in GlobalHeadsOrTails `docs/DECISIONS.md`.

## 15. Key Custody: keys never leave the key store; tag tools move to `ntag-tools`; coins stay in the game (amends 13)
- **Context**: `tag_validator_service` returned tag secrets over unauthenticated HTTP (`?raw=true`, `POST /keys/generate`), flagged by tto's SEC-002. The validator and provisioner were also developed beside the game although they know nothing about coins.
- **Decision**:
  1. **New repo `ntag-tools`** (`git@github.com:drusifer/ntag-tools.git`, fresh history) holds `tag_validator_service`, `sdm_provisioner`, `shared` and the new `ntag_keys`; one `VERSION` (0.3.0) and `CHANGELOG.md`; `make check-versions` enforces it. This repo keeps `game_server` and consumes the `shared`, `ntag-keys` and `tag-validator-service` wheels (`make venv`, `make vendor-ntag-wheels`).
  2. **`ntag_keys`**: `TagSecret`, the key store contract (incl. counters), memory, **CSV (default)** and k3s stores (extra `ntag-keys[k3s]`). The CSV store has tag columns only (`uid,k0,k1,k3,status,created_at,deleted_at`), shares safely between processes (lock + atomic rename), and counters live in a sibling file.
  3. **Provisioner writes keys straight into the store** (`StoreKeyManager`, `NTAG_KEY_STORE=csv|k3s`); it generates keys with the CSPRNG, saves them before touching the tag, resumes by reading the store, and never logs key values. Real hardware requires a persistent store (CSV or k3s), never memory; this replaces the old rule that forbade CSV.
  4. **Validate-only mode**: `TAG_VALIDATOR_MODE=validate` removes every key route (404) and adds `validate-only` to `/healthz` `features`; an unrecognised value stops startup.
  5. **Coins are a game concept**: a coin is one heads tag and one tails tag, not interchangeable. Tag tools carry no coin, side or `Outcome`. The game's registry (`coins` table) enforces one tag per side per coin, refuses moving a tag onto another coin, reports unassigned tags as unassigned, and imports coin data from a legacy key CSV at startup.
- **Not done (backlog)**: removing `?raw=true` and key-returning `generate` (proposal part 4; `game_server/service_key_manager.py` and `scripts/update_keys_to_active.py` still use them); game validator stays in default mode; pruning `tag-ctr-*` Secrets; publishing the wheels to the Forgejo PyPI.
- **Status**: Accepted, 2026-11-17. `ntag-tools`: 4 + 19 + 69 + 167 + 9 tests; `game_server`: 186 tests.
