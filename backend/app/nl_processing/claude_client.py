"""
Claude API client for natural language command parsing.

Uses Anthropic's Claude API to parse user commands like:
- "find all holes larger than 10mm"
- "detect fillets with radius 5mm"
- "show me all cavities"

The API returns structured JSON mapping commands to recognizers and parameters.
"""

import json
import logging
from typing import Dict, Any, List

import anthropic

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class ClaudeClient:
    """
    Client for Claude API natural language processing.
    """

    def __init__(self, api_key: str = None):
        """
        Initialize Claude client.

        Args:
            api_key: Optional API key (defaults to settings)
        """
        self.api_key = api_key or settings.anthropic_api_key

        if not self.api_key:
            logger.warning("No Anthropic API key configured!")

        self.client = anthropic.Anthropic(api_key=self.api_key) if self.api_key else None

    def parse_command(
        self,
        command: str,
        available_recognizers: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Parse natural language command into recognizer call.

        Args:
            command: User's natural language command
            available_recognizers: List of available recognizer info

        Returns:
            Dictionary with:
            - recognizer: str (recognizer name)
            - parameters: dict (recognizer parameters)
            - confidence: float (confidence in parsing)

        Example:
            Input: "find all holes larger than 10mm"
            Output: {
                "recognizer": "hole_detector",
                "parameters": {"min_diameter": 10.0},
                "confidence": 0.95
            }
        """
        if not self.client:
            # Fallback to simple keyword matching
            logger.warning("No Claude API client, using fallback parser")
            return self._fallback_parse(command, available_recognizers)

        # Build system prompt with recognizer descriptions
        system_prompt = self._build_system_prompt(available_recognizers)

        try:
            # Call Claude API
            message = self.client.messages.create(
                model=settings.claude_model,
                max_tokens=settings.claude_max_tokens,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": command}
                ]
            )

            # Extract response text
            response_text = message.content[0].text

            # Parse JSON
            result = json.loads(response_text)

            logger.info(f"Parsed command: '{command}' → {result['recognizer']}")

            return result

        except Exception as e:
            logger.error(f"Claude API parsing failed: {e}")
            # Fallback to simple parsing
            return self._fallback_parse(command, available_recognizers)

    def _build_system_prompt(self, recognizers: List[Dict[str, Any]]) -> str:
        """
        Build system prompt with recognizer descriptions.

        Args:
            recognizers: List of recognizer information

        Returns:
            System prompt string
        """
        recognizer_info = "\n".join([
            f"- {r['name']}: {r['description']}"
            for r in recognizers
        ])

        return f"""You are a CAD feature recognition assistant. Parse user commands and map them to specific feature recognizers.

Available recognizers:
{recognizer_info}

Your response MUST be valid JSON with this exact structure:
{{
    "recognizer": "recognizer_name",
    "parameters": {{
        "param1": value1,
        "param2": value2
    }},
    "confidence": 0.95
}}

Extract parameters from the command:
- Dimensions: "larger than 10mm" → {{"min_diameter": 10.0}}
- Dimensions: "between 5mm and 10mm" → {{"min_diameter": 5.0, "max_diameter": 10.0}}
- Feature types: "countersunk holes" → {{"hole_types": ["countersunk"]}}
- Quantities: "all holes" means no filtering

Examples:
User: "find all holes larger than 10mm"
Assistant: {{"recognizer": "hole_detector", "parameters": {{"min_diameter": 10.0}}, "confidence": 0.95}}

User: "detect fillets with radius 5mm"
Assistant: {{"recognizer": "fillet_detector", "parameters": {{"radius": 5.0}}, "confidence": 0.90}}

User: "show me holes between 3mm and 8mm"
Assistant: {{"recognizer": "hole_detector", "parameters": {{"min_diameter": 3.0, "max_diameter": 8.0}}, "confidence": 0.95}}

IMPORTANT: Respond ONLY with the JSON object, no other text."""

    def _fallback_parse(
        self,
        command: str,
        available_recognizers: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Fallback keyword-based parser when Claude API is unavailable.

        Args:
            command: User command
            available_recognizers: Available recognizers

        Returns:
            Parsed result (best effort)
        """
        command_lower = command.lower()

        # Simple keyword matching
        if "hole" in command_lower:
            # Extract diameter if mentioned
            parameters = {}

            # Look for "larger than X" or "bigger than X"
            import re
            match = re.search(r'(?:larger|bigger|greater)\s+than\s+(\d+(?:\.\d+)?)', command_lower)
            if match:
                parameters['min_diameter'] = float(match.group(1))

            # Look for "smaller than X"
            match = re.search(r'(?:smaller|less)\s+than\s+(\d+(?:\.\d+)?)', command_lower)
            if match:
                parameters['max_diameter'] = float(match.group(1))

            return {
                "recognizer": "hole_detector",
                "parameters": parameters,
                "confidence": 0.7
            }

        elif "fillet" in command_lower:
            parameters = {}

            # Look for radius
            import re
            match = re.search(r'radius\s+(\d+(?:\.\d+)?)', command_lower)
            if match:
                parameters['radius'] = float(match.group(1))

            return {
                "recognizer": "fillet_detector",
                "parameters": parameters,
                "confidence": 0.7
            }

        elif "shaft" in command_lower:
            return {
                "recognizer": "shaft_detector",
                "parameters": {},
                "confidence": 0.7
            }

        elif "cavity" in command_lower or "pocket" in command_lower:
            return {
                "recognizer": "cavity_detector",
                "parameters": {},
                "confidence": 0.7
            }

        else:
            # Default to hole detector
            return {
                "recognizer": "hole_detector",
                "parameters": {},
                "confidence": 0.3
            }
