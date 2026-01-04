"""
QueryParser for converting natural language queries to structured queries.

Uses Claude API to parse queries like:
- "show me all faces with area 20mm²"
- "find the largest face"
- "show planar faces"
- "find circular edges with radius 5mm"

Returns StructuredQuery objects for execution by QueryEngine.
"""

import json
import logging
import re
from typing import Dict, Any, Optional, List

import anthropic

from app.config import get_settings
from .query_engine import StructuredQuery, Predicate, Operator

logger = logging.getLogger(__name__)
settings = get_settings()


class QueryParser:
    """
    Parse natural language queries into StructuredQuery objects.

    Uses Claude API for robust parsing with fallback to regex for simple queries.
    """

    def __init__(self, api_key: str = None):
        """
        Initialize QueryParser.

        Args:
            api_key: Optional Anthropic API key (defaults to settings)
        """
        self.api_key = api_key or settings.anthropic_api_key

        if not self.api_key:
            logger.warning("No Anthropic API key configured! Will use fallback parser only.")

        self.client = anthropic.Anthropic(api_key=self.api_key) if self.api_key else None

        # Default tolerance for numeric comparisons
        self.default_tolerance = 0.5

    def parse(
        self,
        query: str,
        aag_schema: Optional[Dict[str, Any]] = None
    ) -> StructuredQuery:
        """
        Parse natural language query into StructuredQuery.

        Args:
            query: User's natural language query
            aag_schema: Optional AAG schema with available attributes

        Returns:
            StructuredQuery object

        Example:
            Input: "show me all faces with area 20mm²"
            Output: StructuredQuery(
                entity_type="face",
                predicates=[Predicate(attribute="area", operator="in_range", value=20.0, tolerance=0.5)]
            )
        """
        if not self.client:
            logger.warning("No Claude API client, using fallback parser")
            return self._fallback_parse(query)

        # Build system prompt with AAG schema
        system_prompt = self._build_system_prompt(aag_schema)

        try:
            # Call Claude API
            message = self.client.messages.create(
                model=settings.claude_model,
                max_tokens=settings.claude_max_tokens,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": query}
                ]
            )

            # Extract response text
            response_text = message.content[0].text

            # Parse JSON response
            result = json.loads(response_text)

            # Convert to StructuredQuery
            structured_query = self._convert_to_structured_query(result)

            logger.info(f"Parsed query: '{query}' → {structured_query.entity_type} with {len(structured_query.predicates)} predicates")

            return structured_query

        except Exception as e:
            logger.error(f"Claude API parsing failed: {e}")
            # Fallback to regex parser
            return self._fallback_parse(query)

    def _build_system_prompt(self, aag_schema: Optional[Dict[str, Any]] = None) -> str:
        """
        Build system prompt with AAG schema and examples.

        Args:
            aag_schema: Optional AAG schema with available attributes

        Returns:
            System prompt string
        """
        schema_info = """
Available entity types:
- face: Surface elements with area, surface_type, normal
- edge: Curve elements with curve_type, length, radius
- vertex: Points with x, y, z coordinates
- shell: Solid volumes

Face attributes:
- area: Surface area in mm²
- surface_type: plane, cylinder, cone, sphere, torus, bspline
- normal: [x, y, z] unit normal vector
- radius: For cylindrical/spherical faces (mm)
- is_internal_cylinder: Boolean - true for internal cylindrical faces (holes), false for external (fillets/bosses)
- is_blend_candidate: Boolean - true if this face is part of a blend/fillet feature
- blend_chain_id: Integer - ID of the blend chain this face belongs to (-1 if not in a chain)
- blend_vexity: String - "concave" for concave blends/fillets, "convex" for convex blends
- smooth_edge_count: Number of smooth edges connecting to other blend faces
- edge_count: Total number of edges bounding this face
- has_full_circle_edges: Boolean - true if face has full circular edges
- has_arc_edges: Boolean - true if face has arc edges
- quarter_circle_edge_count: Number of 90-degree arc edges (typical for fillets)
- semicircle_edge_count: Number of 180-degree arc edges (typical for holes)
- local_thickness: Local wall thickness at face centroid in mm (from ray casting analysis)
- is_thin_wall_face: Boolean - true if this face is part of a thin wall feature
- wall_thickness: Wall thickness for thin wall features in mm
- thickness_variance: Standard deviation of thickness across face (0-1, higher = non-uniform)
- stress_concentration: SDF gradient magnitude (0-1, higher = sharp thickness changes)
- draft_angle: Draft angle in degrees (positive = good for molding, negative = undercut)
- overhang_angle: Overhang angle from horizontal in degrees (>45° requires supports for 3D printing)
- has_undercut: Boolean - true if face has negative draft angle (prevents demolding)

Edge attributes:
- curve_type: line, circle, ellipse, hyperbola, parabola, bezier, bspline
- length: Edge length in mm
- radius: For circular edges and arcs (mm)
- is_arc: Boolean - true for arcs, false for full circles
- is_full_circle: Boolean - true for complete circles
- is_semicircle: Boolean - true for 180-degree arcs
- is_quarter_circle: Boolean - true for 90-degree arcs (common in fillets)
- is_three_quarter_circle: Boolean - true for 270-degree arcs
- arc_angle: Arc angle in degrees (only for arcs) - use for querying specific angles
- center: [x, y, z] center point for circular edges
- start_point: [x, y, z] edge start point
- end_point: [x, y, z] edge end point

Vertex attributes:
- x, y, z: 3D coordinates in mm

Operators:
- eq: Equal (exact match)
- ne: Not equal
- gt: Greater than
- lt: Less than
- gte: Greater than or equal
- lte: Less than or equal
- in_range: Value within tolerance (for approximate numeric matches)
- contains: String contains substring
- in: Value in list
"""

        if aag_schema:
            # TODO: Extract actual schema info when available
            pass

        return f"""You are a CAD geometry query parser. Convert natural language queries into structured database queries for geometric entities.

{schema_info}

Your response MUST be valid JSON with this exact structure:
{{
    "entity_type": "face|edge|vertex|shell",
    "predicates": [
        {{
            "attribute": "attribute_name",
            "operator": "eq|ne|gt|lt|gte|lte|in_range|contains|in",
            "value": value,
            "tolerance": 0.5  // Optional, only for in_range
        }}
    ],
    "sort_by": "attribute_name",  // Optional
    "order": "asc|desc",  // Optional
    "limit": 10  // Optional
}}

Query parsing rules:
1. Numeric values with units should use "in_range" operator with tolerance=0.5 by default
   Example: "20mm²" → {{"operator": "in_range", "value": 20.0, "tolerance": 0.5}}

2. Exact comparisons use "eq", "gt", "lt", etc.
   Example: "larger than 50mm" → {{"operator": "gt", "value": 50.0}}

3. Superlatives (largest, smallest) use sort + limit
   Example: "largest face" → {{"sort_by": "area", "order": "desc", "limit": 1}}

4. Type filters check specific attribute values
   Example: "planar faces" → {{"attribute": "surface_type", "operator": "eq", "value": "plane"}}

5. Multiple conditions create multiple predicates
   Example: "faces with area > 20 and surface_type = plane" → Two predicates

Example queries:

User: "show me all faces with area 20mm²"
Assistant: {{
    "entity_type": "face",
    "predicates": [
        {{"attribute": "area", "operator": "in_range", "value": 20.0, "tolerance": 0.5}}
    ]
}}

User: "find the largest face"
Assistant: {{
    "entity_type": "face",
    "predicates": [],
    "sort_by": "area",
    "order": "desc",
    "limit": 1
}}

User: "show planar faces"
Assistant: {{
    "entity_type": "face",
    "predicates": [
        {{"attribute": "surface_type", "operator": "eq", "value": "plane"}}
    ]
}}

User: "find circular edges with radius 5mm"
Assistant: {{
    "entity_type": "edge",
    "predicates": [
        {{"attribute": "curve_type", "operator": "eq", "value": "circle"}},
        {{"attribute": "radius", "operator": "in_range", "value": 5.0, "tolerance": 0.5}}
    ]
}}

User: "edges longer than 50mm"
Assistant: {{
    "entity_type": "edge",
    "predicates": [
        {{"attribute": "length", "operator": "gt", "value": 50.0}}
    ]
}}

User: "find cylindrical faces"
Assistant: {{
    "entity_type": "face",
    "predicates": [
        {{"attribute": "surface_type", "operator": "eq", "value": "cylinder"}}
    ]
}}

User: "smallest edge"
Assistant: {{
    "entity_type": "edge",
    "predicates": [],
    "sort_by": "length",
    "order": "asc",
    "limit": 1
}}

User: "show faces with thickness less than 2mm"
Assistant: {{
    "entity_type": "face",
    "predicates": [
        {{"attribute": "local_thickness", "operator": "lt", "value": 2.0}}
    ]
}}

User: "find faces with thickness between 2 and 5mm"
Assistant: {{
    "entity_type": "face",
    "predicates": [
        {{"attribute": "local_thickness", "operator": "gte", "value": 2.0}},
        {{"attribute": "local_thickness", "operator": "lte", "value": 5.0}}
    ]
}}

User: "show thin walls"
Assistant: {{
    "entity_type": "face",
    "predicates": [
        {{"attribute": "is_thin_wall_face", "operator": "eq", "value": true}}
    ]
}}

User: "find faces with non-uniform thickness"
Assistant: {{
    "entity_type": "face",
    "predicates": [
        {{"attribute": "thickness_variance", "operator": "gt", "value": 0.3}}
    ]
}}

User: "show high stress concentration areas"
Assistant: {{
    "entity_type": "face",
    "predicates": [
        {{"attribute": "stress_concentration", "operator": "gt", "value": 0.7}}
    ]
}}

User: "find undercuts"
Assistant: {{
    "entity_type": "face",
    "predicates": [
        {{"attribute": "has_undercut", "operator": "eq", "value": true}}
    ]
}}

User: "show faces with insufficient draft angle"
Assistant: {{
    "entity_type": "face",
    "predicates": [
        {{"attribute": "draft_angle", "operator": "lt", "value": 1.0}}
    ]
}}

User: "find overhangs that need support"
Assistant: {{
    "entity_type": "face",
    "predicates": [
        {{"attribute": "overhang_angle", "operator": "gt", "value": 45.0}}
    ]
}}

User: "faces with extreme overhang"
Assistant: {{
    "entity_type": "face",
    "predicates": [
        {{"attribute": "overhang_angle", "operator": "gt", "value": 70.0}}
    ]
}}

User: "show all line edges"
Assistant: {{
    "entity_type": "edge",
    "predicates": [
        {{"attribute": "curve_type", "operator": "eq", "value": "line"}}
    ]
}}

User: "vertices at z=0"
Assistant: {{
    "entity_type": "vertex",
    "predicates": [
        {{"attribute": "z", "operator": "in_range", "value": 0.0, "tolerance": 0.1}}
    ]
}}

User: "faces with area between 10 and 20"
Assistant: {{
    "entity_type": "face",
    "predicates": [
        {{"attribute": "area", "operator": "gte", "value": 10.0}},
        {{"attribute": "area", "operator": "lte", "value": 20.0}}
    ]
}}

User: "find semicircular edges"
Assistant: {{
    "entity_type": "edge",
    "predicates": [
        {{"attribute": "is_semicircle", "operator": "eq", "value": true}}
    ]
}}

User: "arcs with radius 5mm"
Assistant: {{
    "entity_type": "edge",
    "predicates": [
        {{"attribute": "is_arc", "operator": "eq", "value": true}},
        {{"attribute": "radius", "operator": "in_range", "value": 5.0, "tolerance": 0.5}}
    ]
}}

User: "edges that are arcs but not full circles"
Assistant: {{
    "entity_type": "edge",
    "predicates": [
        {{"attribute": "is_arc", "operator": "eq", "value": true}}
    ]
}}

User: "find quarter circle edges"
Assistant: {{
    "entity_type": "edge",
    "predicates": [
        {{"attribute": "is_quarter_circle", "operator": "eq", "value": true}}
    ]
}}

User: "arcs with angle between 80 and 100 degrees"
Assistant: {{
    "entity_type": "edge",
    "predicates": [
        {{"attribute": "arc_angle", "operator": "gte", "value": 80.0}},
        {{"attribute": "arc_angle", "operator": "lte", "value": 100.0}}
    ]
}}

User: "fillet edges with radius 5mm"
Assistant: {{
    "entity_type": "edge",
    "predicates": [
        {{"attribute": "is_arc", "operator": "eq", "value": true}},
        {{"attribute": "radius", "operator": "in_range", "value": 5.0, "tolerance": 0.5}}
    ]
}}

User: "find cylindrical fillet faces"
Assistant: {{
    "entity_type": "face",
    "predicates": [
        {{"attribute": "surface_type", "operator": "eq", "value": "cylinder"}},
        {{"attribute": "quarter_circle_edge_count", "operator": "gt", "value": 0}}
    ]
}}

User: "find fillets"
Assistant: {{
    "entity_type": "face",
    "predicates": [
        {{"attribute": "surface_type", "operator": "eq", "value": "cylinder"}},
        {{"attribute": "quarter_circle_edge_count", "operator": "gt", "value": 0}}
    ]
}}

User: "find curved fillets"
Assistant: {{
    "entity_type": "face",
    "predicates": [
        {{"attribute": "surface_type", "operator": "eq", "value": "torus"}},
        {{"attribute": "quarter_circle_edge_count", "operator": "gt", "value": 0}}
    ]
}}

User: "toroidal fillets"
Assistant: {{
    "entity_type": "face",
    "predicates": [
        {{"attribute": "surface_type", "operator": "eq", "value": "torus"}},
        {{"attribute": "quarter_circle_edge_count", "operator": "gt", "value": 0}}
    ]
}}

User: "find chamfers"
Assistant: {{
    "entity_type": "face",
    "predicates": [
        {{"attribute": "surface_type", "operator": "eq", "value": "plane"}},
        {{"attribute": "area", "operator": "lt", "value": 50.0}}
    ]
}}

User: "small planar bevels"
Assistant: {{
    "entity_type": "face",
    "predicates": [
        {{"attribute": "surface_type", "operator": "eq", "value": "plane"}},
        {{"attribute": "area", "operator": "lt", "value": 50.0}}
    ]
}}

User: "small cylindrical surfaces"
Assistant: {{
    "entity_type": "face",
    "predicates": [
        {{"attribute": "surface_type", "operator": "eq", "value": "cylinder"}},
        {{"attribute": "radius", "operator": "lt", "value": 5.0}}
    ]
}}

User: "find holes"
Assistant: {{
    "entity_type": "face",
    "predicates": [
        {{"attribute": "surface_type", "operator": "eq", "value": "cylinder"}},
        {{"attribute": "is_internal_cylinder", "operator": "eq", "value": true}},
        {{"attribute": "semicircle_edge_count", "operator": "gt", "value": 0}}
    ]
}}

User: "find cylindrical holes"
Assistant: {{
    "entity_type": "face",
    "predicates": [
        {{"attribute": "surface_type", "operator": "eq", "value": "cylinder"}},
        {{"attribute": "is_internal_cylinder", "operator": "eq", "value": true}},
        {{"attribute": "semicircle_edge_count", "operator": "gt", "value": 0}}
    ]
}}

User: "cylindrical faces with radius less than 2mm"
Assistant: {{
    "entity_type": "face",
    "predicates": [
        {{"attribute": "surface_type", "operator": "eq", "value": "cylinder"}},
        {{"attribute": "radius", "operator": "lt", "value": 2.0}}
    ]
}}

User: "find cavities"
Assistant: {{
    "entity_type": "face",
    "predicates": [
        {{"attribute": "is_cavity_face", "operator": "eq", "value": true}}
    ]
}}

User: "show pockets"
Assistant: {{
    "entity_type": "face",
    "predicates": [
        {{"attribute": "is_cavity_face", "operator": "eq", "value": true}}
    ]
}}

User: "find recesses"
Assistant: {{
    "entity_type": "face",
    "predicates": [
        {{"attribute": "is_cavity_face", "operator": "eq", "value": true}}
    ]
}}

IMPORTANT: Respond ONLY with the JSON object, no other text or explanation."""

    def _convert_to_structured_query(self, parsed_json: Dict[str, Any]) -> StructuredQuery:
        """
        Convert parsed JSON to StructuredQuery object.

        Args:
            parsed_json: JSON response from Claude API

        Returns:
            StructuredQuery object
        """
        # Extract entity type
        entity_type = parsed_json.get("entity_type", "face")

        # Build predicates
        predicates = []
        for pred_dict in parsed_json.get("predicates", []):
            predicate = Predicate(
                attribute=pred_dict["attribute"],
                operator=Operator(pred_dict["operator"]),
                value=pred_dict["value"],
                tolerance=pred_dict.get("tolerance")
            )
            predicates.append(predicate)

        # Build query
        return StructuredQuery(
            entity_type=entity_type,
            predicates=predicates,
            sort_by=parsed_json.get("sort_by"),
            order=parsed_json.get("order", "asc"),
            limit=parsed_json.get("limit")
        )

    def _fallback_parse(self, query: str) -> StructuredQuery:
        """
        Fallback regex-based parser for simple queries when Claude API unavailable.

        Args:
            query: User query

        Returns:
            StructuredQuery (best effort)
        """
        query_lower = query.lower()

        # Determine entity type
        entity_type = "face"  # Default
        if "edge" in query_lower:
            entity_type = "edge"
        elif "vertex" in query_lower or "vertices" in query_lower:
            entity_type = "vertex"
        elif "shell" in query_lower:
            entity_type = "shell"

        predicates = []
        sort_by = None
        order = "asc"
        limit = None

        # Handle superlatives
        if "largest" in query_lower or "biggest" in query_lower:
            sort_by = "area" if entity_type == "face" else "length"
            order = "desc"
            limit = 1
        elif "smallest" in query_lower or "shortest" in query_lower:
            sort_by = "area" if entity_type == "face" else "length"
            order = "asc"
            limit = 1

        # Handle "curved fillet" keyword - toroidal fillets
        if ("curved" in query_lower and "fillet" in query_lower) or "toroidal fillet" in query_lower:
            if entity_type == "face":
                predicates.append(Predicate(
                    attribute="surface_type",
                    operator=Operator.EQ,
                    value="torus"
                ))
                predicates.append(Predicate(
                    attribute="quarter_circle_edge_count",
                    operator=Operator.GT,
                    value=0
                ))

        # Handle "fillet" keyword - cylindrical fillets have quarter-circle edges
        elif "fillet" in query_lower and entity_type == "face":
            predicates.append(Predicate(
                attribute="surface_type",
                operator=Operator.EQ,
                value="cylinder"
            ))
            # Fillets have quarter-circle edges (90-degree arcs)
            predicates.append(Predicate(
                attribute="quarter_circle_edge_count",
                operator=Operator.GT,
                value=0
            ))

        # Handle "chamfer" keyword - small planar bevels
        if "chamfer" in query_lower and entity_type == "face":
            predicates.append(Predicate(
                attribute="surface_type",
                operator=Operator.EQ,
                value="plane"
            ))
            # Chamfers are small (typically < 50mm²)
            predicates.append(Predicate(
                attribute="area",
                operator=Operator.LT,
                value=50.0
            ))

        # Handle "hole" keyword - holes are internal with semicircular edges
        if "hole" in query_lower and entity_type == "face":
            predicates.append(Predicate(
                attribute="surface_type",
                operator=Operator.EQ,
                value="cylinder"
            ))
            # Holes are internal cylinders
            predicates.append(Predicate(
                attribute="is_internal_cylinder",
                operator=Operator.EQ,
                value=True
            ))
            # Holes have semicircular edges (180-degree arcs)
            predicates.append(Predicate(
                attribute="semicircle_edge_count",
                operator=Operator.GT,
                value=0
            ))

        # Handle "cavity", "pocket", "recess" keywords
        if ("cavity" in query_lower or "pocket" in query_lower or "recess" in query_lower) and entity_type == "face":
            predicates.append(Predicate(
                attribute="is_cavity_face",
                operator=Operator.EQ,
                value=True
            ))

        # Handle type filters
        type_keywords = {
            "planar": ("surface_type", "plane"),
            "plane": ("surface_type", "plane"),
            "flat": ("surface_type", "plane"),
            "cylindrical": ("surface_type", "cylinder"),
            "cylinder": ("surface_type", "cylinder"),
            "toroidal": ("surface_type", "torus"),
            "torus": ("surface_type", "torus"),
            "spherical": ("surface_type", "sphere"),
            "sphere": ("surface_type", "sphere"),
            "conical": ("surface_type", "cone"),
            "cone": ("surface_type", "cone"),
            "circular": ("curve_type", "circle"),
            "circle": ("curve_type", "circle"),
            "arc": ("curve_type", "circle"),
            "line": ("curve_type", "line"),
            "linear": ("curve_type", "line"),
            "straight": ("curve_type", "line"),
            "spline": ("curve_type", "bspline"),
            "bspline": ("curve_type", "bspline"),
            "curved": ("curve_type", "bspline"),
        }

        for keyword, (attr, value) in type_keywords.items():
            if keyword in query_lower:
                predicates.append(Predicate(
                    attribute=attr,
                    operator=Operator.EQ,
                    value=value
                ))
                break  # Only match first keyword to avoid duplicates

        # Handle arc/semicircle/quarter circle keywords
        if "semicircle" in query_lower or "semi-circle" in query_lower or "half circle" in query_lower:
            predicates.append(Predicate(
                attribute="is_semicircle",
                operator=Operator.EQ,
                value=True
            ))
        elif "quarter circle" in query_lower or "quarter-circle" in query_lower:
            predicates.append(Predicate(
                attribute="is_quarter_circle",
                operator=Operator.EQ,
                value=True
            ))
        elif "three quarter" in query_lower or "three-quarter" in query_lower:
            predicates.append(Predicate(
                attribute="is_three_quarter_circle",
                operator=Operator.EQ,
                value=True
            ))
        elif "arc" in query_lower and "full" not in query_lower:
            predicates.append(Predicate(
                attribute="is_arc",
                operator=Operator.EQ,
                value=True
            ))
        elif "full circle" in query_lower or "complete circle" in query_lower:
            predicates.append(Predicate(
                attribute="is_full_circle",
                operator=Operator.EQ,
                value=True
            ))

        # Handle numeric filters
        # Pattern: "area 20" or "area 20mm²"
        area_match = re.search(r'area\s+(\d+(?:\.\d+)?)', query_lower)
        if area_match:
            area_value = float(area_match.group(1))
            predicates.append(Predicate(
                attribute="area",
                operator=Operator.IN_RANGE,
                value=area_value,
                tolerance=self.default_tolerance
            ))

        # Pattern: "radius 5" or "radius 5mm"
        radius_match = re.search(r'radius\s+(\d+(?:\.\d+)?)', query_lower)
        if radius_match:
            radius_value = float(radius_match.group(1))
            predicates.append(Predicate(
                attribute="radius",
                operator=Operator.IN_RANGE,
                value=radius_value,
                tolerance=self.default_tolerance
            ))

        # Pattern: "length > 50" or "longer than 50"
        length_gt_match = re.search(r'(?:length\s*>\s*|longer\s+than\s+)(\d+(?:\.\d+)?)', query_lower)
        if length_gt_match:
            length_value = float(length_gt_match.group(1))
            predicates.append(Predicate(
                attribute="length",
                operator=Operator.GT,
                value=length_value
            ))

        # Pattern: "area > 20" or "area greater than 20"
        area_gt_match = re.search(r'(?:area\s*>\s*|area\s+(?:greater|larger)\s+than\s+)(\d+(?:\.\d+)?)', query_lower)
        if area_gt_match:
            area_value = float(area_gt_match.group(1))
            predicates.append(Predicate(
                attribute="area",
                operator=Operator.GT,
                value=area_value
            ))

        # Pattern: "area < 20" or "area less than 20"
        area_lt_match = re.search(r'(?:area\s*<\s*|area\s+(?:less|smaller)\s+than\s+)(\d+(?:\.\d+)?)', query_lower)
        if area_lt_match:
            area_value = float(area_lt_match.group(1))
            predicates.append(Predicate(
                attribute="area",
                operator=Operator.LT,
                value=area_value
            ))

        # Pattern: "radius < 5" or "radius less than 5"
        radius_lt_match = re.search(r'(?:radius\s*<\s*|radius\s+(?:less|smaller)\s+than\s+)(\d+(?:\.\d+)?)', query_lower)
        if radius_lt_match:
            radius_value = float(radius_lt_match.group(1))
            predicates.append(Predicate(
                attribute="radius",
                operator=Operator.LT,
                value=radius_value
            ))

        # Thickness patterns
        if entity_type == "face":
            # Pattern: "thin walls" or "thin wall"
            if re.search(r'thin\s+walls?', query_lower):
                predicates.append(Predicate(
                    attribute="is_thin_wall_face",
                    operator=Operator.EQ,
                    value=True
                ))

            # Pattern: "thickness < 2" or "thickness less than 2mm"
            thickness_lt_match = re.search(r'thickness\s+(?:less\s+than|<|under)\s+(\d+(?:\.\d+)?)', query_lower)
            if thickness_lt_match:
                thickness_value = float(thickness_lt_match.group(1))
                predicates.append(Predicate(
                    attribute="local_thickness",
                    operator=Operator.LT,
                    value=thickness_value
                ))

            # Pattern: "thickness > 5" or "thickness greater than 5mm"
            thickness_gt_match = re.search(r'thickness\s+(?:greater\s+than|>|over)\s+(\d+(?:\.\d+)?)', query_lower)
            if thickness_gt_match:
                thickness_value = float(thickness_gt_match.group(1))
                predicates.append(Predicate(
                    attribute="local_thickness",
                    operator=Operator.GT,
                    value=thickness_value
                ))

            # Pattern: "thickness between 2 and 5"
            thickness_range_match = re.search(r'thickness\s+between\s+(\d+(?:\.\d+)?)\s+and\s+(\d+(?:\.\d+)?)', query_lower)
            if thickness_range_match:
                min_thickness = float(thickness_range_match.group(1))
                max_thickness = float(thickness_range_match.group(2))
                predicates.append(Predicate(
                    attribute="local_thickness",
                    operator=Operator.GTE,
                    value=min_thickness
                ))
                predicates.append(Predicate(
                    attribute="local_thickness",
                    operator=Operator.LTE,
                    value=max_thickness
                ))

            # DFM attribute patterns
            # Pattern: "non-uniform thickness" or "thickness variance"
            if re.search(r'(non[- ]?uniform|variance|varying)\s+thickness', query_lower) or "thickness variance" in query_lower:
                predicates.append(Predicate(
                    attribute="thickness_variance",
                    operator=Operator.GT,
                    value=0.3  # Threshold for non-uniform
                ))

            # Pattern: "stress concentration" or "high stress"
            if re.search(r'(high\s+)?stress(\s+concentration)?', query_lower):
                predicates.append(Predicate(
                    attribute="stress_concentration",
                    operator=Operator.GT,
                    value=0.7  # Threshold for high stress
                ))

            # Pattern: "undercuts" or "undercut"
            if re.search(r'undercuts?', query_lower):
                predicates.append(Predicate(
                    attribute="has_undercut",
                    operator=Operator.EQ,
                    value=True
                ))

            # Pattern: "insufficient draft" or "draft angle less than"
            draft_lt_match = re.search(r'(?:draft\s+(?:angle\s+)?(?:less\s+than|<)|insufficient\s+draft)\s*(\d+(?:\.\d+)?)', query_lower)
            if draft_lt_match:
                draft_value = float(draft_lt_match.group(1))
                predicates.append(Predicate(
                    attribute="draft_angle",
                    operator=Operator.LT,
                    value=draft_value
                ))
            elif "insufficient draft" in query_lower or "low draft" in query_lower:
                predicates.append(Predicate(
                    attribute="draft_angle",
                    operator=Operator.LT,
                    value=1.0  # Default threshold
                ))

            # Pattern: "overhangs" or "overhang angle"
            overhang_match = re.search(r'overhang\s+(?:angle\s+)?(?:greater\s+than|>)\s*(\d+(?:\.\d+)?)', query_lower)
            if overhang_match:
                overhang_value = float(overhang_match.group(1))
                predicates.append(Predicate(
                    attribute="overhang_angle",
                    operator=Operator.GT,
                    value=overhang_value
                ))
            elif "overhangs" in query_lower or "overhang" in query_lower:
                predicates.append(Predicate(
                    attribute="overhang_angle",
                    operator=Operator.GT,
                    value=45.0  # Default threshold for 3D printing
                ))

        # Warn if no predicates and no sorting (query might not be understood)
        if len(predicates) == 0 and sort_by is None:
            logger.warning(f"Fallback parser created query with 0 predicates - query may not be understood: '{query}'")

        logger.info(f"Fallback parse: '{query}' → {entity_type} with {len(predicates)} predicates")

        return StructuredQuery(
            entity_type=entity_type,
            predicates=predicates,
            sort_by=sort_by,
            order=order,
            limit=limit
        )
