# Sprint 2: no key leaves the validator over HTTP, in any mode

Tier 2 (stories and architecture in one document). Date: 2026-11-20. Closes part 4 of `docs/PROPOSAL_KEY_CUSTODY.md` and tto's SEC-002.

## Story

As the owner of tto (and of the game), I want the tag validator to have no HTTP route that returns a key, in any mode, so a reader of its port can never get K0, K1 or K3, and so the validator can be deployed without a mode switch to be safe.

Owner decision (2026-11-20): nothing has been deployed against the old routes (tto is not deployed; the game's validator is a single owner-run instance), so the routes are removed outright. No deprecation period, no compatibility flag.

### Acceptance criteria
1. `POST /api/v1/keys/generate` is not served in any mode (404 in validate mode, 405 in default mode, where the path is no longer a route). The handler, the client method `generate_key` and the README entry are gone.
2. `GET /api/v1/keys/<uid>` and `GET /api/v1/keys` return metadata only (uid, secret name, status, timestamps, key fingerprints). A `raw=true` query changes nothing.
3. `TagSecret.to_dict` has no way to include key values (the `include_secret` parameter is removed). The old `k0_masked`/`k1_masked`/`k3_masked` fields showed the first and last four hex characters of each key (32 of 128 bits). They are replaced by `k0_fingerprint`, `k1_fingerprint`, `k3_fingerprint`: the first 8 hex characters of SHA-256 of the key bytes, enough to tell keys apart, no key characters. `masked_k*()` become `fingerprint_k*()` (the importer's dry-run log uses them).
4. The client's `get_key` and `list_keys` lose their `raw` parameter.
4a. **SEC-003 (found in the design review):** no validate response contains the CMAC the tap should have carried (`cmac_calculated` is removed). Before this, a refused tap told the caller the correct CMAC, so reaching the port was enough to forge a tap. See `agents/switch/findings/2026-11-20-sec-003-validate-response-reveals-expected-cmac.md`.
5. A sweep test stores a known key, calls every route the app has (every method, with and without `raw=true`), in default mode and validate mode, and asserts that no response body or header contains any of K0, K1, K3 as hex (either case). It fails on the old code.
6. The game's `ServiceKeyManager` loses `generate_random_keys` and the in-memory key cache that fed `get_key`; `scripts/update_keys_to_active.py` is deleted (it needs raw keys to work, and the provisioner now sets status itself).
7. Validate-only mode keeps working as before (its tests still pass, with the `raw` and `generate` rows now expecting 404 in both modes).
8. Versions: 0.4.0 (a breaking API change), `CHANGELOG.md`, `make check-versions` passes. Docs updated: SDLC key custody rule, ADR 16, README, proposal status, `docs/sprints` index, tto handoff notes.

### Out of scope
- Publishing the 0.4.0 image and wheels, and re-pinning tto's `VALIDATOR_IMAGE` (owner-triggered, after this sprint).
- Key-write routes `POST /keys`, `POST /keys/import-csv`, `DELETE`, `undelete`: they take keys in and never return one. Validate mode still turns them off. They stay for the game's validator and for tto's image tests.
- Pruning `tag-ctr-*` Secrets; publishing wheels to the Forgejo PyPI.

## Architecture

| Piece | Change |
|---|---|
| `ntag_keys.TagSecret.to_dict` | no `include_secret`; always masked. Key values stay reachable only through the attributes `k0`, `k1`, `k3`, for the store code. |
| `tag_validator.api.app` | delete `/keys/generate` route and `_handle_generate_key`; `_handle_get_key` and `_handle_list_keys` ignore `raw`; `details` stays (it only adds metadata). |
| `tag_validator.client` | delete `generate_key`; remove `raw` from `get_key` and `list_keys`. |
| `game_server.service_key_manager` | delete `generate_random_keys`, `_cached_keys`; `get_key` no longer reads a cache (it already returns zeros for unknown keys; check callers). |
| `scripts/update_keys_to_active.py` | delete. |

Failure behaviour: a caller still sending `raw=true` gets metadata (not an error), so a stale client cannot be tricked into believing it received keys; a caller of `generate` gets 404.

Threat model (Switch, design gate): the asset is the key; the entry point is the validator's port; with this change the port has no response that contains a key in any mode. Remaining paths to a key: the validator's own credential (k3s token, CSV file) and the provisioner machine. Both are outside the HTTP surface and were accepted earlier (SEC-002).

## Verification
`make test-all`, `make lint`, `make check-versions`, `make dist`, plus the game's `make test-game-server` in GlobalHeadsOrTails.
