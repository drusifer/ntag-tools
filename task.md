# Sprint 2 Task Board: No key leaves the validator over HTTP

*   **Goal**: Remove `generate` and `?raw=true`; the validator returns metadata only, in every mode.
*   **Tier**: Tier 2
*   **Branch**: `main` (ntag-tools, GlobalHeadsOrTails)
*   **Status**: COMPLETE (2026-11-20); publishing and the tto re-pin wait for the owner

Stories and architecture: `docs/sprints/SPRINT2_KEY_EGRESS.md`.

---

## Stage 0: SDLC Gate
- [x] **Task 0.1:** `docs/SDLC.md` exists. (*Owner: Mouse | Verification: `test -f docs/SDLC.md`*)

## Phase 1: Tests that fail on the old code (Owner: Neo; L2)
- [x] **Task 1.1:** Sweep test: no route returns K0/K1/K3, default and validate mode. (*Verification: failed before, `make test-tag-validator`*)
- [x] **Task 1.2:** Update existing tests that expect `generate` or `raw` keys to expect 404 and metadata only. (*Verification: `make test-tag-validator`*)

## Phase 2: Remove the egress (Owner: Neo; L2)
- [x] **Task 2.1:** `ntag_keys` `to_dict`, validator app and client. (*Verification: `make test-all`*)
- [x] **Task 2.2:** README, `docs/DECISIONS.md` ADR 16, SDLC key custody rule. (*Verification: read-through*)
- [x] **Task 2.3:** Switch security review found SEC-003 (validate response echoed the expected CMAC); fixed with a failing test first. Trin UAT: `make test-all` and `make lint` pass.

## Phase 3: Game and scripts (Owner: Neo; L1)
- [x] **Task 3.1:** Remove `generate_random_keys` and cache from the game's `ServiceKeyManager`; game stops relaying `cmac_calculated`; reads `k3_fingerprint`; delete `scripts/update_keys_to_active.py`; docs lines. (*Verification: `make test-game-server` passes, 187 tests*)
- [x] **Task 3.2:** UAT + review.

## Phase 4: Version (Owner: Tank; L1)
- [x] **Task 4.1:** Bump to 0.4.0 in `VERSION` and every package, `CHANGELOG.md`. (*Verification: `make check-versions && make dist` pass*)

## Close
- [x] Tank `*devops sdlc-check` (SDLC stamp updated); Oracle groom (DECISIONS 16, LESSONS, proposal status); Smith acceptance (each AC checked against the tests); retro (`docs/LESSONS.md`); Cypher launch. Publishing and the tto re-pin wait for the owner.
