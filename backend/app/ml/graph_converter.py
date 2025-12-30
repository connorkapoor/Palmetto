"""
Convert AAG (Attributed Adjacency Graph) to PyTorch Geometric format.

Extracts node and edge features for GNN training.
"""

import torch
import numpy as np
from typing import Dict, List, Tuple, Optional
from torch_geometric.data import Data

from app.core.topology.graph import AttributedAdjacencyGraph, AAGNode, TopologyType
from app.core.topology.attributes import SurfaceType, CurveType


class AAGToGraphConverter:
    """Converts AAG to PyTorch Geometric Data objects."""

    def __init__(self):
        # Feature dimensions
        self.node_feature_dim = 12  # See _extract_face_features
        self.edge_feature_dim = 2   # Dihedral angle + edge type

    def convert(
        self,
        aag: AttributedAdjacencyGraph,
        face_labels: Optional[Dict[int, int]] = None
    ) -> Data:
        """
        Convert AAG to PyTorch Geometric Data.

        Args:
            aag: Attributed Adjacency Graph
            face_labels: Optional ground truth labels (face_id -> label_idx)

        Returns:
            PyTorch Geometric Data object with:
                - x: Node features [num_nodes, node_feature_dim]
                - edge_index: Graph connectivity [2, num_edges]
                - edge_attr: Edge features [num_edges, edge_feature_dim]
                - y: Node labels [num_nodes] (if face_labels provided)
                - face_id_map: Mapping from node index to AAG face ID
        """
        # Extract planar face nodes
        face_nodes = [
            node for node in aag.get_nodes_by_type(TopologyType.FACE)
            if node.attributes.get('surface_type') == SurfaceType.PLANE
        ]

        if not face_nodes:
            return self._empty_graph()

        # Create node index mapping
        node_to_idx = {node.node_id: i for i, node in enumerate(face_nodes)}
        idx_to_face_id = {}  # Node index -> STEP face ID

        # Extract STEP face IDs
        for i, node in enumerate(face_nodes):
            if node.node_id.startswith("face_"):
                try:
                    step_face_id = int(node.node_id.split("_")[1])
                    idx_to_face_id[i] = step_face_id
                except:
                    pass

        # Extract node features
        node_features = []
        for node in face_nodes:
            features = self._extract_face_features(node, aag)
            node_features.append(features)

        x = torch.tensor(node_features, dtype=torch.float)

        # Extract edges and edge features
        edge_list = []
        edge_features = []

        for i, node in enumerate(face_nodes):
            # Get adjacent faces
            for edge in aag.edges.values():
                # Check for face-to-face adjacency (relationship is "adjacent" for face nodes)
                if edge.relationship.value == "adjacent":
                    # Both source and target should be face nodes
                    if edge.source == node.node_id and edge.target in node_to_idx:
                        j = node_to_idx[edge.target]
                        edge_list.append([i, j])

                        # Extract edge features
                        edge_feat = self._extract_edge_features(
                            node.node_id, edge.target, aag
                        )
                        edge_features.append(edge_feat)

        if edge_list:
            edge_index = torch.tensor(edge_list, dtype=torch.long).t().contiguous()
            edge_attr = torch.tensor(edge_features, dtype=torch.float)
        else:
            # Empty graph - no edges
            edge_index = torch.empty((2, 0), dtype=torch.long)
            edge_attr = torch.empty((0, self.edge_feature_dim), dtype=torch.float)

        # Extract labels if provided
        y = None
        if face_labels is not None:
            labels = []
            for i, node in enumerate(face_nodes):
                step_face_id = idx_to_face_id.get(i)
                if step_face_id is not None and step_face_id in face_labels:
                    # Binary classification: feature (0-14) vs stock (15)
                    label_idx = face_labels[step_face_id]
                    labels.append(0 if label_idx < 15 else 1)  # 0=feature, 1=stock
                else:
                    labels.append(-1)  # Unknown

            y = torch.tensor(labels, dtype=torch.long)

        data = Data(
            x=x,
            edge_index=edge_index,
            edge_attr=edge_attr,
            y=y
        )

        # Don't store mappings in Data - they cause batching issues
        # These can be reconstructed later if needed for inference

        return data

    def _extract_face_features(
        self,
        face_node: AAGNode,
        aag: AttributedAdjacencyGraph
    ) -> List[float]:
        """
        Extract geometric features from a face node.

        Feature vector (12 dimensions):
        [0-2]: Normal vector (nx, ny, nz)
        [3-5]: Center of mass (x, y, z)
        [6]:   Area
        [7]:   Number of bounding edges
        [8]:   Min dihedral angle
        [9]:   Max dihedral angle
        [10]:  Avg dihedral angle
        [11]:  Std dihedral angle
        """
        # Normal
        normal = face_node.attributes.get('normal')
        if normal:
            nx, ny, nz = normal.X(), normal.Y(), normal.Z()
        else:
            nx, ny, nz = 0.0, 0.0, 1.0

        # Center of mass
        center = face_node.attributes.get('center_of_mass')
        if center:
            cx, cy, cz = center.X(), center.Y(), center.Z()
        else:
            cx, cy, cz = 0.0, 0.0, 0.0

        # Area
        area = face_node.attributes.get('area', 0.0)

        # Count bounding edges
        num_edges = 0
        for edge in aag.edges.values():
            if edge.relationship.value == "face_bound_edge" and edge.source == face_node.node_id:
                num_edges += 1

        # Dihedral angles with adjacent faces
        dihedrals = []
        for edge in aag.edges.values():
            if edge.relationship.value == "face_adjacent_face":
                if edge.source == face_node.node_id:
                    adj_id = edge.target
                elif edge.target == face_node.node_id:
                    adj_id = edge.source
                else:
                    continue

                dihedral = aag.get_cached_dihedral_angle(face_node.node_id, adj_id)
                if dihedral is None:
                    dihedral = aag.get_cached_dihedral_angle(adj_id, face_node.node_id)

                if dihedral is not None:
                    dihedrals.append(dihedral)

        if dihedrals:
            min_dihedral = min(dihedrals)
            max_dihedral = max(dihedrals)
            avg_dihedral = np.mean(dihedrals)
            std_dihedral = np.std(dihedrals)
        else:
            min_dihedral = 180.0
            max_dihedral = 180.0
            avg_dihedral = 180.0
            std_dihedral = 0.0

        return [
            nx, ny, nz,           # Normal
            cx, cy, cz,           # Center
            area,                 # Area
            float(num_edges),     # Edge count
            min_dihedral,         # Min dihedral
            max_dihedral,         # Max dihedral
            avg_dihedral,         # Avg dihedral
            std_dihedral          # Std dihedral
        ]

    def _extract_edge_features(
        self,
        face_id1: str,
        face_id2: str,
        aag: AttributedAdjacencyGraph
    ) -> List[float]:
        """
        Extract features from an edge (face-face adjacency).

        Feature vector (2 dimensions):
        [0]: Dihedral angle
        [1]: Edge type (0=shared edge, 1=other)
        """
        # Dihedral angle
        dihedral = aag.get_cached_dihedral_angle(face_id1, face_id2)
        if dihedral is None:
            dihedral = aag.get_cached_dihedral_angle(face_id2, face_id1)
        if dihedral is None:
            dihedral = 180.0  # Default

        # Edge type (simplified - all are shared edges for now)
        edge_type = 0.0

        return [dihedral, edge_type]

    def _empty_graph(self) -> Data:
        """Return an empty graph."""
        return Data(
            x=torch.empty((0, self.node_feature_dim), dtype=torch.float),
            edge_index=torch.empty((2, 0), dtype=torch.long),
            edge_attr=torch.empty((0, self.edge_feature_dim), dtype=torch.float),
            y=torch.empty((0,), dtype=torch.long)
        )
