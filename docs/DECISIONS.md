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
- **Not done (backlog)**: removing `?raw=true` and key-returning `generate` (proposal part 4; done in decision 16); game validator stays in default mode; pruning `tag-ctr-*` Secrets; publishing the wheels to the Forgejo PyPI.
- **Status**: Accepted, 2026-11-17. `ntag-tools`: 4 + 19 + 69 + 167 + 9 tests; `game_server`: 186 tests.

## 16. No key leaves the validator over HTTP, in any mode (amends 13 and 15; closes proposal part 4 and tto SEC-002)
- **Context**: Decision 13 let the provisioner read keys back over HTTP (`?raw=true`) and `generate` returned the new keys. Nothing authorised the caller. Decision 15 stopped the provisioner using those routes and added validate-only mode, but left the routes in the default mode. Nothing was deployed against them (tto not deployed; the game's validator is one owner-run instance), so no compatibility period was needed.
- **Decision**:
  1. `POST /api/v1/keys/generate` is removed (route, handler, client `generate_key`). `?raw=true` is removed from `GET /keys` and `GET /keys/<uid>` and ignored if sent; the client's `get_key` and `list_keys` lose `raw` (`list_keys` gains `details`, metadata only).
  2. `TagSecret.to_dict` has no `include_secret`; it always returns metadata. Key values stay reachable only as attributes, for the store code.
  3. The partial-key masks (`k0_masked` etc.: first and last four hex characters, 32 of 128 bits) are replaced by one-way fingerprints (`k0_fingerprint` etc.: first 8 hex characters of SHA-256 of the key bytes). `masked_k*()` become `fingerprint_k*()`.
  4. `tests/test_no_key_egress.py` sweeps every route (every method, with and without `raw=true`, both modes) with keys whose first and last 8 characters are distinctive, and fails if any response holds a whole key or either end of one.
  4a. **SEC-003**: the validate responses no longer include `cmac_calculated`. A refused tap used to return the CMAC it should have carried, so anyone who could reach the port could forge a tap with no key. `test_a_refused_tap_never_reveals_the_cmac_that_would_have_been_accepted` pins it (default and validate mode, GET and POST).
  5. The game's `ServiceKeyManager` loses `generate_random_keys` and the cache that served `get_key`; `scripts/update_keys_to_active.py` (which needed raw keys) is deleted.
- **Consequences**: validate-only mode is now a hardening of the write routes, not the only protection against reads. The paths to a key that remain are outside HTTP: the validator's own credential (k3s token or CSV file) and the provisioner machine, both accepted earlier. Local displays in the provisioner TUI still show key prefixes (backlog: remove them).
- **Status**: Accepted, 2026-11-20. Version 0.4.0 (breaking API change).
