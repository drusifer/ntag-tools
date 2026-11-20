# Changelog

One version for the whole product (see `VERSION`); `make check-versions` keeps every package in step.

## 0.4.0 (breaking: validator API)
- **No key leaves the validator over HTTP, in any mode** (decision 16; closes tto SEC-002). Removed: `POST /api/v1/keys/generate`, `?raw=true` on `GET /keys` and `GET /keys/<uid>` (ignored if sent), the client's `generate_key` and the `raw` argument of `get_key` and `list_keys` (`list_keys(details=True)` returns metadata). `TagSecret.to_dict` has no `include_secret`.
- Key fields in API responses: `k0_masked`/`k1_masked`/`k3_masked` (first and last four hex characters of the key) are replaced by `k0_fingerprint`/`k1_fingerprint`/`k3_fingerprint` (first 8 hex characters of SHA-256 of the key bytes). `TagSecret.masked_k*()` become `fingerprint_k*()`.
- **SEC-003 fixed**: validate responses no longer include `cmac_calculated`. A refused tap used to return the CMAC it should have carried, so anyone who could reach the port could forge a tap without a key.
- New `tests/test_no_key_egress.py` sweeps every route in both modes.
- Game (GlobalHeadsOrTails): `ServiceKeyManager` no longer generates or reads keys; `scripts/update_keys_to_active.py` removed.

## 0.3.1
- `ProvisioningService.provision()` (one-shot) now runs `provision_keys()` then `provision_url()`; it used to crash on an `SDMUrlTemplate` mismatch and on a missing key-manager method. About 200 duplicate lines removed.
- Simulator: ChangeKey uses the session command counter, so the second key changed in a session (key 3) is no longer garbled.
- `make dist` builds reproducible wheels only (`SOURCE_DATE_EPOCH` from the commit); no sdists.

## 0.3.0
- Repo created from GlobalHeadsOrTails: `tag_validator_service`, `sdm_provisioner`, `shared` (fresh history).
- `ntag_keys`: key model and stores (CSV default, memory, k3s extra); CSV store shares safely between processes.
- Validator: `TAG_VALIDATOR_MODE=validate` removes every key route; `/healthz` lists `validate-only`; uses `ntag_keys`; `csv` backend added.
- Provisioner: `StoreKeyManager` saves keys straight into the key store (`NTAG_KEY_STORE`); no coin/outcome code; key values no longer logged; real hardware requires a persistent store.
- `shared`: `Outcome` and `TagKeys.outcome/coin_name` removed (coins belong to the game).
- End-to-end test: provision -> publish -> validate.
- Known at the time (fixed in 0.3.1): one-shot `provision()` crashed; simulator garbled key 3.
