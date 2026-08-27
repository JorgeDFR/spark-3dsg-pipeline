#!/usr/bin/env python3
"""Summarize a serialized Spark-DSG and optionally enforce v1 acceptance."""

from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path
from typing import Any


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
    objects_layer = layers.OBJECTS
    places_layer = getattr(layers, "MESH_PLACES", getattr(layers, "PLACES"))
    agents_layer = layers.AGENTS

    object_count = layer_count(graph, objects_layer)
    place_count = layer_count(graph, places_layer)
    agent_count = layer_count(graph, agents_layer)

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
        "layers": {
            "OBJECTS": object_count,
            "MESH_PLACES": place_count,
            "AGENTS": agent_count,
        },
        "object_labels": dict(labels.most_common()),
        "mesh": {"vertices": mesh_vertices, "faces": mesh_faces},
        "trajectory_exists": agent_count > 0,
    }


def print_human(summary: dict[str, Any]) -> None:
    print("Graph:")
    print(f"  nodes: {summary['graph']['nodes']}")
    print(f"  edges: {summary['graph']['edges']}")
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
    print("\nMesh:")
    print(f"  vertices: {summary['mesh']['vertices']}")
    print(f"  faces: {summary['mesh']['faces']}")
    print(f"\nTrajectory: {'present' if summary['trajectory_exists'] else 'missing'}")


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
    valid_labels = {key: value for key, value in summary["object_labels"].items() if key not in {"unknown", "None", "0"}}
    if not valid_labels:
        errors.append("at least one object must have a valid semantic label")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dsg", type=Path)
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--require-v1", action="store_true", help="enforce the Spot v1 output contract")
    args = parser.parse_args()

    if not args.dsg.is_file():
        parser.error(f"DSG does not exist: {args.dsg}")
    try:
        summary = summarize(args.dsg)
    except Exception as error:
        print(f"failed to inspect DSG: {error}", file=sys.stderr)
        return 1

    if args.as_json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print_human(summary)

    if args.require_v1:
        errors = acceptance_errors(summary)
        for error in errors:
            print(f"acceptance failure: {error}", file=sys.stderr)
        return 1 if errors else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
