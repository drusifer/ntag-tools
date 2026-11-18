# ntag-tools

Tools for NTAG 424 DNA tags, built as one product with one version (see `VERSION`, `CHANGELOG.md`):

| Package | What it is |
|---|---|
| `shared` | `UID`, `TagKeys`, `mask_key` |
| `ntag_keys` | Tag key model and key stores: **CSV (default)**, memory, k3s (`pip install ntag-keys[k3s]`) |
| `tag_validator_service` | HTTP service that checks SDM taps (CMAC + replay counter); `TAG_VALIDATOR_MODE=validate` removes every key route |
| `sdm_provisioner` | NFC provisioner + Textual TUI; writes a tag's keys straight into a key store |

Coins, heads/tails and the game live in GlobalHeadsOrTails, not here. These tools know tags only.

## Key custody
The provisioner generates keys and saves them in the key store before touching the tag; the validator reads the same store. Choose it with `NTAG_KEY_STORE=csv|k3s` (provisioner; `NTAG_KEY_CSV`, `NTAG_K3S_NAMESPACE`) and `SECRET_STORE_BACKEND=csv|memory|k3s` (validator; `TAG_KEYS_CSV`, `TAG_SECRETS_NAMESPACE`). Keys are write-once; key values are never logged. Real hardware needs a persistent store (CSV or k3s).

## Develop
`make help`. `make venv` once, then `make test-all`, `make lint`, `make check-versions`, `make dist` (wheels in `dist/`), `make export-tag-validator-image`, `make deploy-forgejo`.
The provisioner's tests use the mock HAL; `tools/pcsc_stub` stands in for `pyscard` when it is not installed.
Design notes: `docs/PROPOSAL_KEY_CUSTODY.md`, `docs/DECISIONS.md`, `docs/SDLC.md`.
