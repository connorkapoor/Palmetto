"""
Dihedral angle computation and classification.

Dihedral angles are used to classify edges as convex, concave, or tangent,
which is essential for feature recognition (e.g., distinguishing holes from shafts).
"""

from enum import Enum
import math

from OCC.Core.TopoDS import TopoDS_Face, TopoDS_Edge
from OCC.Core.gp import gp_Vec, gp_Pnt

from app.core.topology.attributes import AttributeComputer


class AngleType(Enum):
    """Classification of dihedral angles."""
    CONVEX = "convex"      # Angle > 180° (outward edge)
    CONCAVE = "concave"    # Angle < 180° (inward edge)
    TANGENT = "tangent"    # Angle ≈ 180° (smooth transition)
    SHARP = "sharp"        # Angle ≈ 0° or 360° (sharp edge)


class DihedralAnalyzer:
    """
    Analyzer for dihedral angles between adjacent faces.

    Dihedral angle is the angle between the normal vectors of two faces
    sharing an edge. Used to classify edges and detect features.
    """

    @staticmethod
    def compute_angle(face1: TopoDS_Face, face2: TopoDS_Face, shared_edge: TopoDS_Edge = None) -> float:
        """
        Compute SIGNED dihedral angle following Analysis Situs methodology.

        Returns angle in degrees [-180, 180]:
        - Negative angle: CONVEX (material addition, shaft/boss)
        - Positive angle: CONCAVE (material removal, hole/pocket)
        - ~0°: Sharp edge
        - ~±180°: Smooth/tangent edge

        This follows Analysis Situs asiAlgo_CheckDihedralAngle exactly:
          angleRad = TF.AngleWithRef(TG, Ref);
          if ( angleRad < 0 ) → CONVEX
          else → CONCAVE

        Args:
            face1: First face
            face2: Second face
            shared_edge: Shared edge between faces (required)

        Returns:
            SIGNED angle in degrees [-180, 180]
        """
        import logging
        logger = logging.getLogger(__name__)

        if shared_edge is None:
            logger.warning("Dihedral angle requires shared edge, returning 0")
            return 0.0

        from app.core.occt_imports import (
            BRepAdaptor_Curve, BRep_Tool, GeomAPI_ProjectPointOnSurf,
            GeomLProp_SLProps, TopAbs_REVERSED, gp_Pnt, gp_Vec
        )

        try:
            # Get edge curve and midpoint
            curve_adaptor = BRepAdaptor_Curve(shared_edge)
            first_param = curve_adaptor.FirstParameter()
            last_param = curve_adaptor.LastParameter()
            mid_param = (first_param + last_param) / 2.0

            # Get two points along edge for reference direction
            param_step = (last_param - first_param) * 0.01
            A_param = mid_param - param_step
            B_param = mid_param + param_step
            A = curve_adaptor.Value(A_param)
            B = curve_adaptor.Value(B_param)

            # Vx: edge direction (vector from A to B)
            Vx = gp_Vec(A, B)
            if Vx.Magnitude() < 1e-10:
                return 0.0

            # Get normal and tangent for face1
            surf1 = BRep_Tool.Surface(face1)
            projector1 = GeomAPI_ProjectPointOnSurf(A, surf1)
            if projector1.NbPoints() == 0:
                return 0.0
            u1, v1 = projector1.Parameters(1)

            props1 = GeomLProp_SLProps(surf1, u1, v1, 1, 1e-6)
            if not props1.IsNormalDefined():
                return 0.0
            N1 = gp_Vec(props1.Normal())
            if face1.Orientation() == TopAbs_REVERSED:
                N1.Reverse()

            # TF: in-plane tangent for face1
            Vy1 = N1.Crossed(Vx)
            if Vy1.Magnitude() < 1e-10:
                return 0.0
            TF = Vy1.Normalized()

            # Ref: reference direction
            Ref = Vx.Normalized()

            # Get normal and tangent for face2
            surf2 = BRep_Tool.Surface(face2)
            projector2 = GeomAPI_ProjectPointOnSurf(A, surf2)
            if projector2.NbPoints() == 0:
                return 0.0
            u2, v2 = projector2.Parameters(1)

            props2 = GeomLProp_SLProps(surf2, u2, v2, 1, 1e-6)
            if not props2.IsNormalDefined():
                return 0.0
            N2 = gp_Vec(props2.Normal())
            if face2.Orientation() == TopAbs_REVERSED:
                N2.Reverse()

            # TG: in-plane tangent for face2
            Vy2 = N2.Crossed(Vx)
            if Vy2.Magnitude() < 1e-10:
                return 0.0
            TG = Vy2.Normalized()

            # Compute SIGNED angle (Analysis Situs: TF.AngleWithRef(TG, Ref))
            # This returns angle in [-π, π]
            angle_rad = TF.AngleWithRef(TG, Ref)
            angle_deg = math.degrees(angle_rad)

            return angle_deg

        except Exception as e:
            logger.warning(f"Dihedral angle computation failed: {e}")
            return 0.0

    @staticmethod
    def _get_normal_at_point(face: TopoDS_Face, point: gp_Pnt) -> gp_Vec:
        """
        Get face normal at a specific 3D point.
        Projects point onto surface to find UV, then computes normal.

        Args:
            face: Face to analyze
            point: 3D point on or near the face

        Returns:
            Normal vector at that point
        """
        import logging
        logger = logging.getLogger(__name__)

        from app.core.occt_imports import (
            BRep_Tool, GeomAPI_ProjectPointOnSurf, GeomLProp_SLProps,
            TopAbs_REVERSED, gp_Vec
        )

        try:
            # Get surface
            geom_surface = BRep_Tool.Surface(face)

            if geom_surface is None:
                logger.warning("Could not get surface from face, using center normal")
                return AttributeComputer._compute_face_normal(face, 0.5, 0.5)

            # Project point onto surface
            projector = GeomAPI_ProjectPointOnSurf(point, geom_surface)

            if projector.NbPoints() == 0:
                # Fallback to center normal
                logger.warning("Could not project point to surface, using center normal")
                return AttributeComputer._compute_face_normal(face, 0.5, 0.5)

            u, v = projector.Parameters(1)  # Get UV of closest point

            # Compute normal at UV
            props = GeomLProp_SLProps(geom_surface, u, v, 1, 1e-6)

            if not props.IsNormalDefined():
                logger.warning("Normal not defined at projected point")
                return gp_Vec(0, 0, 1)

            normal = props.Normal()

            # Account for face orientation
            if face.Orientation() == TopAbs_REVERSED:
                normal.Reverse()

            return gp_Vec(normal.X(), normal.Y(), normal.Z())

        except Exception as e:
            logger.warning(f"Failed to get normal at point: {e}, using center normal")
            return AttributeComputer._compute_face_normal(face, 0.5, 0.5)

    @staticmethod
    def _compute_angle_at_centers(face1: TopoDS_Face, face2: TopoDS_Face) -> float:
        """
        Fallback: Compute angle using face center normals.
        Less accurate but works when shared edge is unknown.

        Args:
            face1: First face
            face2: Second face

        Returns:
            Angle in degrees (0-180)
        """
        normal1 = AttributeComputer._compute_face_normal(face1, 0.5, 0.5)
        normal2 = AttributeComputer._compute_face_normal(face2, 0.5, 0.5)

        dot = normal1.Dot(normal2)
        magnitude = normal1.Magnitude() * normal2.Magnitude()

        if magnitude < 1e-10:
            return 180.0

        cos_angle = max(-1.0, min(1.0, dot / magnitude))
        angle_deg = math.degrees(math.acos(cos_angle))

        return angle_deg

    @staticmethod
    def classify_angle(angle: float, smooth_tolerance: float = 3.0) -> AngleType:
        """
        Classify SIGNED dihedral angle following Analysis Situs methodology.

        Args:
            angle: SIGNED angle in degrees [-180, 180]
            smooth_tolerance: Tolerance for smooth/tangent classification (default 3°)

        Returns:
            AngleType classification

        Classification (Analysis Situs):
            - angle < 0: CONVEX (material addition)
            - angle > 0: CONCAVE (material removal)
            - |angle| ≈ 180°: TANGENT (smooth transition)
        """
        abs_angle = abs(angle)

        # Check if smooth (~180° angle)
        if abs_angle > (180.0 - smooth_tolerance):
            return AngleType.TANGENT

        # Negative = convex, Positive = concave
        if angle < 0:
            return AngleType.CONVEX
        else:
            return AngleType.CONCAVE

    @staticmethod
    def is_convex(angle: float, smooth_tolerance: float = 3.0) -> bool:
        """
        Check if angle indicates a convex edge (protrusion, shaft).

        Following Analysis Situs: angleRad < 0 → CONVEX

        Args:
            angle: SIGNED dihedral angle in degrees [-180, 180]
            smooth_tolerance: Tolerance for smooth edge classification

        Returns:
            True if edge is convex (angle < 0 and not smooth)
        """
        abs_angle = abs(angle)
        # Not smooth and negative
        return angle < 0 and abs_angle < (180.0 - smooth_tolerance)

    @staticmethod
    def is_concave(angle: float, smooth_tolerance: float = 3.0) -> bool:
        """
        Check if angle indicates a concave edge (depression, hole).

        Following Analysis Situs: angleRad > 0 → CONCAVE

        Args:
            angle: SIGNED dihedral angle in degrees [-180, 180]
            smooth_tolerance: Tolerance for smooth edge classification

        Returns:
            True if edge is concave (angle > 0 and not smooth)
        """
        abs_angle = abs(angle)
        # Not smooth and positive
        return angle > 0 and abs_angle < (180.0 - smooth_tolerance)

    @staticmethod
    def is_tangent(angle: float, tolerance: float = 10.0) -> bool:
        """
        Check if angle indicates a tangent (smooth) edge.

        Args:
            angle: Dihedral angle in degrees
            tolerance: Tolerance around 180° for tangent classification

        Returns:
            True if edge is tangent (angle ≈ 180°)
        """
        # Tangent edges are around 180° (175-185° by default)
        return abs(angle - 180.0) < tolerance

    @staticmethod
    def angle_to_radians(angle_deg: float) -> float:
        """Convert angle from degrees to radians."""
        return math.radians(angle_deg)

    @staticmethod
    def angle_to_degrees(angle_rad: float) -> float:
        """Convert angle from radians to degrees."""
        return math.degrees(angle_rad)
