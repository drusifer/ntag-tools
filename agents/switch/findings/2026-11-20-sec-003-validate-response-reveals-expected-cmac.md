# SEC-003: a refused tap's response contained the CMAC the tap should have carried

- **Severity:** High: anyone who can reach the validator's port could mint a valid tap for any tag and counter without ever seeing a key.
- **Status:** Fixed in Sprint 2 (0.4.0).
- **Verdict:** Blocked until fixed; clear after the fix and the new test.
- **Date / author:** 2026-11-20 / Switch (found while reviewing the key-egress removal; the key sweep could not catch it because the value is a CMAC, not a key)
- **Affected:** `tag_validator_service/src/tag_validator/api/app.py` `_execute_validation` and `models.py` `ValidationResult` (field `cmac_calculated`, returned on valid and refused taps alike, in default and validate modes, GET and POST)
- **Class / reference:** CWE-203 observable discrepancy / oracle; CWE-200 exposure of sensitive information

## Next Action

| Who | Does what | By / trigger |
|---|---|---|
| Neo | Done: `cmac_calculated` removed from every validate response and from `ValidationResult` | Sprint 2 |
| Trin | Done: `test_a_refused_tap_never_reveals_the_cmac_that_would_have_been_accepted` (both modes, POST, POST with `consume`, GET) failed before the fix and passes now | Sprint 2 |
| Cypher | Tell tto and the game that `cmac_calculated` is gone (tto's client never read it; the game's `ServiceKeyManager` passes it through as `None`) | With the 0.4.0 release note |

## Evidence

- **Reproduce:** `POST /api/v1/validate {"uid": U, "counter": 9, "cmac": "0000000000000000"}` returned `valid: false` and `cmac_calculated: <the correct CMAC for U and counter 9>`. Resending that value as `cmac` with `consume: true` is then accepted as a genuine tap. No key and no tag needed, only network reach to the port (tto's loopback sidecar, or the game's validator on the LAN).
- **Observed:** the test above failed on both modes before the change (the correct CMAC appeared in the body).
- **Confidence:** High (reproduced in a test).

## Impact and Reachability

It undoes what removing the key routes was for: with the oracle, reaching the port is as good as holding the keys for opening gates, except the attacker cannot reuse an already consumed counter. Any counter above the last consumed one works, so one request mints a tap that opens the gate. The same reach earlier gave the keys themselves (SEC-002); both are closed together.

## Options

1. Remove the field (chosen): no caller needs it. The provisioner computes its own expected CMAC locally from the key store; the HTTP API never needed to show it.
2. Return it only when a debug flag is set: a flag reachable by the same caller is no protection.
