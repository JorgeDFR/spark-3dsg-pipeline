# Updating upstream

1. Review upstream release notes, branches, licenses, and ROS compatibility.
2. Update only `dependencies/adt4-public.repos`.
3. Build the existing core image and run `make lock-dependencies` to resolve exact commits.
4. Confirm every lock URL is HTTPS and every revision is a 40-character SHA.
5. Rebuild core from scratch; run lint, unit/smoke tests, then the uHumans2 test.
6. Run the manual GPU image test and Spot acceptance before merging.
7. Update `UPSTREAM_BASELINE.md` only when intentionally recapturing ADT4 architecture, not for every dependency refresh.
8. Review/update `THIRD_PARTY_NOTICES.md`.

For GPU updates, also refresh and test the direct pins in `dependencies/gpu.requirements.txt`; never let the semantic package silently clone its floating `Spark-Config` URL. The image installs the exact locked checkout first and then installs semantic inference with `--no-deps`.

Never hand-edit one SHA to “latest” in isolation. Hydra, Hydra-ROS, Khronos, and Spark-DSG APIs move together. Never merge the DAAAM lock into the standard lock.

The Docker build consumes only `dependencies/locks/adt4.lock.repos`. Repository validation rejects a floating branch in that file.
