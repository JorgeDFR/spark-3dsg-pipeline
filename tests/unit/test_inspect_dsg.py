from inspect_dsg import acceptance_errors


def valid_summary():
    return {
        "layers": {"OBJECTS": 2, "MESH_PLACES": 3, "AGENTS": 1},
        "object_labels": {"chair": 2},
        "mesh": {"vertices": 10, "faces": 4},
    }


def test_v1_acceptance_passes_complete_graph():
    assert acceptance_errors(valid_summary()) == []


def test_v1_acceptance_reports_every_missing_component():
    summary = valid_summary()
    summary["layers"] = {"OBJECTS": 0, "MESH_PLACES": 0, "AGENTS": 0}
    summary["object_labels"] = {}
    summary["mesh"] = {"vertices": 0, "faces": 0}
    assert len(acceptance_errors(summary)) == 5
