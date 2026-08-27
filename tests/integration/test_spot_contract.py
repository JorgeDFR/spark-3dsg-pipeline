import os
from pathlib import Path

import pytest

from inspect_dsg import acceptance_errors, summarize


@pytest.mark.integration
def test_external_spot_output_meets_v1_contract():
    value = os.environ.get("SPOT_DSG")
    if not value:
        pytest.skip("set SPOT_DSG for the manual/self-hosted GPU integration test")
    path = Path(value)
    assert path.is_file()
    assert acceptance_errors(summarize(path)) == []
