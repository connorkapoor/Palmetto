"""
B-Rep to mesh tessellation.

Converts B-Rep shapes to triangulated meshes while maintaining
the mapping between faces and their corresponding triangles.
This mapping is essential for face-level highlighting in the frontend.
"""

from typing import Dict, List, Tuple
import logging
import numpy as np

from app.core.occt_imports import (
    TopoDS_Shape, TopoDS_Face, topods,
    TopExp_Explorer, TopAbs_FACE,
    BRepMesh_IncrementalMesh, BRep_Tool, TopLoc_Location,
    PYTHONOCC_AVAILABLE
)

logger = logging.getLogger(__name__)


class Tessellator:
    """
    Tessellates B-Rep shapes to triangle meshes.

    Performs incremental mesh tessellation and builds the crucial
    face_map that links each face to its triangles for frontend highlighting.
    """

    def __init__(
        self,
        shape: TopoDS_Shape,
        linear_deflection: float = 0.1,
        angular_deflection: float = 0.5
    ):
        """
        Initialize tessellator.

        Args:
            shape: B-Rep shape to tessellate
            linear_deflection: Maximum distance between surface and triangulation
            angular_deflection: Maximum angle between adjacent triangle normals (radians)
        """
        self.shape = shape
        self.linear_deflection = linear_deflection
        self.angular_deflection = angular_deflection

    def tessellate(self) -> Tuple[np.ndarray, np.ndarray, Dict[str, List[int]]]:
        """
        Tessellate the B-Rep shape.

        Returns:
            Tuple of:
            - vertices: (N, 3) array of vertex positions
            - triangles: (M, 3) array of triangle indices
            - face_map: {face_id: [triangle_indices]}

        The face_map is critical - it enables the frontend to highlight
        specific faces by selecting their corresponding triangles.
        """
        logger.info(f"Tessellating shape (linear_def={self.linear_deflection}, "
                   f"angular_def={self.angular_deflection})")

        # Perform incremental mesh
        mesh = BRepMesh_IncrementalMesh(
            self.shape,
            self.linear_deflection,
            False,  # Not relative
            self.angular_deflection,
            True   # In parallel
        )
        mesh.Perform()

        if not mesh.IsDone():
            logger.warning("Mesh computation did not complete successfully")

        vertices_list = []
        triangles_list = []
        face_map = {}

        vertex_offset = 0  # Global vertex index offset

        # Iterate over faces
        explorer = TopExp_Explorer(self.shape, TopAbs_FACE)
        face_index = 0

        while explorer.More():
            face = topods.Face(explorer.Current())
            face_id = f"face_{face_index}"

            # Get triangulation for this face
            location = TopLoc_Location()
            triangulation = BRep_Tool.Triangulation(face, location)

            if triangulation:
                # Extract vertices from this face
                face_triangle_indices = []

                # Add vertices
                transformation = location.Transformation()
                for i in range(1, triangulation.NbNodes() + 1):
                    pnt = triangulation.Node(i)

                    # Apply transformation
                    pnt.Transform(transformation)

                    vertices_list.append([pnt.X(), pnt.Y(), pnt.Z()])

                # Extract triangles
                for i in range(1, triangulation.NbTriangles() + 1):
                    tri = triangulation.Triangle(i)
                    v1, v2, v3 = tri.Get()

                    # Adjust indices for global vertex array
                    # OCC indices are 1-based, convert to 0-based
                    global_v1 = vertex_offset + v1 - 1
                    global_v2 = vertex_offset + v2 - 1
                    global_v3 = vertex_offset + v3 - 1

                    # Check face orientation to ensure correct winding
                    if face.Orientation() == 1:  # Reversed
                        # Swap v2 and v3 to reverse winding
                        triangles_list.append([global_v1, global_v3, global_v2])
                    else:
                        triangles_list.append([global_v1, global_v2, global_v3])

                    # Record which triangle belongs to this face
                    triangle_index = len(triangles_list) - 1
                    face_triangle_indices.append(triangle_index)

                # Store face mapping
                face_map[face_id] = face_triangle_indices

                # Update offset for next face
                vertex_offset += triangulation.NbNodes()

            else:
                logger.warning(f"No triangulation for {face_id}")
                face_map[face_id] = []

            face_index += 1
            explorer.Next()

        # Convert to numpy arrays
        vertices = np.array(vertices_list, dtype=np.float32)
        triangles = np.array(triangles_list, dtype=np.uint32)

        logger.info(f"Tessellation complete: {len(vertices)} vertices, "
                   f"{len(triangles)} triangles, {len(face_map)} faces")

        return vertices, triangles, face_map

    def get_mesh_statistics(
        self,
        vertices: np.ndarray,
        triangles: np.ndarray,
        face_map: Dict[str, List[int]]
    ) -> Dict[str, any]:
        """
        Compute statistics about the tessellated mesh.

        Args:
            vertices: Vertex array
            triangles: Triangle array
            face_map: Face mapping

        Returns:
            Dictionary with mesh statistics
        """
        # Compute bounding box
        if len(vertices) > 0:
            bbox_min = vertices.min(axis=0)
            bbox_max = vertices.max(axis=0)
            bbox_size = bbox_max - bbox_min
        else:
            bbox_min = bbox_max = bbox_size = np.zeros(3)

        # Triangles per face stats
        triangles_per_face = [len(tris) for tris in face_map.values()]
        avg_tris_per_face = np.mean(triangles_per_face) if triangles_per_face else 0

        return {
            'vertex_count': len(vertices),
            'triangle_count': len(triangles),
            'face_count': len(face_map),
            'bounding_box_min': bbox_min.tolist(),
            'bounding_box_max': bbox_max.tolist(),
            'bounding_box_size': bbox_size.tolist(),
            'average_triangles_per_face': float(avg_tris_per_face),
            'min_triangles_per_face': min(triangles_per_face) if triangles_per_face else 0,
            'max_triangles_per_face': max(triangles_per_face) if triangles_per_face else 0
        }
