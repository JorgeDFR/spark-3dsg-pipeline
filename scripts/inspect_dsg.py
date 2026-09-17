#!/usr/bin/env python3
"""Summarize a serialized Spark-DSG and optionally enforce output acceptance."""

from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path
from typing import Any


EDGE_LAYER_ORDER = (
    "SEGMENTS",
    "OBJECTS",
    "AGENTS",
    "MESH_PLACES",
    "TRAVERSABILITY",
    "PLACES",
    "ROOMS",
    "BUILDINGS",
)


def _layer_key_tuple(key: Any) -> tuple[int, int]:
    return int(key.layer), int(key.partition)


def _layer_names_by_key(graph: Any, layers: Any) -> dict[tuple[int, int], str]:
    names_by_key: dict[tuple[int, int], str] = {}
    for name in EDGE_LAYER_ORDER:
        if name == "AGENTS":
            # Agent trajectories are stored in dynamic partitions of the object
            # layer, so the default AGENTS key aliases OBJECTS.
            continue
        layer = getattr(layers, name, None)
        if layer is None:
            continue
        try:
            names_by_key.setdefault(_layer_key_tuple(graph.get_layer_key(layer)), name)
        except Exception:
            try:
                key = layers.name_to_layer_id(name)
                if key is not None:
                    names_by_key.setdefault(_layer_key_tuple(key), name)
            except Exception:
                pass

    try:
        for name, key in graph.layer_names.items():
            if name != "AGENTS":
                names_by_key.setdefault(_layer_key_tuple(key), str(name))
    except Exception:
        pass
    return names_by_key


def _edge_layer_name(
    graph: Any,
    node: Any,
    layers: Any,
    names_by_key: dict[tuple[int, int], str],
) -> str:
    if "Agent" in type(node.attributes).__name__:
        return "AGENTS"

    key = _layer_key_tuple(node.layer)
    name = names_by_key.get(key)
    if name is not None:
        return name

    # Spark-DSG stores agent trajectories in non-primary partitions of the
    # OBJECTS/AGENTS layer. This fallback also handles custom agent attributes.
    try:
        objects_key = _layer_key_tuple(graph.get_layer_key(layers.OBJECTS))
        if key[0] == objects_key[0] and key[1] != objects_key[1]:
            return "AGENTS"
    except Exception:
        pass

    return f"LAYER_{key[0]}" if key[1] == 0 else f"LAYER_{key[0]}[{key[1]}]"


def edge_type_counts(graph: Any, layers: Any) -> dict[str, int]:
    """Count graph edges by their unordered endpoint layer types."""
    names_by_key = _layer_names_by_key(graph, layers)
    rank = {name: index for index, name in enumerate(EDGE_LAYER_ORDER)}
    counts: collections.Counter[str] = collections.Counter()

    for edge in graph.edges:
        names = [
            _edge_layer_name(graph, graph.get_node(edge.source), layers, names_by_key),
            _edge_layer_name(graph, graph.get_node(edge.target), layers, names_by_key),
        ]
        names.sort(key=lambda name: (rank.get(name, len(rank)), name))
        counts[f"{names[0]} to {names[1]}"] += 1

    return dict(sorted(counts.items()))


def agent_node_count(graph: Any, layers: Any) -> int:
    names_by_key = _layer_names_by_key(graph, layers)
    return sum(
        _edge_layer_name(graph, node, layers, names_by_key) == "AGENTS"
        for node in graph.nodes
    )


def layer_count(graph: Any, layer: Any) -> int:
    try:
        return graph.get_layer(layer).num_nodes()
    except Exception:
        try:
            layer_id = graph.get_layer_key(layer).layer
            return sum(1 for node in graph.nodes if node.layer.layer == layer_id)
        except Exception:
            return 0


def ply_counts(path: Path) -> tuple[int, int]:
    vertices = faces = 0
    if not path.is_file():
        return vertices, faces
    with path.open("rb") as stream:
        for raw_line in stream:
            line = raw_line.decode("ascii", errors="replace").strip()
            if line.startswith("element vertex "):
                vertices = int(line.rsplit(" ", 1)[1])
            elif line.startswith("element face "):
                faces = int(line.rsplit(" ", 1)[1])
            elif line == "end_header":
                break
    return vertices, faces


def summarize(path: Path) -> dict[str, Any]:
    try:
        import spark_dsg as dsg
    except ImportError as error:
        raise RuntimeError("Spark-DSG Python bindings are not available; run this inside the core image") from error

    graph = dsg.DynamicSceneGraph.load(str(path))
    layers = dsg.DsgLayers
    layer_names = (
        "OBJECTS",
        "PLACES",
        "MESH_PLACES",
        "ROOMS",
        "BUILDINGS",
        "AGENTS",
    )
    layer_counts = {
        name: layer_count(graph, layer)
        if (layer := getattr(layers, name, None)) is not None
        else 0
        for name in layer_names
    }
    layer_counts["AGENTS"] = agent_node_count(graph, layers)
    objects_layer = layers.OBJECTS
    object_count = layer_counts["OBJECTS"]
    agent_count = layer_counts["AGENTS"]

    labels: collections.Counter[str] = collections.Counter()
    if object_count:
        objects = graph.get_layer(objects_layer)
        labelspace = None
        try:
            key = graph.get_layer_key(objects_layer)
            labelspace = graph.get_labelspace(key.layer, key.partition)
        except Exception:
            pass
        for node in objects.nodes:
            attributes = node.attributes
            semantic_id = getattr(attributes, "semantic_label", None)
            name = getattr(attributes, "name", "")
            if labelspace and semantic_id is not None:
                try:
                    name = labelspace.get_category(semantic_id) or name
                except Exception:
                    pass
            resolved = name or semantic_id
            labels[str(resolved if resolved is not None else "unknown")] += 1

    mesh_vertices = mesh_faces = 0
    try:
        if graph.has_mesh():
            mesh_vertices = graph.mesh.num_vertices()
            mesh_faces = graph.mesh.num_faces()
    except Exception:
        pass
    if mesh_vertices == 0:
        mesh_vertices, mesh_faces = ply_counts(path.with_name("mesh.ply"))

    return {
        "graph": {"nodes": graph.num_nodes(), "edges": graph.num_edges()},
        "edge_types": edge_type_counts(graph, layers),
        "layers": layer_counts,
        "object_labels": dict(labels.most_common()),
        "mesh": {"vertices": mesh_vertices, "faces": mesh_faces},
        "trajectory_exists": agent_count > 0,
    }


def inspection_view(summary: dict[str, Any]) -> dict[str, Any]:
    """Return the static graph fields exposed by human and JSON inspection."""
    edge_types = {
        name: count
        for name, count in summary["edge_types"].items()
        if "AGENTS" not in name.split(" to ")
    }
    layers = {
        name: count for name, count in summary["layers"].items() if name != "AGENTS"
    }
    agent_nodes = summary["layers"].get("AGENTS", 0)
    agent_edges = sum(summary["edge_types"].values()) - sum(edge_types.values())
    return {
        "graph": {
            "nodes": summary["graph"]["nodes"] - agent_nodes,
            "edges": summary["graph"]["edges"] - agent_edges,
        },
        "edge_types": edge_types,
        "layers": layers,
        "object_labels": summary["object_labels"],
    }


def print_human(summary: dict[str, Any]) -> None:
    summary = inspection_view(summary)
    print("Graph:")
    print(f"  nodes: {summary['graph']['nodes']}")
    print(f"  edges: {summary['graph']['edges']}")
    print("\nEdges by type:")
    if summary["edge_types"]:
        width = max(map(len, summary["edge_types"]))
        for edge_type, count in summary["edge_types"].items():
            print(f"  {edge_type:<{width}}  {count}")
    else:
        print("  (none)")
    print("\nLayers:")
    for name, count in summary["layers"].items():
        print(f"  {name}: {count}")
    print("\nObject labels:")
    if summary["object_labels"]:
        width = max(map(len, summary["object_labels"]))
        for label, count in summary["object_labels"].items():
            print(f"  {label:<{width}}  {count}")
    else:
        print("  (none)")


def acceptance_errors(summary: dict[str, Any]) -> list[str]:
    errors = []
    if summary["layers"]["OBJECTS"] <= 0:
        errors.append("OBJECTS must contain at least one node")
    if summary["layers"]["MESH_PLACES"] <= 0:
        errors.append("MESH_PLACES must contain at least one node")
    if summary["layers"]["AGENTS"] <= 0:
        errors.append("AGENTS/trajectory must contain at least one node")
    if summary["mesh"]["vertices"] <= 0:
        errors.append("mesh must contain vertices")
    valid_labels = {
        key: value
        for key, value in summary["object_labels"].items()
        if key not in {"unknown", "None", "0"}
    }
    if not valid_labels:
        errors.append("at least one object must have a valid semantic label")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dsg", type=Path)
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument(
        "--require-pipeline-output",
        action="store_true",
        help="require objects, mesh places, trajectory, mesh, and semantic labels",
    )
    args = parser.parse_args()

    if not args.dsg.is_file():
        parser.error(f"DSG does not exist: {args.dsg}")
    try:
        summary = summarize(args.dsg)
    except Exception as error:
        print(f"failed to inspect DSG: {error}", file=sys.stderr)
        return 1

    if args.as_json:
        print(json.dumps(inspection_view(summary), indent=2, sort_keys=True))
    else:
        print_human(summary)

    if args.require_pipeline_output:
        errors = acceptance_errors(summary)
        for error in errors:
            print(f"acceptance failure: {error}", file=sys.stderr)
        return 1 if errors else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
