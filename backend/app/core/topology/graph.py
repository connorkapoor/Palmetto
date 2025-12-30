"""
Attributed Adjacency Graph (AAG) data structures.

The AAG is the core representation for CAD feature recognition.
It combines topology (vertices, edges, faces) with geometric attributes
and supports graph-based pattern matching for feature detection.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Callable
from collections import defaultdict

from OCC.Core.TopoDS import TopoDS_Shape


class TopologyType(Enum):
    """Types of topological entities in a B-Rep model."""
    VERTEX = "vertex"
    EDGE = "edge"
    FACE = "face"
    SHELL = "shell"
    SOLID = "solid"
    COMPOUND = "compound"


class RelationType(Enum):
    """Types of relationships between topological entities."""
    BOUNDS = "bounds"              # Edge bounds face, face bounds solid
    BOUNDED_BY = "bounded_by"      # Inverse of BOUNDS
    ADJACENT = "adjacent"          # Faces share edge, edges share vertex
    COPLANAR = "coplanar"          # Faces are coplanar
    TANGENT = "tangent"            # Faces are tangent
    PARALLEL = "parallel"          # Edges/faces are parallel


@dataclass
class AAGNode:
    """
    Node in the Attributed Adjacency Graph.
    Represents a topological entity with geometric attributes.
    """
    node_id: str
    topology_type: TopologyType
    occt_entity: TopoDS_Shape  # Original OpenCASCADE entity
    attributes: Dict[str, Any] = field(default_factory=dict)

    def get_attribute(self, key: str, default: Any = None) -> Any:
        """Get an attribute value with optional default."""
        return self.attributes.get(key, default)

    def set_attribute(self, key: str, value: Any) -> None:
        """Set an attribute value."""
        self.attributes[key] = value

    def has_attribute(self, key: str) -> bool:
        """Check if attribute exists."""
        return key in self.attributes

    def __hash__(self) -> int:
        """Make node hashable based on node_id."""
        return hash(self.node_id)

    def __eq__(self, other: object) -> bool:
        """Compare nodes by node_id."""
        if not isinstance(other, AAGNode):
            return NotImplemented
        return self.node_id == other.node_id


@dataclass
class AAGEdge:
    """
    Edge in the Attributed Adjacency Graph.
    Represents a relationship between two topological entities.

    Following Analysis Situs principle: Edges can store attributes like
    dihedral angles, edge vexity, and other geometric properties.
    """
    edge_id: str
    source: str  # source node_id
    target: str  # target node_id
    relationship: RelationType
    attributes: Dict[str, Any] = field(default_factory=dict)

    def get_attribute(self, key: str, default: Any = None) -> Any:
        """Get an attribute value with optional default."""
        return self.attributes.get(key, default)

    def set_attribute(self, key: str, value: Any) -> None:
        """Set an attribute value."""
        self.attributes[key] = value

    def has_attribute(self, key: str) -> bool:
        """Check if attribute exists."""
        return key in self.attributes

    def __hash__(self) -> int:
        """Make edge hashable based on edge_id."""
        return hash(self.edge_id)

    def __eq__(self, other: object) -> bool:
        """Compare edges by edge_id."""
        if not isinstance(other, AAGEdge):
            return NotImplemented
        return self.edge_id == other.edge_id


@dataclass
class GraphPattern:
    """
    Template for subgraph pattern matching.
    Used to find recurring feature patterns in the AAG.
    """
    node_constraints: List[Dict[str, Any]]  # Constraints for each pattern node
    edge_constraints: List[tuple[int, int, RelationType]]  # (src_idx, tgt_idx, rel_type)
    name: Optional[str] = None


@dataclass
class SubgraphMatch:
    """
    Result of pattern matching operation.
    Maps pattern node indices to actual graph node IDs.
    """
    node_mapping: Dict[int, str]  # pattern_idx -> graph_node_id
    confidence: float = 1.0


class AttributedAdjacencyGraph:
    """
    Main AAG data structure.

    Represents CAD B-Rep topology as an attributed graph where:
    - Nodes represent topological entities (vertices, edges, faces, etc.)
    - Edges represent relationships (bounding, adjacency, etc.)
    - Attributes store geometric properties (normals, areas, surface types, etc.)
    """

    def __init__(self):
        """Initialize empty graph."""
        self.nodes: Dict[str, AAGNode] = {}
        self.edges: Dict[str, AAGEdge] = {}
        self._adjacency_list: Dict[str, List[str]] = defaultdict(list)  # node_id -> [edge_ids]
        self._reverse_adjacency: Dict[str, List[str]] = defaultdict(list)  # node_id -> [edge_ids pointing to it]

    def add_node(self, node: AAGNode) -> None:
        """
        Add a node to the graph.

        Args:
            node: AAGNode to add
        """
        self.nodes[node.node_id] = node
        if node.node_id not in self._adjacency_list:
            self._adjacency_list[node.node_id] = []
        if node.node_id not in self._reverse_adjacency:
            self._reverse_adjacency[node.node_id] = []

    def add_edge(self, edge: AAGEdge) -> None:
        """
        Add an edge to the graph.

        Args:
            edge: AAGEdge to add
        """
        self.edges[edge.edge_id] = edge
        self._adjacency_list[edge.source].append(edge.edge_id)
        self._reverse_adjacency[edge.target].append(edge.edge_id)

    def get_node(self, node_id: str) -> Optional[AAGNode]:
        """
        Get node by ID.

        Args:
            node_id: Node identifier

        Returns:
            AAGNode or None if not found
        """
        return self.nodes.get(node_id)

    def get_edge(self, edge_id: str) -> Optional[AAGEdge]:
        """
        Get edge by ID.

        Args:
            edge_id: Edge identifier

        Returns:
            AAGEdge or None if not found
        """
        return self.edges.get(edge_id)

    def get_neighbors(self, node_id: str, rel_type: Optional[RelationType] = None) -> List[AAGNode]:
        """
        Get neighboring nodes connected via outgoing edges.

        Args:
            node_id: Source node ID
            rel_type: Optional filter by relationship type

        Returns:
            List of neighbor AAGNodes
        """
        neighbors = []
        for edge_id in self._adjacency_list.get(node_id, []):
            edge = self.edges[edge_id]
            if rel_type is None or edge.relationship == rel_type:
                target_node = self.nodes.get(edge.target)
                if target_node:
                    neighbors.append(target_node)
        return neighbors

    def get_predecessors(self, node_id: str, rel_type: Optional[RelationType] = None) -> List[AAGNode]:
        """
        Get predecessor nodes connected via incoming edges.

        Args:
            node_id: Target node ID
            rel_type: Optional filter by relationship type

        Returns:
            List of predecessor AAGNodes
        """
        predecessors = []
        for edge_id in self._reverse_adjacency.get(node_id, []):
            edge = self.edges[edge_id]
            if rel_type is None or edge.relationship == rel_type:
                source_node = self.nodes.get(edge.source)
                if source_node:
                    predecessors.append(source_node)
        return predecessors

    def get_faces_adjacent_to_edge(self, edge_node_id: str) -> List[AAGNode]:
        """
        Get faces that are bounded by a specific edge.

        Args:
            edge_node_id: ID of edge node (TopologyType.EDGE)

        Returns:
            List of face AAGNodes
        """
        # Find faces where this edge bounds them
        faces = []
        for face_node in self.nodes.values():
            if face_node.topology_type == TopologyType.FACE:
                # Check if this edge bounds the face
                bounding_edges = self.get_predecessors(face_node.node_id, RelationType.BOUNDS)
                if any(e.node_id == edge_node_id for e in bounding_edges):
                    faces.append(face_node)
        return faces

    def get_edges_bounding_face(self, face_node_id: str) -> List[AAGNode]:
        """
        Get edges that bound a specific face.

        Args:
            face_node_id: ID of face node (TopologyType.FACE)

        Returns:
            List of edge AAGNodes
        """
        return self.get_predecessors(face_node_id, RelationType.BOUNDS)

    def get_nodes_by_type(self, topology_type: TopologyType) -> List[AAGNode]:
        """
        Get all nodes of a specific topology type.

        Args:
            topology_type: Type to filter by

        Returns:
            List of AAGNodes of the specified type
        """
        return [node for node in self.nodes.values() if node.topology_type == topology_type]

    def get_adjacency_edge(self, source_id: str, target_id: str) -> Optional[AAGEdge]:
        """
        Get the adjacency edge between two nodes (if it exists).

        This is useful for retrieving cached dihedral angles and other
        edge attributes computed during AAG construction.

        Args:
            source_id: Source node ID
            target_id: Target node ID

        Returns:
            AAGEdge if edge exists, None otherwise
        """
        edge_id = f"{source_id}_adjacent_{target_id}"
        return self.edges.get(edge_id)

    def get_cached_dihedral_angle(self, face1_id: str, face2_id: str) -> Optional[float]:
        """
        Get cached dihedral angle between two adjacent faces.

        Returns the angle computed during AAG construction (Analysis Situs principle).
        This is more efficient than recomputing the angle.

        Args:
            face1_id: First face node ID
            face2_id: Second face node ID

        Returns:
            Dihedral angle in degrees, or None if not found
        """
        edge = self.get_adjacency_edge(face1_id, face2_id)
        if edge and 'dihedral_angle' in edge.attributes:
            return edge.attributes['dihedral_angle']
        return None

    def traverse_bfs(self, start_id: str, visitor: Callable[[AAGNode], bool]) -> None:
        """
        Breadth-first traversal starting from a node.

        Args:
            start_id: Starting node ID
            visitor: Function called for each node. Return False to stop traversal.
        """
        if start_id not in self.nodes:
            return

        from collections import deque
        queue = deque([start_id])
        visited = {start_id}

        while queue:
            current_id = queue.popleft()
            current_node = self.nodes[current_id]

            # Visit node
            should_continue = visitor(current_node)
            if not should_continue:
                return

            # Add unvisited neighbors
            for neighbor in self.get_neighbors(current_id):
                if neighbor.node_id not in visited:
                    visited.add(neighbor.node_id)
                    queue.append(neighbor.node_id)

    def traverse_dfs(self, start_id: str, visitor: Callable[[AAGNode], bool]) -> None:
        """
        Depth-first traversal starting from a node.

        Args:
            start_id: Starting node ID
            visitor: Function called for each node. Return False to stop traversal.
        """
        if start_id not in self.nodes:
            return

        visited = set()

        def _dfs_helper(node_id: str):
            if node_id in visited:
                return True

            visited.add(node_id)
            node = self.nodes[node_id]

            # Visit node
            should_continue = visitor(node)
            if not should_continue:
                return False

            # Recurse to neighbors
            for neighbor in self.get_neighbors(node_id):
                if not _dfs_helper(neighbor.node_id):
                    return False

            return True

        _dfs_helper(start_id)

    def find_subgraph(self, pattern: GraphPattern) -> List[SubgraphMatch]:
        """
        Find all subgraphs matching the given pattern.
        Uses backtracking algorithm for subgraph isomorphism.

        Args:
            pattern: GraphPattern to match

        Returns:
            List of SubgraphMatch objects
        """
        matches = []

        if not pattern.node_constraints:
            return matches

        # Get candidate nodes for first pattern node
        candidates = self._get_candidate_nodes(pattern.node_constraints[0])

        for candidate in candidates:
            mapping = {0: candidate.node_id}
            if self._backtrack_match(pattern, mapping, 1):
                matches.append(SubgraphMatch(
                    node_mapping=mapping.copy(),
                    confidence=self._compute_match_confidence(pattern, mapping)
                ))

        return matches

    def _get_candidate_nodes(self, constraints: Dict[str, Any]) -> List[AAGNode]:
        """Get nodes matching the given constraints."""
        candidates = []
        for node in self.nodes.values():
            if self._node_matches_constraints(node, constraints):
                candidates.append(node)
        return candidates

    def _node_matches_constraints(self, node: AAGNode, constraints: Dict[str, Any]) -> bool:
        """Check if a node matches all constraints."""
        for key, value in constraints.items():
            if key == "topology_type":
                if node.topology_type != value:
                    return False
            elif key in node.attributes:
                if node.attributes[key] != value:
                    return False
            else:
                return False
        return True

    def _backtrack_match(self, pattern: GraphPattern, mapping: Dict[int, str], next_idx: int) -> bool:
        """Backtracking algorithm for pattern matching."""
        if next_idx >= len(pattern.node_constraints):
            return True  # All nodes matched

        # Get constraints for next pattern node
        constraints = pattern.node_constraints[next_idx]

        # Find required connections from already-mapped nodes
        required_neighbors = [
            (src_idx, rel) for src_idx, tgt_idx, rel in pattern.edge_constraints
            if tgt_idx == next_idx and src_idx in mapping
        ]

        # Get candidate nodes
        candidates = set()
        if required_neighbors:
            for src_idx, rel in required_neighbors:
                src_node_id = mapping[src_idx]
                neighbors = self.get_neighbors(src_node_id, rel)
                node_candidates = [
                    n.node_id for n in neighbors
                    if self._node_matches_constraints(n, constraints) and n.node_id not in mapping.values()
                ]
                if not candidates:
                    candidates = set(node_candidates)
                else:
                    candidates = candidates.intersection(node_candidates)
        else:
            # No required connections, get all matching nodes
            matching_nodes = self._get_candidate_nodes(constraints)
            candidates = {n.node_id for n in matching_nodes if n.node_id not in mapping.values()}

        # Try each candidate
        for candidate_id in candidates:
            mapping[next_idx] = candidate_id
            if self._backtrack_match(pattern, mapping, next_idx + 1):
                return True
            del mapping[next_idx]

        return False

    def _compute_match_confidence(self, pattern: GraphPattern, mapping: Dict[int, str]) -> float:
        """Compute confidence score for a pattern match."""
        # Simple confidence: 1.0 if all constraints satisfied
        # Can be extended with fuzzy matching, geometric similarity, etc.
        return 1.0

    def get_statistics(self) -> Dict[str, int]:
        """
        Get graph statistics.

        Returns:
            Dictionary with counts of different topology types
        """
        stats = {ttype.value: 0 for ttype in TopologyType}
        for node in self.nodes.values():
            stats[node.topology_type.value] += 1
        stats["total_edges"] = len(self.edges)
        return stats

    def __len__(self) -> int:
        """Return number of nodes in graph."""
        return len(self.nodes)

    def __repr__(self) -> str:
        """String representation of graph."""
        stats = self.get_statistics()
        return (f"AttributedAdjacencyGraph("
                f"nodes={len(self.nodes)}, "
                f"edges={len(self.edges)}, "
                f"faces={stats.get('face', 0)})")
