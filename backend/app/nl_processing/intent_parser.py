"""
Intent parser - orchestrates natural language processing.

Combines Claude API with recognizer registry to map
natural language commands to executable recognizer calls.
"""

import logging
from typing import Dict, Any

from app.nl_processing.claude_client import ClaudeClient
from app.recognizers.registry import RecognizerRegistry

logger = logging.getLogger(__name__)


class IntentParser:
    """
    Parses natural language commands and maps to recognizers.
    """

    def __init__(self, claude_client: ClaudeClient = None):
        """
        Initialize parser.

        Args:
            claude_client: Optional ClaudeClient instance
        """
        self.claude = claude_client or ClaudeClient()

    def parse(self, command: str) -> Dict[str, Any]:
        """
        Parse command and return execution plan.

        Args:
            command: Natural language command

        Returns:
            Dictionary with:
            - recognizer: str (recognizer name)
            - parameters: dict (parameters for recognizer)
            - confidence: float (confidence in parsing)

        Raises:
            ValueError: If recognizer not found
        """
        logger.info(f"Parsing command: '{command}'")

        # Get available recognizers
        recognizers = []
        for name in RecognizerRegistry.list_all():
            info = RecognizerRegistry.get_recognizer_info(name)
            if info:
                recognizers.append(info)

        # Parse with Claude
        result = self.claude.parse_command(command, recognizers)

        # Validate recognizer exists
        if not RecognizerRegistry.get(result["recognizer"]):
            raise ValueError(
                f"Unknown recognizer: {result['recognizer']}. "
                f"Available: {RecognizerRegistry.list_all()}"
            )

        logger.info(f"Intent parsed: recognizer={result['recognizer']}, "
                   f"params={result['parameters']}, confidence={result['confidence']}")

        return result

    def validate_parameters(
        self,
        recognizer_name: str,
        parameters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Validate and sanitize parameters for a recognizer.

        Args:
            recognizer_name: Name of recognizer
            parameters: Parameters to validate

        Returns:
            Validated parameters

        Note:
            This is a placeholder for more sophisticated validation.
            In a production system, each recognizer would declare its
            parameter schema and we'd validate against it.
        """
        # For now, just pass through
        # TODO: Implement schema-based validation
        return parameters
