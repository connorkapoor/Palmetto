"""
Geometric attribute computation for topological entities.

Computes and stores geometric properties such as:
- Face: normal, area, surface type, center of mass, curvature
- Edge: curve type, length, endpoints, tangent
- Vertex: point coordinates, convexity
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple
import math

from app.core.occt_imports import (
    TopoDS_Face, TopoDS_Edge, TopoDS_Vertex, BRep_Tool, GProp_GProps,
    brepgprop_SurfaceProperties, brepgprop_LinearProperties,
    gp_Pnt, gp_Vec, gp_Dir,
    GeomAbs_Plane, GeomAbs_Cylinder, GeomAbs_Cone, GeomAbs_Sphere,
    GeomAbs_Torus, GeomAbs_BSplineSurface, GeomAbs_BezierSurface,
    GeomAbs_SurfaceOfRevolution, GeomAbs_SurfaceOfExtrusion,
    GeomAbs_Line, GeomAbs_Circle, GeomAbs_Ellipse, GeomAbs_Parabola,
    GeomAbs_Hyperbola, GeomAbs_BSplineCurve, GeomAbs_BezierCurve,
    BRepAdaptor_Surface, BRepAdaptor_Curve, GeomLProp_SLProps,
    PYTHONOCC_AVAILABLE
)


class SurfaceType(Enum):
    """Types of surfaces in B-Rep geometry."""
    PLANE = "plane"
    CYLINDER = "cylinder"
    CONE = "cone"
    SPHERE = "sphere"
    TORUS = "torus"
    BSPLINE = "bspline"
    BEZIER = "bezier"
    REVOLUTION = "revolution"
    EXTRUSION = "extrusion"
    OTHER = "other"


class CurveType(Enum):
    """Types of curves in B-Rep geometry."""
    LINE = "line"
    CIRCLE = "circle"
    ELLIPSE = "ellipse"
    PARABOLA = "parabola"
    HYPERBOLA = "hyperbola"
    BSPLINE = "bspline"
    BEZIER = "bezier"
    OTHER = "other"


class ConvexityType(Enum):
    """Vertex convexity classification."""
    CONVEX = "convex"
    CONCAVE = "concave"
    SADDLE = "saddle"
    PLANAR = "planar"


@dataclass
class FaceAttributes:
    """Geometric attributes for a face."""
    normal: gp_Vec
    area: float
    surface_type: SurfaceType
    center_of_mass: gp_Pnt
    curvature: Optional[float] = None
    # Surface-specific attributes
    radius: Optional[float] = None  # For cylinder, sphere, cone
    axis: Optional[gp_Dir] = None   # For cylinder, cone
    apex: Optional[gp_Pnt] = None   # For cone
    plane_normal: Optional[gp_Dir] = None  # For plane


@dataclass
class EdgeAttributes:
    """Geometric attributes for an edge."""
    curve_type: CurveType
    length: float
    first_point: gp_Pnt
    last_point: gp_Pnt
    tangent: gp_Vec
    # Curve-specific attributes
    radius: Optional[float] = None  # For circle, ellipse
    center: Optional[gp_Pnt] = None  # For circle, ellipse
    axis: Optional[gp_Dir] = None    # For circle


@dataclass
class VertexAttributes:
    """Geometric attributes for a vertex."""
    point: gp_Pnt
    convexity: Optional[ConvexityType] = None
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    def __post_init__(self):
        """Extract coordinates from point."""
        self.x = self.point.X()
        self.y = self.point.Y()
        self.z = self.point.Z()


class AttributeComputer:
    """
    Computes geometric attributes from OpenCASCADE entities.
    Static methods for computing properties of faces, edges, and vertices.
    """

    @staticmethod
    def compute_face_attributes(face: TopoDS_Face) -> FaceAttributes:
        """
        Compute geometric attributes for a face.

        Args:
            face: TopoDS_Face to analyze

        Returns:
            FaceAttributes with computed properties
        """
        # Get surface properties
        from app.core.occt_imports import brepgprop
        props = GProp_GProps()
        brepgprop.SurfaceProperties(face, props)

        area = props.Mass()
        center = props.CentreOfMass()

        # Get surface adaptor
        surface = BRepAdaptor_Surface(face)
        surface_type = AttributeComputer._classify_surface(surface)

        # Compute normal at center (UV = 0.5, 0.5)
        normal = AttributeComputer._compute_face_normal(face, 0.5, 0.5)

        # Surface-specific attributes
        radius = None
        axis = None
        apex = None
        plane_normal = None
        curvature = None

        if surface_type == SurfaceType.CYLINDER:
            cylinder = surface.Cylinder()
            radius = cylinder.Radius()
            axis = cylinder.Axis().Direction()

        elif surface_type == SurfaceType.SPHERE:
            sphere = surface.Sphere()
            radius = sphere.Radius()
            curvature = 1.0 / radius if radius > 0 else None

        elif surface_type == SurfaceType.CONE:
            cone = surface.Cone()
            radius = cone.RefRadius()
            axis = cone.Axis().Direction()
            apex = cone.Apex()

        elif surface_type == SurfaceType.TORUS:
            torus = surface.Torus()
            radius = torus.MinorRadius()
            curvature = 1.0 / radius if radius > 0 else None

        elif surface_type == SurfaceType.PLANE:
            plane = surface.Plane()
            plane_normal = plane.Axis().Direction()

        return FaceAttributes(
            normal=normal,
            area=area,
            surface_type=surface_type,
            center_of_mass=center,
            curvature=curvature,
            radius=radius,
            axis=axis,
            apex=apex,
            plane_normal=plane_normal
        )

    @staticmethod
    def compute_edge_attributes(edge: TopoDS_Edge) -> EdgeAttributes:
        """
        Compute geometric attributes for an edge.

        Args:
            edge: TopoDS_Edge to analyze

        Returns:
            EdgeAttributes with computed properties
        """
        # Get curve properties
        from app.core.occt_imports import brepgprop
        props = GProp_GProps()
        brepgprop.LinearProperties(edge, props)

        length = props.Mass()

        # Get curve adaptor
        curve_adaptor = BRepAdaptor_Curve(edge)
        curve_type = AttributeComputer._classify_curve(curve_adaptor)

        # Get endpoints
        first_param = curve_adaptor.FirstParameter()
        last_param = curve_adaptor.LastParameter()
        first_point = curve_adaptor.Value(first_param)
        last_point = curve_adaptor.Value(last_param)

        # Get tangent at mid-parameter
        mid_param = (first_param + last_param) / 2.0
        tangent = gp_Vec()
        curve_adaptor.D1(mid_param, gp_Pnt(), tangent)

        # Curve-specific attributes
        radius = None
        center = None
        axis = None

        if curve_type == CurveType.CIRCLE:
            circle = curve_adaptor.Circle()
            radius = circle.Radius()
            center = circle.Location()
            axis = circle.Axis().Direction()

        elif curve_type == CurveType.ELLIPSE:
            ellipse = curve_adaptor.Ellipse()
            radius = ellipse.MajorRadius()
            center = ellipse.Location()

        return EdgeAttributes(
            curve_type=curve_type,
            length=length,
            first_point=first_point,
            last_point=last_point,
            tangent=tangent,
            radius=radius,
            center=center,
            axis=axis
        )

    @staticmethod
    def compute_vertex_attributes(vertex: TopoDS_Vertex) -> VertexAttributes:
        """
        Compute geometric attributes for a vertex.

        Args:
            vertex: TopoDS_Vertex to analyze

        Returns:
            VertexAttributes with computed properties
        """
        point = BRep_Tool.Pnt(vertex)

        return VertexAttributes(
            point=point,
            convexity=None  # Computed later based on adjacent edges
        )

    @staticmethod
    def _classify_surface(surface: BRepAdaptor_Surface) -> SurfaceType:
        """Classify surface type using GeomAbs enumeration."""
        surface_geom_type = surface.GetType()

        mapping = {
            GeomAbs_Plane: SurfaceType.PLANE,
            GeomAbs_Cylinder: SurfaceType.CYLINDER,
            GeomAbs_Cone: SurfaceType.CONE,
            GeomAbs_Sphere: SurfaceType.SPHERE,
            GeomAbs_Torus: SurfaceType.TORUS,
            GeomAbs_BSplineSurface: SurfaceType.BSPLINE,
            GeomAbs_BezierSurface: SurfaceType.BEZIER,
            GeomAbs_SurfaceOfRevolution: SurfaceType.REVOLUTION,
            GeomAbs_SurfaceOfExtrusion: SurfaceType.EXTRUSION,
        }

        return mapping.get(surface_geom_type, SurfaceType.OTHER)

    @staticmethod
    def _classify_curve(curve: BRepAdaptor_Curve) -> CurveType:
        """Classify curve type using GeomAbs enumeration."""
        curve_geom_type = curve.GetType()

        mapping = {
            GeomAbs_Line: CurveType.LINE,
            GeomAbs_Circle: CurveType.CIRCLE,
            GeomAbs_Ellipse: CurveType.ELLIPSE,
            GeomAbs_Parabola: CurveType.PARABOLA,
            GeomAbs_Hyperbola: CurveType.HYPERBOLA,
            GeomAbs_BSplineCurve: CurveType.BSPLINE,
            GeomAbs_BezierCurve: CurveType.BEZIER,
        }

        return mapping.get(curve_geom_type, CurveType.OTHER)

    @staticmethod
    def _compute_face_normal(face: TopoDS_Face, u: float = 0.5, v: float = 0.5) -> gp_Vec:
        """
        Compute normal vector at UV parameter on face.

        Args:
            face: Face to analyze
            u: U parameter (0.0 to 1.0)
            v: V parameter (0.0 to 1.0)

        Returns:
            Normal vector at UV point
        """
        surface = BRepAdaptor_Surface(face)

        # Get UV bounds
        u_min = surface.FirstUParameter()
        u_max = surface.LastUParameter()
        v_min = surface.FirstVParameter()
        v_max = surface.LastVParameter()

        # Interpolate UV
        u_param = u_min + u * (u_max - u_min)
        v_param = v_min + v * (v_max - v_min)

        # Compute normal using surface properties
        # Get the underlying Geom_Surface from the BRepAdaptor
        try:
            # Get the geometric surface from the adaptor
            geom_surface = BRep_Tool.Surface(face)

            if geom_surface is None:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Could not get Geom_Surface from face, using fallback")
                return gp_Vec(0, 0, 1)

            # Create surface properties object
            # Constructor: GeomLProp_SLProps(surface_handle, u, v, continuity_order, tolerance)
            props = GeomLProp_SLProps(geom_surface, u_param, v_param, 1, 1e-6)

            if props.IsNormalDefined():
                normal = props.Normal()

                # Check face orientation (Analysis Situs principle)
                # TopAbs_REVERSED means the face normal should be flipped
                from app.core.occt_imports import TopAbs_REVERSED
                if face.Orientation() == TopAbs_REVERSED:
                    normal.Reverse()

                # Return as gp_Vec
                return gp_Vec(normal.X(), normal.Y(), normal.Z())
            else:
                # Fallback: return arbitrary normal
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Normal not defined for face at UV=({u_param:.3f}, {v_param:.3f}), using fallback")
                return gp_Vec(0, 0, 1)
        except Exception as e:
            # If normal computation fails, return default
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Normal computation failed: {e}, using fallback (0,0,1)")
            return gp_Vec(0, 0, 1)

    @staticmethod
    def compute_dihedral_angle(face1: TopoDS_Face, face2: TopoDS_Face) -> float:
        """
        Compute dihedral angle between two faces (in degrees).

        Args:
            face1: First face
            face2: Second face

        Returns:
            Angle in degrees (0-360)
        """
        # Get normals
        normal1 = AttributeComputer._compute_face_normal(face1)
        normal2 = AttributeComputer._compute_face_normal(face2)

        # Compute angle using dot product
        dot = normal1.Dot(normal2)
        magnitude = normal1.Magnitude() * normal2.Magnitude()

        if magnitude < 1e-10:
            return 0.0

        # Clamp to [-1, 1] to avoid numerical errors in acos
        cos_angle = max(-1.0, min(1.0, dot / magnitude))
        angle_rad = math.acos(cos_angle)
        angle_deg = math.degrees(angle_rad)

        return angle_deg

    @staticmethod
    def are_faces_coplanar(face1: TopoDS_Face, face2: TopoDS_Face, tolerance: float = 1e-6) -> bool:
        """
        Check if two faces are coplanar.

        Args:
            face1: First face
            face2: Second face
            tolerance: Tolerance for comparison

        Returns:
            True if faces are coplanar
        """
        attrs1 = AttributeComputer.compute_face_attributes(face1)
        attrs2 = AttributeComputer.compute_face_attributes(face2)

        # Only planes can be coplanar
        if attrs1.surface_type != SurfaceType.PLANE or attrs2.surface_type != SurfaceType.PLANE:
            return False

        # Check if normals are parallel
        angle = AttributeComputer.compute_dihedral_angle(face1, face2)

        # Normals are parallel if angle is 0 or 180 degrees
        return abs(angle) < tolerance or abs(angle - 180.0) < tolerance
