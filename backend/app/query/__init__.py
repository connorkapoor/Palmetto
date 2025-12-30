"""
Query package for natural language geometric queries.

This package provides:
- QueryEngine: Executes structured queries against AAG data
- QueryParser: Converts natural language to structured queries
"""

from .query_engine import QueryEngine, QueryResult, StructuredQuery, Predicate
from .query_parser import QueryParser

__all__ = [
    'QueryEngine',
    'QueryResult',
    'StructuredQuery',
    'Predicate',
    'QueryParser',
]
