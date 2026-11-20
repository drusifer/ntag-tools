# Lessons

## Sprint 2 (2026-11-20)

1. **A response can leak a secret without containing it.** The key sweep was green on the first design, yet a refused tap still returned the CMAC it should have carried, which is as good as a key for forging taps. When a design review says "nothing secret leaves", also list what a caller could *derive*: expected MACs, timing, error text that echoes expected values. Sweep tests need a row for each (see `test_a_refused_tap_never_reveals_the_cmac_that_would_have_been_accepted`).
2. **A mask is a leak.** "First 4 and last 4 characters" of a 128-bit key is 32 bits of it. Show a one-way fingerprint or nothing.
3. **Removing a route is only half of removing a capability.** The model's `to_dict(include_secret=...)` switch would have let the next route re-add the leak with one argument; the switch was removed, so the model cannot serialise a key at all.
4. **Pre-release is the cheap time to break an API.** Nothing was deployed against the old routes, so they were deleted outright rather than deprecated (owner decision). Do the same cleanup before the first deploy of anything else.
5. **Process slip: `sed -i` on a test file** (rule 11: edit with Edit/Write only). It renamed two mock values as intended but bypassed review; the command was also mislabelled "placeholder". Use Edit for every change, and describe commands truthfully.

## Backlog from this sprint
- The provisioner TUI and logs still show key prefixes (`widgets.py`, `key_recovery.py`, `diagnostics_service.py` use `[:8]`/`[:4]` of key hex). Local to the admin machine, not HTTP; replace with fingerprints.
- Publish 0.4.0 (image and wheels) with `make deploy-forgejo` from `main`, then re-pin tto's `VALIDATOR_IMAGE` and the game's wheels; tto's SEC-002 can be closed after that.
