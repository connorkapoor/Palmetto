"""
Query Engine for executing structured queries against AAG data.

This module provides the core query execution functionality for filtering
and selecting geometric entities (faces, edges, vertices) based on attributes
and relationships.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Any, Dict
from enum import Enum
import time


class Operator(str, Enum):
    """Query operators"""
    EQ = "eq"           # Equal
    NE = "ne"           # Not equal
    GT = "gt"           # Greater than
    LT = "lt"           # Less than
    GTE = "gte"         # Greater than or equal
    LTE = "lte"         # Less than or equal
    IN_RANGE = "in_range"  # Value within tolerance
    CONTAINS = "contains"  # String contains
    IN = "in"           # Value in list


@dataclass
class Predicate:
    """A single query predicate (filter condition)"""
    attribute: str
    operator: Operator
    value: Any
    tolerance: Optional[float] = None  # For numeric comparisons

    def evaluate(self, entity: Dict[str, Any]) -> bool:
        """
        Evaluate this predicate against an entity.

        Args:
            entity: Entity dict with attributes

        Returns:
            True if predicate matches, False otherwise
        """
        # Get attribute value from entity
        # Handle nested attributes (e.g., "attributes.area")
        attr_value = self._get_attribute_value(entity, self.attribute)

        if attr_value is None:
            return False

        # Apply operator
        if self.operator == Operator.EQ:
            return attr_value == self.value
        elif self.operator == Operator.NE:
            return attr_value != self.value
        elif self.operator == Operator.GT:
            return float(attr_value) > float(self.value)
        elif self.operator == Operator.LT:
            return float(attr_value) < float(self.value)
        elif self.operator == Operator.GTE:
            return float(attr_value) >= float(self.value)
        elif self.operator == Operator.LTE:
            return float(attr_value) <= float(self.value)
        elif self.operator == Operator.IN_RANGE:
            tolerance = self.tolerance if self.tolerance is not None else 0.5
            return abs(float(attr_value) - float(self.value)) <= tolerance
        elif self.operator == Operator.CONTAINS:
            return str(self.value).lower() in str(attr_value).lower()
        elif self.operator == Operator.IN:
            return attr_value in self.value

        return False

    def _get_attribute_value(self, entity: Dict[str, Any], attr_path: str) -> Any:
        """
        Get attribute value from entity, supporting nested paths.

        Examples:
            "area" -> entity["attributes"]["area"]
            "surface_type" -> entity["attributes"]["surface_type"]
            "name" -> entity["name"]
        """
        # Direct attributes
        if attr_path in entity:
            return entity[attr_path]

        # Check in attributes dict
        if "attributes" in entity and attr_path in entity["attributes"]:
            return entity["attributes"][attr_path]

        # Handle nested paths (e.g., "attributes.area")
        parts = attr_path.split(".")
        value = entity
        for part in parts:
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                return None

        return value


@dataclass
class StructuredQuery:
    """A structured query with predicates and sorting"""
    entity_type: str  # "face", "edge", "vertex", "shell"
    predicates: List[Predicate] = field(default_factory=list)
    sort_by: Optional[str] = None
    order: Optional[str] = "asc"  # "asc" or "desc"
    limit: Optional[int] = None


@dataclass
class QueryResult:
    """Result of query execution"""
    matching_ids: List[str]
    total_matches: int
    entity_type: str
    execution_time_ms: float
    entities: Optional[List[Dict[str, Any]]] = None  # Full entity data


class QueryEngine:
    """
    Execute structured queries against AAG data.

    The engine filters entities by type, applies predicates,
    sorts results, and returns matching entity IDs.
    """

    def __init__(self, aag_data: Dict[str, Any]):
        """
        Initialize query engine with AAG data.

        Args:
            aag_data: Complete AAG JSON from C++ engine
        """
        self.aag_data = aag_data
        self.nodes_by_type = self._index_by_type()

    def _index_by_type(self) -> Dict[str, List[Dict[str, Any]]]:
        """Build index of nodes by entity type"""
        index = {
            "vertex": [],
            "edge": [],
            "face": [],
            "shell": []
        }

        for node in self.aag_data.get("nodes", []):
            group = node.get("group")
            if group in index:
                index[group].append(node)

        return index

    def execute(self, query: StructuredQuery) -> QueryResult:
        """
        Execute a structured query and return matching entity IDs.

        Args:
            query: StructuredQuery with filters and sorting

        Returns:
            QueryResult with matching IDs and statistics
        """
        start_time = time.time()

        # Get candidates by type
        candidates = self.nodes_by_type.get(query.entity_type, [])

        # Apply predicates
        filtered = candidates
        for predicate in query.predicates:
            filtered = [entity for entity in filtered if predicate.evaluate(entity)]

        # Sort if requested
        if query.sort_by:
            filtered = self._sort_entities(filtered, query.sort_by, query.order)

        # Apply limit
        if query.limit:
            filtered = filtered[:query.limit]

        # Extract IDs
        matching_ids = [entity["id"] for entity in filtered]

        execution_time_ms = (time.time() - start_time) * 1000

        return QueryResult(
            matching_ids=matching_ids,
            total_matches=len(matching_ids),
            entity_type=query.entity_type,
            execution_time_ms=execution_time_ms,
            entities=filtered
        )

    def _sort_entities(
        self,
        entities: List[Dict[str, Any]],
        sort_by: str,
        order: str
    ) -> List[Dict[str, Any]]:
        """
        Sort entities by attribute.

        Args:
            entities: List of entities
            sort_by: Attribute name to sort by
            order: "asc" or "desc"

        Returns:
            Sorted list of entities
        """
        def get_sort_key(entity: Dict[str, Any]) -> Any:
            """Extract sort key from entity"""
            # Try direct attribute
            if sort_by in entity:
                return entity[sort_by]

            # Try attributes dict
            if "attributes" in entity and sort_by in entity["attributes"]:
                value = entity["attributes"][sort_by]
                # Convert string numbers to float for proper numeric sorting
                try:
                    return float(value)
                except (ValueError, TypeError):
                    return value

            return 0  # Default for missing values

        reverse = (order == "desc")
        return sorted(entities, key=get_sort_key, reverse=reverse)
