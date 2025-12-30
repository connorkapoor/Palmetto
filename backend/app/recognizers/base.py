"""
Base recognizer class and common data structures for feature recognition.

All feature recognizers inherit from BaseRecognizer and implement
the recognize() method. This provides a unified interface and
common utilities for graph-based feature detection.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Dict, Any

from app.core.topology.graph import (
    AttributedAdjacencyGraph,
    AAGNode,
    TopologyType,
    GraphPattern,
    SubgraphMatch
)
from app.core.topology.attributes import SurfaceType, CurveType


class FeatureType(Enum):
    """Types of recognizable features."""
    # Hole variants
    HOLE_SIMPLE = "hole_simple"
    HOLE_COUNTERSUNK = "hole_countersunk"
    HOLE_COUNTERBORED = "hole_counterbored"
    HOLE_THREADED = "hole_threaded"

    # Shaft features
    SHAFT = "shaft"
    BOSS = "boss"

    # Cavity features
    CAVITY_BLIND = "cavity_blind"
    CAVITY_THROUGH = "cavity_through"
    CAVITY_POCKET = "cavity_pocket"  # Enclosed depression
    CAVITY_SLOT = "cavity_slot"      # Linear depression
    POCKET = "pocket"
    SLOT = "slot"

    # Step features (MFCAD)
    STEP_THROUGH = "step_through"    # Through step/shelf
    STEP_BLIND = "step_blind"        # Blind step/ledge

    # Passage features (MFCAD)
    PASSAGE = "passage"              # Through-passage/extruded cutout

    # Blend features
    FILLET = "fillet"
    CHAMFER = "chamfer"
    ROUND = "round"

    # Sheet metal features
    SHEET_METAL_BEND = "sheet_metal_bend"
    SHEET_METAL_FLANGE = "sheet_metal_flange"
    SHEET_METAL_TAB = "sheet_metal_tab"

    # CNC milling features
    CNC_POCKET = "cnc_pocket"
    CNC_SLOT = "cnc_slot"
    CNC_DRILL = "cnc_drill"

    # Generic
    PROTRUSION = "protrusion"
    DEPRESSION = "depression"
    OTHER = "other"


@dataclass
class RecognizedFeature:
    """
    Result from a feature recognizer.
    Standard output format for all recognizers.
    """
    feature_id: str
    feature_type: FeatureType
    confidence: float  # 0.0 to 1.0
    face_ids: List[str]  # AAG node IDs of faces comprising this feature
    properties: Dict[str, Any] = field(default_factory=dict)  # Feature-specific properties
    bounding_geometry: Optional[Any] = None  # Bounding cylinder, box, etc.
    metadata: Dict[str, Any] = field(default_factory=dict)  # Additional metadata

    def __post_init__(self):
        """Validate confidence is in valid range."""
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError(f"Confidence must be between 0 and 1, got {self.confidence}")


class BaseRecognizer(ABC):
    """
    Abstract base class for all feature recognizers.

    Recognizers analyze the AAG to detect specific features.
    Each recognizer implements its own recognition logic while
    sharing common utilities for graph queries and pattern matching.
    """

    def __init__(self, graph: AttributedAdjacencyGraph):
        """
        Initialize recognizer with an AAG.

        Args:
            graph: AttributedAdjacencyGraph to analyze
        """
        self.graph = graph

    @abstractmethod
    def recognize(self, **kwargs) -> List[RecognizedFeature]:
        """
        Main recognition method - must be implemented by subclasses.

        Args:
            **kwargs: Recognizer-specific parameters

        Returns:
            List of recognized features

        Example:
            For a hole recognizer, kwargs might include:
            - min_diameter: float
            - max_diameter: float
            - hole_types: List[str]
        """
        pass

    @abstractmethod
    def get_name(self) -> str:
        """
        Get unique recognizer name for registration.

        Returns:
            Recognizer name (e.g., "hole_detector")
        """
        pass

    @abstractmethod
    def get_description(self) -> str:
        """
        Get human-readable description for NL mapping.

        Returns:
            Description string
        """
        pass

    @abstractmethod
    def get_feature_types(self) -> List[FeatureType]:
        """
        Get list of feature types this recognizer can detect.

        Returns:
            List of FeatureType enum values
        """
        pass

    # Common utility methods for recognizers

    def _find_cylindrical_faces(
        self,
        min_radius: float = 0.0,
        max_radius: float = float('inf')
    ) -> List[AAGNode]:
        """
        Find cylindrical faces within radius range.

        Args:
            min_radius: Minimum radius
            max_radius: Maximum radius

        Returns:
            List of AAGNodes representing cylindrical faces
        """
        return [
            node for node in self.graph.get_nodes_by_type(TopologyType.FACE)
            if node.attributes.get('surface_type') == SurfaceType.CYLINDER
            and min_radius <= node.attributes.get('radius', 0.0) <= max_radius
        ]

    def _find_planar_faces(self) -> List[AAGNode]:
        """
        Find all planar faces.

        Returns:
            List of AAGNodes representing planar faces
        """
        return [
            node for node in self.graph.get_nodes_by_type(TopologyType.FACE)
            if node.attributes.get('surface_type') == SurfaceType.PLANE
        ]

    def _find_spherical_faces(
        self,
        min_radius: float = 0.0,
        max_radius: float = float('inf')
    ) -> List[AAGNode]:
        """
        Find spherical faces within radius range.

        Args:
            min_radius: Minimum radius
            max_radius: Maximum radius

        Returns:
            List of AAGNodes representing spherical faces
        """
        return [
            node for node in self.graph.get_nodes_by_type(TopologyType.FACE)
            if node.attributes.get('surface_type') == SurfaceType.SPHERE
            and min_radius <= node.attributes.get('radius', 0.0) <= max_radius
        ]

    def _find_conical_faces(self) -> List[AAGNode]:
        """
        Find all conical faces.

        Returns:
            List of AAGNodes representing conical faces
        """
        return [
            node for node in self.graph.get_nodes_by_type(TopologyType.FACE)
            if node.attributes.get('surface_type') == SurfaceType.CONE
        ]

    def _find_toroidal_faces(self) -> List[AAGNode]:
        """
        Find all toroidal faces (potential fillets).

        Returns:
            List of AAGNodes representing toroidal faces
        """
        return [
            node for node in self.graph.get_nodes_by_type(TopologyType.FACE)
            if node.attributes.get('surface_type') == SurfaceType.TORUS
        ]

    def _find_circular_edges(
        self,
        min_radius: float = 0.0,
        max_radius: float = float('inf')
    ) -> List[AAGNode]:
        """
        Find circular edges within radius range.

        Args:
            min_radius: Minimum radius
            max_radius: Maximum radius

        Returns:
            List of AAGNodes representing circular edges
        """
        return [
            node for node in self.graph.get_nodes_by_type(TopologyType.EDGE)
            if node.attributes.get('curve_type') == CurveType.CIRCLE
            and min_radius <= node.attributes.get('radius', 0.0) <= max_radius
        ]

    def _find_linear_edges(self) -> List[AAGNode]:
        """
        Find all linear edges.

        Returns:
            List of AAGNodes representing linear edges
        """
        return [
            node for node in self.graph.get_nodes_by_type(TopologyType.EDGE)
            if node.attributes.get('curve_type') == CurveType.LINE
        ]

    def _match_subgraph(self, pattern: GraphPattern) -> List[SubgraphMatch]:
        """
        Find subgraphs matching a pattern.

        Args:
            pattern: GraphPattern to match

        Returns:
            List of SubgraphMatch objects
        """
        return self.graph.find_subgraph(pattern)

    def _get_adjacent_faces(self, face_node: AAGNode) -> List[AAGNode]:
        """
        Get faces adjacent to the given face.

        Args:
            face_node: Face node

        Returns:
            List of adjacent face nodes
        """
        from app.core.topology.graph import RelationType
        return self.graph.get_neighbors(face_node.node_id, RelationType.ADJACENT)

    def _get_bounding_edges(self, face_node: AAGNode) -> List[AAGNode]:
        """
        Get edges that bound a face.

        Args:
            face_node: Face node

        Returns:
            List of edge nodes bounding the face
        """
        return self.graph.get_edges_bounding_face(face_node.node_id)

    def _filter_by_attribute(
        self,
        nodes: List[AAGNode],
        attribute_name: str,
        attribute_value: Any
    ) -> List[AAGNode]:
        """
        Filter nodes by attribute value.

        Args:
            nodes: List of nodes to filter
            attribute_name: Attribute name to check
            attribute_value: Value to match

        Returns:
            Filtered list of nodes
        """
        return [
            node for node in nodes
            if node.attributes.get(attribute_name) == attribute_value
        ]

    def _generate_feature_id(self, feature_type: FeatureType, index: int = 0) -> str:
        """
        Generate a unique feature ID.

        Args:
            feature_type: Type of feature
            index: Index for uniqueness

        Returns:
            Feature ID string
        """
        return f"{feature_type.value}_{index}"

    @staticmethod
    def _serialize_geometry(obj: Any) -> Any:
        """
        Convert OpenCASCADE geometry objects to JSON-serializable formats.

        Args:
            obj: Object to serialize (gp_Pnt, gp_Dir, gp_Vec, etc.)

        Returns:
            Serializable representation (list, dict, or original if already serializable)
        """
        from OCC.Core.gp import gp_Pnt, gp_Dir, gp_Vec

        if isinstance(obj, (gp_Pnt, gp_Dir, gp_Vec)):
            # Convert to [x, y, z] list
            return [obj.X(), obj.Y(), obj.Z()]
        elif isinstance(obj, (list, tuple)):
            # Recursively serialize list/tuple elements
            return [BaseRecognizer._serialize_geometry(item) for item in obj]
        elif isinstance(obj, dict):
            # Recursively serialize dict values
            return {key: BaseRecognizer._serialize_geometry(value) for key, value in obj.items()}
        else:
            # Return as-is if already serializable
            return obj

    def _find_shared_edge(self, face_node1: AAGNode, face_node2: AAGNode) -> Optional[Any]:
        """
        Find the shared edge between two adjacent faces.

        Args:
            face_node1: First face node
            face_node2: Second face node

        Returns:
            TopoDS_Edge if found, None otherwise
        """
        from app.core.occt_imports import TopExp_Explorer, TopAbs_EDGE, topods

        try:
            # Get edges of face1
            edges1 = set()
            edge_explorer = TopExp_Explorer(face_node1.occt_entity, TopAbs_EDGE)
            while edge_explorer.More():
                edges1.add(edge_explorer.Current().__hash__())
                edge_explorer.Next()

            # Find matching edge in face2
            edge_explorer = TopExp_Explorer(face_node2.occt_entity, TopAbs_EDGE)
            while edge_explorer.More():
                edge = edge_explorer.Current()
                if edge.__hash__() in edges1:
                    return topods.Edge(edge)
                edge_explorer.Next()

            return None

        except Exception:
            return None
