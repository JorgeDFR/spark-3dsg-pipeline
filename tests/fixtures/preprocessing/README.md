# Preprocessing integration tests

These fixtures are test inputs, not camera acquisition examples. Sources and
OpenVINS calibration profiles here are passed by explicit path. They are not
installed as package source profiles.

## Validate the preprocessing toolbox

From the repository root, after configuring `.env` as described in the repository README:

```bash
make build-preprocess
```

```bash
make test-preprocess
```

`test-preprocess` downloads the public fixtures, converts ROS 1 bags to ROS 2,
runs **all 11 cases**, and checks their normalized outputs. This includes both
OpenVINS modes. Independent cases continue after a failure. Any failed or
skipped case makes the command exit nonzero. OpenVINS is still experimental:
including it in the suite does not establish trajectory accuracy.

| Case | Pose provider | Depth operation |
| --- | --- | --- |
| `zed2_lake_zed_tracking` | ZED SDK GEN_1 visual-only tracking | SDK registered depth |
| `zed2_lake_rtabmap` | RTAB-Map on ZED SVO replay. SDK tracking disabled | SDK registered depth |
| `uosm_zed2i_zed_tracking` | ZED SDK tracking, also checks IMU output | SDK registered depth |
| `d435i_recorded_odometry` | Recorded odometry topic → TF | Already aligned left IR/depth |
| `d435i_passthrough` | Existing TF from the recorded-odometry case | Already aligned |
| `d435i_rtabmap` | RTAB-Map RGB-D odometry | Already aligned left IR/depth |
| `d435i_register_recorded_odometry` | Recorded odometry topic → TF | Offline projection into right IR |
| `d435i_register_rtabmap` | RTAB-Map RGB-D odometry | ROS `depth_image_proc` into right IR |
| `d435i_openvins_mono` | OpenVINS mono + IMU | Already aligned left IR/depth |
| `d435i_openvins_stereo` | OpenVINS stereo + IMU | Already aligned left IR/depth |
| `tum_rtabmap` | RTAB-Map RGB-D odometry | Already registered RGB-D |

The older Lake SVO does not supply the high-frequency IMU data required by the
SDK's default tracker in these runs. Both Lake cases use the dedicated
`validation_zed2_lake` source with `zed.legacy_svo: true`. Its wrapper overrides
select `GEN_1`, disable IMU fusion and gravity initialization, and use
image-synchronized sensor reads without IMU publication. This is a visual-only
tracking test. The UoSM SVO2 case retains default SDK tracking and validates IMU
output. Generic `zed2_svo` and `zed2i_svo` profiles retain their defaults.

When another estimator such as RTAB-Map supplies pose, preprocessing disables
ZED's internal positional tracking **and** depth stabilization. The pinned
wrapper would otherwise activate tracking for stabilization even with TF
publication disabled. These settings use its supported `param_overrides`
launch argument. No upstream source is patched.

The registration cases reuse the D435i recording without another download.
Its right infrared camera provides a different optical viewpoint from native
depth, so these cases actually enable `depth.mode: register`. Infrared serves
as the image stream for these integration tests. It is not a color-semantic
mapping benchmark. The matrix covers each supplied pose profile and both
registration execution paths, not every sensor/backend combination.

Each output must pass `validate_bag.py` (image/camera/TF contract) and
`validate_preprocessing_output.py` (nonempty normalized RGB-D, CameraInfo,
TF, backend-specific topics, and provenance files). These are integration checks, not trajectory-accuracy or
pixel-accuracy benchmarks. Repository unit tests also check depth projection
with a nonzero translation and competing depths.

The four downloads total about **1.25 GiB**, before conversion and outputs:
88.5 MB ZED2 Lake SVO, 109 MB UoSM ZED2i SVO2, 634 MB D435i (12.5 seconds), and
504 MB TUM Freiburg 1 xyz. URLs, expected byte lengths, and license information
are in [the dataset manifest](datasets.yaml).
Raw downloads, converted sensor bags, and generated calibration live under
`${DATA_DIR:-./data}/raw/test-preprocess/`. Converted storage format alone does
not make a bag mapping-ready.

Results live under `${DATA_DIR:-./data}/normalized/test-preprocess/`:

- `summary.json` records each selected case as passed, failed, skipped, or not run.
- `logs/<UTC-run-timestamp>/` keeps complete Docker command output for each
  dataset preparation and case, including failures before a bag is created.
  These transcripts survive `--force` and are retained across runs.
- Each successful case directory contains the normalized bag and validation report.
- Failed `.CASE.tmp-*` and `.CASE.logs-*` directories retain bags and process logs.

The console shows numbered `START` blocks, `PASS`/`FAIL` results with elapsed
seconds, and a final results table. Verbose ROS, download, and validation output
is saved in the printed log paths. To also stream it live, use
`make test-preprocess PREPROCESS_TEST_ARGS='--verbose'`. You can follow a single log
with `tail -f <printed-log-path>` while a case runs.

Existing successful outputs are revalidated, not regenerated. After changing
code, profiles, or the image, use `--force` to exercise the new preprocessing:

```bash
make test-preprocess PREPROCESS_TEST_ARGS='--force --skip-download'
```

`--force` removes only selected test outputs and their temporary/log
directories. Raw downloads remain. Omit `--skip-download` if fixtures or their
prepared calibration are missing. Preparation reuses valid cached downloads.

Useful narrower commands:

```bash
# List cases without Docker or downloads.
python3 scripts/python/run_preprocessing_tests.py --list
```

```bash
# Download/convert only. Never builds the image implicitly.
make prepare-preprocess-data
```

```bash
# Run one case (its prerequisites are included automatically).
make test-preprocess PREPROCESS_TEST_ARGS='--case d435i_passthrough'
```

```bash
# Explicitly omit experimental OpenVINS cases.
make test-preprocess PREPROCESS_TEST_ARGS='--suite stable'
```

```bash
# Stop at the first failure instead of continuing (default: --keep-going).
make test-preprocess PREPROCESS_TEST_ARGS='--fail-fast'
```


Preparation migrates cached downloads and converted inputs from the former
`raw/qualification` and `raw/validation` paths when the new destination does not exist. Existing
`normalized/qualification` and `normalized/validation` reports remain untouched. New runs write to
`normalized/test-preprocess`. Multiple conflicting caches require manual reconciliation.
