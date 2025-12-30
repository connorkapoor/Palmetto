"""
C++ Engine Integration

Wrapper to call the palmetto_engine C++ binary from Python.
"""

import subprocess
import json
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Path to the C++ engine binary
ENGINE_BINARY = os.environ.get(
    "PALMETTO_ENGINE_PATH",
    str(Path(__file__).parent.parent.parent / "bin" / "palmetto_engine")
)


@dataclass
class EngineResult:
    """Result from C++ engine processing"""
    success: bool
    model_id: str
    output_dir: Path
    features: List[Dict]
    metadata: Dict
    error: Optional[str] = None


class CppEngineError(Exception):
    """Exception raised when C++ engine fails"""
    pass


class CppEngine:
    """
    Interface to the C++ palmetto_engine binary.

    The C++ engine handles:
    - STEP file loading
    - AAG construction
    - Feature recognition using Analysis Situs
    - Mesh generation with tri→face mapping
    """

    def __init__(self, engine_path: Optional[str] = None):
        """
        Initialize the C++ engine wrapper.

        Args:
            engine_path: Path to palmetto_engine binary. If None, uses environment variable.
        """
        self.engine_path = engine_path or ENGINE_BINARY

        if not os.path.exists(self.engine_path):
            raise FileNotFoundError(
                f"C++ engine not found at {self.engine_path}. "
                f"Build it with: cd core && cmake --build .build/palmetto_engine"
            )

    def process_step_file(
        self,
        input_file: Path,
        output_dir: Path,
        modules: str = "all",
        mesh_quality: float = 0.35,
        timeout: int = 300
    ) -> EngineResult:
        """
        Process a STEP file through the C++ engine.

        Args:
            input_file: Path to input STEP file
            output_dir: Directory to write outputs
            modules: Comma-separated module list or "all"
            mesh_quality: Mesh tessellation quality 0.0-1.0
            timeout: Maximum processing time in seconds

        Returns:
            EngineResult with processing results

        Raises:
            CppEngineError: If engine fails
        """
        # Ensure output directory exists
        output_dir.mkdir(parents=True, exist_ok=True)

        # Build command
        cmd = [
            str(self.engine_path),
            "--input", str(input_file),
            "--outdir", str(output_dir),
            "--modules", modules,
            "--mesh-quality", str(mesh_quality),
            "--units", "mm"
        ]

        logger.info(f"Running C++ engine: {' '.join(cmd)}")

        try:
            # Run engine
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=True
            )

            logger.debug(f"Engine stdout:\n{result.stdout}")

            if result.stderr:
                logger.warning(f"Engine stderr:\n{result.stderr}")

            # Load results
            features = self._load_features(output_dir)
            metadata = self._load_metadata(output_dir)

            # Extract model_id from metadata or use output dir name
            model_id = metadata.get("model_id", output_dir.name)

            return EngineResult(
                success=True,
                model_id=model_id,
                output_dir=output_dir,
                features=features,
                metadata=metadata
            )

        except subprocess.TimeoutExpired as e:
            error_msg = f"C++ engine timed out after {timeout}s"
            logger.error(error_msg)
            raise CppEngineError(error_msg) from e

        except subprocess.CalledProcessError as e:
            error_msg = f"C++ engine failed with exit code {e.returncode}"
            logger.error(f"{error_msg}\nStderr: {e.stderr}")

            return EngineResult(
                success=False,
                model_id="",
                output_dir=output_dir,
                features=[],
                metadata={},
                error=f"{error_msg}: {e.stderr}"
            )

        except Exception as e:
            error_msg = f"Unexpected error running C++ engine: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise CppEngineError(error_msg) from e

    def _load_features(self, output_dir: Path) -> List[Dict]:
        """Load features.json from output directory"""
        features_file = output_dir / "features.json"

        if not features_file.exists():
            logger.warning(f"features.json not found at {features_file}")
            return []

        try:
            with open(features_file, 'r') as f:
                data = json.load(f)
                return data.get("features", [])
        except Exception as e:
            logger.error(f"Failed to load features.json: {e}")
            return []

    def _load_metadata(self, output_dir: Path) -> Dict:
        """Load meta.json from output directory"""
        meta_file = output_dir / "meta.json"

        if not meta_file.exists():
            logger.warning(f"meta.json not found at {meta_file}")
            return {}

        try:
            with open(meta_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load meta.json: {e}")
            return {}

    def check_available(self) -> bool:
        """
        Check if C++ engine is available and working.

        Returns:
            True if engine responds to --version, False otherwise
        """
        try:
            result = subprocess.run(
                [str(self.engine_path), "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except Exception as e:
            logger.error(f"C++ engine check failed: {e}")
            return False

    def list_modules(self) -> List[Dict]:
        """
        Get list of available recognizer modules.

        Returns:
            List of module info dicts: [{name, type, description}, ...]
        """
        try:
            result = subprocess.run(
                [str(self.engine_path), "--list-modules"],
                capture_output=True,
                text=True,
                timeout=5,
                check=True
            )

            data = json.loads(result.stdout)
            return data.get("modules", [])

        except Exception as e:
            logger.error(f"Failed to list modules: {e}")
            return []


# Singleton instance
_engine_instance: Optional[CppEngine] = None


def get_engine() -> CppEngine:
    """Get the global C++ engine instance"""
    global _engine_instance

    if _engine_instance is None:
        _engine_instance = CppEngine()

    return _engine_instance
