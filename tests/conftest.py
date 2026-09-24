from pathlib import Path
import sys

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts" / "python"
sys.path.insert(0, str(SCRIPTS))
PREPROCESSING_PACKAGE = (
    Path(__file__).resolve().parents[1] / "src" / "spark_3dsg_preprocessing"
)
sys.path.insert(0, str(PREPROCESSING_PACKAGE))


def fixture_config(name, kind="sources"):
    return Path(__file__).resolve().parent / "fixtures" / "preprocessing" / kind / f"{name}.yaml"
