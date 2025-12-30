"""
Face normal vector computation and analysis.

Normal vectors are fundamental for:
- Feature orientation determination
- Dihedral angle computation
- Coplanarity checks
- Surface classification
"""

from OCC.Core.TopoDS import TopoDS_Face
from OCC.Core.gp import gp_Vec, gp_Pnt
import math

from app.core.topology.attributes import AttributeComputer


class NormalAnalyzer:
    """
    Analyzer for face normal vectors and related geometric properties.
    """

    @staticmethod
    def compute_normal(face: TopoDS_Face, u: float = 0.5, v: float = 0.5) -> gp_Vec:
        """
        Compute normal vector at UV parameter on face.

        Args:
            face: Face to analyze
            u: U parameter (0.0 to 1.0, default center)
            v: V parameter (0.0 to 1.0, default center)

        Returns:
            Normal vector at UV point
        """
        return AttributeComputer._compute_face_normal(face, u, v)

    @staticmethod
    def are_normals_parallel(normal1: gp_Vec, normal2: gp_Vec, tolerance: float = 1e-6) -> bool:
        """
        Check if two normal vectors are parallel.

        Args:
            normal1: First normal vector
            normal2: Second normal vector
            tolerance: Tolerance for parallel check

        Returns:
            True if normals are parallel (same or opposite direction)
        """
        # Normalize vectors
        n1 = gp_Vec(normal1)
        n2 = gp_Vec(normal2)

        mag1 = n1.Magnitude()
        mag2 = n2.Magnitude()

        if mag1 < tolerance or mag2 < tolerance:
            return False

        n1.Divide(mag1)
        n2.Divide(mag2)

        # Check dot product (1 for same direction, -1 for opposite)
        dot = n1.Dot(n2)

        return abs(abs(dot) - 1.0) < tolerance

    @staticmethod
    def are_normals_same_direction(normal1: gp_Vec, normal2: gp_Vec, tolerance: float = 1e-6) -> bool:
        """
        Check if two normals point in the same direction.

        Args:
            normal1: First normal vector
            normal2: Second normal vector
            tolerance: Tolerance for comparison

        Returns:
            True if normals point in same direction
        """
        n1 = gp_Vec(normal1)
        n2 = gp_Vec(normal2)

        mag1 = n1.Magnitude()
        mag2 = n2.Magnitude()

        if mag1 < tolerance or mag2 < tolerance:
            return False

        n1.Divide(mag1)
        n2.Divide(mag2)

        dot = n1.Dot(n2)

        return dot > (1.0 - tolerance)

    @staticmethod
    def are_normals_opposite(normal1: gp_Vec, normal2: gp_Vec, tolerance: float = 1e-6) -> bool:
        """
        Check if two normals point in opposite directions.

        Args:
            normal1: First normal vector
            normal2: Second normal vector
            tolerance: Tolerance for comparison

        Returns:
            True if normals point in opposite directions
        """
        n1 = gp_Vec(normal1)
        n2 = gp_Vec(normal2)

        mag1 = n1.Magnitude()
        mag2 = n2.Magnitude()

        if mag1 < tolerance or mag2 < tolerance:
            return False

        n1.Divide(mag1)
        n2.Divide(mag2)

        dot = n1.Dot(n2)

        return dot < -(1.0 - tolerance)

    @staticmethod
    def compute_angle_between_normals(normal1: gp_Vec, normal2: gp_Vec) -> float:
        """
        Compute angle between two normal vectors.

        Args:
            normal1: First normal vector
            normal2: Second normal vector

        Returns:
            Angle in degrees (0-180)
        """
        mag1 = normal1.Magnitude()
        mag2 = normal2.Magnitude()

        if mag1 < 1e-10 or mag2 < 1e-10:
            return 0.0

        dot = normal1.Dot(normal2)
        cos_angle = max(-1.0, min(1.0, dot / (mag1 * mag2)))

        angle_rad = math.acos(cos_angle)
        return math.degrees(angle_rad)

    @staticmethod
    def is_coplanar(face1: TopoDS_Face, face2: TopoDS_Face, tolerance: float = 1e-6) -> bool:
        """
        Check if two faces are coplanar.

        Args:
            face1: First face
            face2: Second face
            tolerance: Tolerance for coplanarity check

        Returns:
            True if faces are coplanar
        """
        return AttributeComputer.are_faces_coplanar(face1, face2, tolerance)

    @staticmethod
    def normalize_vector(vec: gp_Vec) -> gp_Vec:
        """
        Normalize a vector to unit length.

        Args:
            vec: Vector to normalize

        Returns:
            Normalized vector
        """
        normalized = gp_Vec(vec)
        mag = normalized.Magnitude()

        if mag > 1e-10:
            normalized.Divide(mag)

        return normalized

    @staticmethod
    def compute_cross_product(vec1: gp_Vec, vec2: gp_Vec) -> gp_Vec:
        """
        Compute cross product of two vectors.

        Args:
            vec1: First vector
            vec2: Second vector

        Returns:
            Cross product vector
        """
        result = vec1.Crossed(vec2)
        return result

    @staticmethod
    def compute_dot_product(vec1: gp_Vec, vec2: gp_Vec) -> float:
        """
        Compute dot product of two vectors.

        Args:
            vec1: First vector
            vec2: Second vector

        Returns:
            Dot product (scalar)
        """
        return vec1.Dot(vec2)
