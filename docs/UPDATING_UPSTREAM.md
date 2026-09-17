# Updating upstream dependencies

1. Edit `dependencies/upstream-public.repos` as a coordinated compatible set.
2. Run `make lock-dependencies` in the core Docker image.
3. Review every exact SHA in `dependencies/locks/v1.lock.repos`.
4. Update `dependencies/UPSTREAM_BASELINE.md` with provenance and compatibility
   notes.
5. Rebuild both images and run CPU plus GPU smoke tests.

Docker consumes only the immutable exact-SHA lock. Never put a branch name in a
lock file or import split Hydra-ROS alongside the pinned Hydra monorepo.
