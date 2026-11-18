# Changelog

One version for the whole product (see `VERSION`); `make check-versions` keeps every package in step.

## 0.3.0 (unreleased)
- Repo created from GlobalHeadsOrTails: `tag_validator_service`, `sdm_provisioner`, `shared` (fresh history).
- `ntag_keys`: key model and stores (CSV default, memory, k3s extra); CSV store shares safely between processes.
- Validator: `TAG_VALIDATOR_MODE=validate` removes every key route; `/healthz` lists `validate-only`; uses `ntag_keys`; `csv` backend added.
- Provisioner: `StoreKeyManager` saves keys straight into the key store (`NTAG_KEY_STORE`); no coin/outcome code; key values no longer logged; real hardware requires a persistent store.
- `shared`: `Outcome` and `TagKeys.outcome/coin_name` removed (coins belong to the game).
- End-to-end test: provision -> publish -> validate.
- Known: `ProvisioningService.provision()` (one-shot) is broken by an `SDMUrlTemplate` signature mismatch carried over from the old repo; the two-phase `provision_keys()` + `provision_url()` works. The simulator reproduces key 3 incorrectly after the first ChangeKey.
