from types import SimpleNamespace

from inspect_dsg import (
    acceptance_errors,
    edge_type_counts,
    inspection_view,
    print_human,
)


class AgentNodeAttributes:
    pass


class ObjectNodeAttributes:
    pass


class FakeGraph:
    def __init__(self):
        self._keys = {
            "OBJECTS": SimpleNamespace(layer=2, partition=0),
            "MESH_PLACES": SimpleNamespace(layer=3, partition=1),
            "PLACES": SimpleNamespace(layer=3, partition=0),
        }
        self.layer_names = self._keys
        self._nodes = {
            1: SimpleNamespace(
                layer=SimpleNamespace(layer=2, partition=0),
                attributes=ObjectNodeAttributes(),
            ),
            2: SimpleNamespace(
                layer=SimpleNamespace(layer=2, partition=0),
                attributes=ObjectNodeAttributes(),
            ),
            3: SimpleNamespace(
                layer=SimpleNamespace(layer=3, partition=0),
                attributes=object(),
            ),
            4: SimpleNamespace(
                layer=SimpleNamespace(layer=2, partition=97),
                attributes=AgentNodeAttributes(),
            ),
        }
        self.edges = [
            SimpleNamespace(source=1, target=2),
            SimpleNamespace(source=1, target=3),
            SimpleNamespace(source=3, target=2),
            SimpleNamespace(source=4, target=3),
        ]

    def get_layer_key(self, name):
        return self._keys[name]

    def get_node(self, node_id):
        return self._nodes[node_id]


class FakeLayers:
    OBJECTS = "OBJECTS"
    MESH_PLACES = "MESH_PLACES"
    PLACES = "PLACES"

    @staticmethod
    def name_to_layer_id(_name):
        return None


def valid_summary():
    return {
        "layers": {
            "OBJECTS": 2,
            "PLACES": 0,
            "MESH_PLACES": 3,
            "ROOMS": 0,
            "BUILDINGS": 0,
            "AGENTS": 1,
        },
        "object_labels": {"chair": 2},
        "mesh": {"vertices": 10, "faces": 4},
    }


def test_pipeline_output_acceptance_passes_complete_graph():
    assert acceptance_errors(valid_summary()) == []


def test_pipeline_output_acceptance_reports_every_missing_component():
    summary = valid_summary()
    summary["layers"] = {
        "OBJECTS": 0,
        "PLACES": 0,
        "MESH_PLACES": 0,
        "ROOMS": 0,
        "BUILDINGS": 0,
        "AGENTS": 0,
    }
    summary["object_labels"] = {}
    summary["mesh"] = {"vertices": 0, "faces": 0}
    assert len(acceptance_errors(summary)) == 5


def test_edge_type_counts_groups_edges_by_unordered_layer_pair():
    assert edge_type_counts(FakeGraph(), FakeLayers) == {
        "AGENTS to PLACES": 1,
        "OBJECTS to OBJECTS": 1,
        "OBJECTS to PLACES": 2,
    }


def test_print_human_displays_edge_types(capsys):
    summary = valid_summary()
    summary["graph"] = {"nodes": 6, "edges": 4}
    summary["edge_types"] = {
        "AGENTS to PLACES": 1,
        "OBJECTS to OBJECTS": 1,
        "OBJECTS to PLACES": 2,
    }
    summary["trajectory_exists"] = True

    print_human(summary)

    output = capsys.readouterr().out
    assert "Edges by type:" in output
    assert "OBJECTS to OBJECTS  1" in output
    assert "OBJECTS to PLACES   2" in output
    assert "AGENTS" not in output
    assert "Mesh:" not in output
    assert "Trajectory:" not in output
    assert "nodes: 5" in output
    assert "edges: 3" in output


def test_inspection_view_omits_agents_trajectory_and_mesh():
    summary = valid_summary()
    summary["graph"] = {"nodes": 6, "edges": 4}
    summary["edge_types"] = {
        "AGENTS to PLACES": 1,
        "OBJECTS to OBJECTS": 1,
        "OBJECTS to PLACES": 2,
    }
    summary["trajectory_exists"] = True

    visible = inspection_view(summary)

    assert visible["graph"] == {"nodes": 5, "edges": 3}
    assert visible["edge_types"] == {
        "OBJECTS to OBJECTS": 1,
        "OBJECTS to PLACES": 2,
    }
    assert "AGENTS" not in visible["layers"]
    assert "mesh" not in visible
    assert "trajectory_exists" not in visible
