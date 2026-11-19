# Changelog

One version for the whole product (see `VERSION`); `make check-versions` keeps every package in step.

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
