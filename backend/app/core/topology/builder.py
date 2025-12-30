"""
AAG Builder - Constructs Attributed Adjacency Graph from B-Rep topology.

This module builds the graph by:
1. Extracting topology (vertices, edges, faces, shells)
2. Computing geometric attributes for each entity
3. Establishing relationships (bounding, adjacency, etc.)
"""

from typing import Dict
import logging

from app.core.occt_imports import (
    TopoDS_Shape, TopoDS_Vertex, TopoDS_Edge, TopoDS_Face, TopoDS_Shell, topods,
    TopExp_Explorer, TopAbs_VERTEX, TopAbs_EDGE, TopAbs_FACE, TopAbs_SHELL,
    TopTools_IndexedDataMapOfShapeListOfShape, TopTools_ListIteratorOfListOfShape,
    topexp, BRep_Tool, PYTHONOCC_AVAILABLE
)

from app.core.topology.graph import (
    AttributedAdjacencyGraph,
    AAGNode,
    AAGEdge,
    TopologyType,
    RelationType
)
from app.core.topology.attributes import (
    AttributeComputer,
    SurfaceType,
    CurveType
)

logger = logging.getLogger(__name__)


class AAGBuilder:
    """
    Constructs an Attributed Adjacency Graph from a B-Rep shape.

    The builder follows a three-phase process:
    1. Extract topology: traverse B-Rep and create graph nodes
    2. Compute attributes: calculate geometric properties for each node
    3. Establish relationships: create edges representing topological relationships
    """

    def __init__(self, shape: TopoDS_Shape):
        """
        Initialize builder with a B-Rep shape.

        Args:
            shape: TopoDS_Shape to build graph from
        """
        self.shape = shape
        self.graph = AttributedAdjacencyGraph()
        self._entity_to_id: Dict[int, str] = {}  # hash -> node_id mapping

    def build(self) -> AttributedAdjacencyGraph:
        """
        Build the complete AAG.

        Returns:
            AttributedAdjacencyGraph with all nodes, edges, and attributes

        Pipeline:
            1. Extract topology (vertices, edges, faces, shells)
            2. Compute geometric attributes
            3. Establish bounding relationships
            4. Establish adjacency relationships
            5. Establish geometric relationships (coplanar, etc.)
        """
        logger.info("Building Attributed Adjacency Graph...")

        # Phase 1: Extract topology
        logger.info("Phase 1: Extracting topology...")
        self._extract_vertices()
        self._extract_edges()
        self._extract_faces()
        self._extract_shells()

        stats = self.graph.get_statistics()
        logger.info(f"Extracted {stats['vertex']} vertices, {stats['edge']} edges, "
                   f"{stats['face']} faces, {stats['shell']} shells")

        # Phase 2: Compute attributes
        logger.info("Phase 2: Computing geometric attributes...")
        self._compute_vertex_attributes()
        self._compute_edge_attributes()
        self._compute_face_attributes()

        # Phase 3: Establish relationships
        logger.info("Phase 3: Establishing relationships...")
        self._establish_bounding_relationships()
        self._establish_adjacency_relationships()
        self._establish_geometric_relationships()

        logger.info(f"AAG built successfully: {len(self.graph.nodes)} nodes, "
                   f"{len(self.graph.edges)} edges")

        return self.graph

    def _extract_vertices(self) -> None:
        """Extract all vertices from B-Rep."""
        explorer = TopExp_Explorer(self.shape, TopAbs_VERTEX)
        vertex_index = 0

        while explorer.More():
            vertex = topods.Vertex(explorer.Current())
            node_id = f"vertex_{vertex_index}"

            # Store hash mapping for later reference
            self._entity_to_id[vertex.__hash__()] = node_id

            node = AAGNode(
                node_id=node_id,
                topology_type=TopologyType.VERTEX,
                occt_entity=vertex,
                attributes={}
            )

            self.graph.add_node(node)
            vertex_index += 1
            explorer.Next()

    def _extract_edges(self) -> None:
        """Extract all edges from B-Rep."""
        explorer = TopExp_Explorer(self.shape, TopAbs_EDGE)
        edge_index = 0

        while explorer.More():
            edge = topods.Edge(explorer.Current())
            node_id = f"edge_{edge_index}"

            # Store hash mapping
            self._entity_to_id[edge.__hash__()] = node_id

            node = AAGNode(
                node_id=node_id,
                topology_type=TopologyType.EDGE,
                occt_entity=edge,
                attributes={}
            )

            self.graph.add_node(node)
            edge_index += 1
            explorer.Next()

    def _extract_faces(self) -> None:
        """Extract all faces from B-Rep."""
        explorer = TopExp_Explorer(self.shape, TopAbs_FACE)
        face_index = 0

        while explorer.More():
            face = topods.Face(explorer.Current())
            node_id = f"face_{face_index}"

            # Store hash mapping
            self._entity_to_id[face.__hash__()] = node_id

            node = AAGNode(
                node_id=node_id,
                topology_type=TopologyType.FACE,
                occt_entity=face,
                attributes={}
            )

            self.graph.add_node(node)
            face_index += 1
            explorer.Next()

    def _extract_shells(self) -> None:
        """Extract all shells from B-Rep."""
        explorer = TopExp_Explorer(self.shape, TopAbs_SHELL)
        shell_index = 0

        while explorer.More():
            shell = topods.Shell(explorer.Current())
            node_id = f"shell_{shell_index}"

            # Store hash mapping
            self._entity_to_id[shell.__hash__()] = node_id

            node = AAGNode(
                node_id=node_id,
                topology_type=TopologyType.SHELL,
                occt_entity=shell,
                attributes={}
            )

            self.graph.add_node(node)
            shell_index += 1
            explorer.Next()

    def _compute_vertex_attributes(self) -> None:
        """Compute geometric attributes for all vertices."""
        for node in self.graph.nodes.values():
            if node.topology_type != TopologyType.VERTEX:
                continue

            vertex = node.occt_entity
            attrs = AttributeComputer.compute_vertex_attributes(vertex)

            # Store as dict in node attributes
            node.attributes.update({
                'x': attrs.x,
                'y': attrs.y,
                'z': attrs.z,
                'point': attrs.point
            })

    def _compute_edge_attributes(self) -> None:
        """Compute geometric attributes for all edges."""
        for node in self.graph.nodes.values():
            if node.topology_type != TopologyType.EDGE:
                continue

            edge = node.occt_entity
            try:
                attrs = AttributeComputer.compute_edge_attributes(edge)

                # Store as dict in node attributes
                node.attributes.update({
                    'curve_type': attrs.curve_type,
                    'length': attrs.length,
                    'first_point': attrs.first_point,
                    'last_point': attrs.last_point,
                    'tangent': attrs.tangent,
                    'radius': attrs.radius,
                    'center': attrs.center,
                    'axis': attrs.axis
                })
            except Exception as e:
                logger.warning(f"Failed to compute attributes for {node.node_id}: {e}")
                node.attributes['curve_type'] = CurveType.OTHER

    def _compute_face_attributes(self) -> None:
        """Compute geometric attributes for all faces."""
        for node in self.graph.nodes.values():
            if node.topology_type != TopologyType.FACE:
                continue

            face = node.occt_entity
            try:
                attrs = AttributeComputer.compute_face_attributes(face)

                # Store as dict in node attributes
                node.attributes.update({
                    'normal': attrs.normal,
                    'area': attrs.area,
                    'surface_type': attrs.surface_type,
                    'center_of_mass': attrs.center_of_mass,
                    'curvature': attrs.curvature,
                    'radius': attrs.radius,
                    'axis': attrs.axis,
                    'apex': attrs.apex,
                    'plane_normal': attrs.plane_normal
                })
            except Exception as e:
                logger.warning(f"Failed to compute attributes for {node.node_id}: {e}")
                node.attributes['surface_type'] = SurfaceType.OTHER

    def _establish_bounding_relationships(self) -> None:
        """
        Establish bounding relationships:
        - Vertices bound edges
        - Edges bound faces
        - Faces bound shells
        """
        # Edges bound faces
        for face_node in self.graph.get_nodes_by_type(TopologyType.FACE):
            face = face_node.occt_entity

            # Explore edges of this face
            edge_explorer = TopExp_Explorer(face, TopAbs_EDGE)

            while edge_explorer.More():
                edge = topods.Edge(edge_explorer.Current())
                edge_hash = edge.__hash__()
                edge_id = self._entity_to_id.get(edge_hash)

                if edge_id:
                    # Create BOUNDS relationship: edge -> face
                    edge_obj = AAGEdge(
                        edge_id=f"{edge_id}_bounds_{face_node.node_id}",
                        source=edge_id,
                        target=face_node.node_id,
                        relationship=RelationType.BOUNDS
                    )
                    self.graph.add_edge(edge_obj)

                    # Create inverse BOUNDED_BY: face -> edge
                    bounded_edge = AAGEdge(
                        edge_id=f"{face_node.node_id}_bounded_by_{edge_id}",
                        source=face_node.node_id,
                        target=edge_id,
                        relationship=RelationType.BOUNDED_BY
                    )
                    self.graph.add_edge(bounded_edge)

                edge_explorer.Next()

        # Vertices bound edges
        for edge_node in self.graph.get_nodes_by_type(TopologyType.EDGE):
            edge = edge_node.occt_entity

            # Get vertices of edge
            vertex_explorer = TopExp_Explorer(edge, TopAbs_VERTEX)

            while vertex_explorer.More():
                vertex = topods.Vertex(vertex_explorer.Current())
                vertex_hash = vertex.__hash__()
                vertex_id = self._entity_to_id.get(vertex_hash)

                if vertex_id:
                    # Create BOUNDS relationship: vertex -> edge
                    edge_obj = AAGEdge(
                        edge_id=f"{vertex_id}_bounds_{edge_node.node_id}",
                        source=vertex_id,
                        target=edge_node.node_id,
                        relationship=RelationType.BOUNDS
                    )
                    self.graph.add_edge(edge_obj)

                    # Create inverse BOUNDED_BY: edge -> vertex
                    bounded_edge = AAGEdge(
                        edge_id=f"{edge_node.node_id}_bounded_by_{vertex_id}",
                        source=edge_node.node_id,
                        target=vertex_id,
                        relationship=RelationType.BOUNDED_BY
                    )
                    self.graph.add_edge(bounded_edge)

                vertex_explorer.Next()

    def _establish_adjacency_relationships(self) -> None:
        """
        Establish adjacency relationships:
        - Faces are adjacent if they share an edge
        - Edges are adjacent if they share a vertex
        - Cache dihedral angles on adjacency edges (Analysis Situs principle)
        """
        from app.core.geometry.dihedral import DihedralAnalyzer

        # Face adjacency via shared edges
        edge_face_map = TopTools_IndexedDataMapOfShapeListOfShape()
        topexp.MapShapesAndAncestors(self.shape, TopAbs_EDGE, TopAbs_FACE, edge_face_map)

        for i in range(1, edge_face_map.Size() + 1):
            shared_edge = edge_face_map.FindKey(i)
            faces = edge_face_map.FindFromIndex(i)

            # If multiple faces share this edge, they are adjacent
            if faces.Size() >= 2:
                face_list = []
                # Use iterator to traverse the list
                face_iter = TopTools_ListIteratorOfListOfShape(faces)
                while face_iter.More():
                    face = topods.Face(face_iter.Value())
                    face_hash = face.__hash__()
                    face_id = self._entity_to_id.get(face_hash)
                    if face_id:
                        face_list.append((face_id, face))
                    face_iter.Next()

                # Create adjacency between pairs and cache dihedral angles
                for idx1, (f1_id, face1) in enumerate(face_list):
                    for idx2, (f2_id, face2) in enumerate(face_list):
                        if idx1 < idx2:  # Only process each pair once
                            # Compute dihedral angle at shared edge (Analysis Situs principle)
                            try:
                                edge_occt = topods.Edge(shared_edge)
                                angle = DihedralAnalyzer.compute_angle(face1, face2, shared_edge=edge_occt)
                                angle_type = DihedralAnalyzer.classify_angle(angle)

                                # Store angle classification
                                is_convex = DihedralAnalyzer.is_convex(angle)
                                is_concave = DihedralAnalyzer.is_concave(angle)
                                is_tangent = DihedralAnalyzer.is_tangent(angle)

                                # Get shared edge ID for reference
                                shared_edge_hash = shared_edge.__hash__()
                                shared_edge_id = self._entity_to_id.get(shared_edge_hash)

                            except Exception as e:
                                # Fallback if dihedral computation fails
                                logger.warning(f"Failed to compute dihedral for {f1_id}-{f2_id}: {e}")
                                angle = 180.0
                                angle_type = None
                                is_convex = False
                                is_concave = False
                                is_tangent = True
                                shared_edge_id = None

                            # Create adjacency edges with cached dihedral data
                            # Edge from f1 to f2
                            adj_edge_1 = AAGEdge(
                                edge_id=f"{f1_id}_adjacent_{f2_id}",
                                source=f1_id,
                                target=f2_id,
                                relationship=RelationType.ADJACENT,
                                attributes={
                                    'dihedral_angle': angle,
                                    'angle_type': angle_type.value if angle_type else 'unknown',
                                    'is_convex': is_convex,
                                    'is_concave': is_concave,
                                    'is_tangent': is_tangent,
                                    'shared_edge_id': shared_edge_id
                                }
                            )
                            self.graph.add_edge(adj_edge_1)

                            # Edge from f2 to f1 (same angle, undirected graph)
                            adj_edge_2 = AAGEdge(
                                edge_id=f"{f2_id}_adjacent_{f1_id}",
                                source=f2_id,
                                target=f1_id,
                                relationship=RelationType.ADJACENT,
                                attributes={
                                    'dihedral_angle': angle,
                                    'angle_type': angle_type.value if angle_type else 'unknown',
                                    'is_convex': is_convex,
                                    'is_concave': is_concave,
                                    'is_tangent': is_tangent,
                                    'shared_edge_id': shared_edge_id
                                }
                            )
                            self.graph.add_edge(adj_edge_2)

        # Edge adjacency via shared vertices (optional, can be expensive)
        # For now, we skip this to keep the graph size manageable

    def _establish_geometric_relationships(self) -> None:
        """
        Establish geometric relationships like coplanarity.
        This is optional and can be expensive, so we only do it for planar faces.
        """
        planar_faces = [
            node for node in self.graph.get_nodes_by_type(TopologyType.FACE)
            if node.attributes.get('surface_type') == SurfaceType.PLANE
        ]

        # Check coplanarity for adjacent planar faces
        for face_node in planar_faces:
            # Get adjacent faces
            adjacent_faces = self.graph.get_neighbors(face_node.node_id, RelationType.ADJACENT)

            for adj_face in adjacent_faces:
                if adj_face.attributes.get('surface_type') != SurfaceType.PLANE:
                    continue

                # Check if coplanar
                try:
                    face1 = face_node.occt_entity
                    face2 = adj_face.occt_entity

                    if AttributeComputer.are_faces_coplanar(face1, face2):
                        # Create coplanar relationship
                        coplanar_edge = AAGEdge(
                            edge_id=f"{face_node.node_id}_coplanar_{adj_face.node_id}",
                            source=face_node.node_id,
                            target=adj_face.node_id,
                            relationship=RelationType.COPLANAR
                        )
                        self.graph.add_edge(coplanar_edge)
                except Exception as e:
                    logger.debug(f"Failed to check coplanarity: {e}")
                    continue
