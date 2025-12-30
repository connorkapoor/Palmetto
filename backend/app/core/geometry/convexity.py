"""
Vertex convexity analysis.

Analyzes the local curvature at vertices to classify them as:
- Convex: vertex protrudes outward
- Concave: vertex caves inward
- Saddle: mixed curvature
- Planar: lies on a plane
"""

from typing import List
from OCC.Core.TopoDS import TopoDS_Vertex, TopoDS_Edge
from OCC.Core.gp import gp_Vec, gp_Pnt
from OCC.Core.BRep import BRep_Tool

from app.core.topology.attributes import ConvexityType


class ConvexityAnalyzer:
    """
    Analyzer for vertex convexity based on adjacent edges.

    Convexity is determined by analyzing the angles between
    edges meeting at a vertex and their tangent vectors.
    """

    @staticmethod
    def compute_vertex_convexity(
        vertex: TopoDS_Vertex,
        adjacent_edges: List[TopoDS_Edge]
    ) -> ConvexityType:
        """
        Determine convexity of a vertex based on adjacent edges.

        Args:
            vertex: Vertex to analyze
            adjacent_edges: List of edges connected to the vertex

        Returns:
            ConvexityType classification

        Note:
            This is a simplified implementation. A complete implementation
            would analyze the local surface curvature and edge angles.
        """
        if len(adjacent_edges) < 2:
            return ConvexityType.PLANAR

        # Get vertex point
        vertex_point = BRep_Tool.Pnt(vertex)

        # Analyze edge tangent vectors at the vertex
        tangents = []

        for edge in adjacent_edges:
            try:
                # Get edge curve
                curve, first, last = BRep_Tool.Curve(edge)

                if curve is None:
                    continue

                # Determine if vertex is at first or last parameter
                first_pnt = curve.Value(first)
                last_pnt = curve.Value(last)

                dist_to_first = vertex_point.Distance(first_pnt)
                dist_to_last = vertex_point.Distance(last_pnt)

                # Get tangent at vertex
                if dist_to_first < dist_to_last:
                    # Vertex is at start
                    param = first
                else:
                    # Vertex is at end
                    param = last

                # Compute tangent
                pnt = gp_Pnt()
                tangent = gp_Vec()
                curve.D1(param, pnt, tangent)

                # Ensure tangent points away from vertex
                if dist_to_first < dist_to_last:
                    # Already pointing away
                    pass
                else:
                    # Reverse to point away
                    tangent.Reverse()

                tangents.append(tangent)

            except Exception:
                continue

        if len(tangents) < 2:
            return ConvexityType.PLANAR

        # Analyze tangent angles
        # Simple heuristic: check average angle between tangent pairs
        total_angle = 0.0
        count = 0

        for i in range(len(tangents)):
            for j in range(i + 1, len(tangents)):
                angle = tangents[i].Angle(tangents[j])
                total_angle += angle
                count += 1

        if count == 0:
            return ConvexityType.PLANAR

        avg_angle = total_angle / count

        # Classification based on average angle
        # This is a simplified heuristic
        import math
        angle_deg = math.degrees(avg_angle)

        if angle_deg < 60:
            return ConvexityType.CONVEX
        elif angle_deg > 120:
            return ConvexityType.CONCAVE
        else:
            return ConvexityType.SADDLE

    @staticmethod
    def is_convex_vertex(vertex: TopoDS_Vertex, adjacent_edges: List[TopoDS_Edge]) -> bool:
        """
        Check if vertex is convex.

        Args:
            vertex: Vertex to check
            adjacent_edges: Adjacent edges

        Returns:
            True if vertex is convex
        """
        convexity = ConvexityAnalyzer.compute_vertex_convexity(vertex, adjacent_edges)
        return convexity == ConvexityType.CONVEX

    @staticmethod
    def is_concave_vertex(vertex: TopoDS_Vertex, adjacent_edges: List[TopoDS_Edge]) -> bool:
        """
        Check if vertex is concave.

        Args:
            vertex: Vertex to check
            adjacent_edges: Adjacent edges

        Returns:
            True if vertex is concave
        """
        convexity = ConvexityAnalyzer.compute_vertex_convexity(vertex, adjacent_edges)
        return convexity == ConvexityType.CONCAVE

    @staticmethod
    def is_saddle_vertex(vertex: TopoDS_Vertex, adjacent_edges: List[TopoDS_Edge]) -> bool:
        """
        Check if vertex is a saddle point.

        Args:
            vertex: Vertex to check
            adjacent_edges: Adjacent edges

        Returns:
            True if vertex is a saddle point
        """
        convexity = ConvexityAnalyzer.compute_vertex_convexity(vertex, adjacent_edges)
        return convexity == ConvexityType.SADDLE
