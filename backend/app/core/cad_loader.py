"""
CAD file loader using pythonOCC.
Supports STEP, IGES, and BREP file formats.
"""

import os
from typing import Optional
from pathlib import Path

# Try to import pythonOCC, fall back to mock if not available
try:
    from OCC.Core.TopoDS import TopoDS_Shape
    from OCC.Core.STEPControl import STEPControl_Reader
    from OCC.Core.IGESControl import IGESControl_Reader
    from OCC.Core.BRep import BRep_Builder
    from OCC.Core.BRepTools import breptools
    from OCC.Core.IFSelect import IFSelect_RetDone
    PYTHONOCC_AVAILABLE = True
except ImportError:
    print("⚠️  WARNING: pythonOCC not available. CAD file loading disabled.")
    print("   To enable: conda install -c conda-forge pythonocc-core")
    from app.core.occt_mock import TopoDS_Shape
    PYTHONOCC_AVAILABLE = False

    class IFSelect_RetDone:
        pass
    class STEPControl_Reader:
        pass
    class IGESControl_Reader:
        pass
    class BRep_Builder:
        pass


class CADLoadError(Exception):
    """Exception raised when CAD file loading fails."""
    pass


class CADLoader:
    """
    Loader for CAD files (STEP, IGES, BREP).
    Provides unified interface for different CAD formats using pythonOCC.
    """

    SUPPORTED_FORMATS = {
        '.step': 'step',
        '.stp': 'step',
        '.iges': 'iges',
        '.igs': 'iges',
        '.brep': 'brep'
    }

    @staticmethod
    def load(file_path: str, file_format: Optional[str] = None) -> TopoDS_Shape:
        """
        Load a CAD file and return the B-Rep shape.

        Args:
            file_path: Path to the CAD file
            file_format: File format ('step', 'iges', 'brep'). If None, inferred from extension.

        Returns:
            TopoDS_Shape: The loaded B-Rep shape

        Raises:
            CADLoadError: If loading fails or format is unsupported
            FileNotFoundError: If file doesn't exist
        """
        if not PYTHONOCC_AVAILABLE:
            raise CADLoadError(
                "pythonOCC is not installed. "
                "To enable CAD file loading, install: conda install -c conda-forge pythonocc-core"
            )

        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        # Infer format from extension if not provided
        if file_format is None:
            ext = Path(file_path).suffix.lower()
            file_format = CADLoader.SUPPORTED_FORMATS.get(ext)
            if file_format is None:
                raise CADLoadError(
                    f"Unsupported file extension: {ext}. "
                    f"Supported: {list(CADLoader.SUPPORTED_FORMATS.keys())}"
                )

        file_format = file_format.lower()

        try:
            if file_format == 'step':
                return CADLoader._load_step(file_path)
            elif file_format == 'iges':
                return CADLoader._load_iges(file_path)
            elif file_format == 'brep':
                return CADLoader._load_brep(file_path)
            else:
                raise CADLoadError(f"Unsupported format: {file_format}")
        except Exception as e:
            raise CADLoadError(f"Failed to load CAD file: {str(e)}") from e

    @staticmethod
    def _load_step(file_path: str) -> TopoDS_Shape:
        """Load STEP file using STEPControl_Reader."""
        reader = STEPControl_Reader()
        status = reader.ReadFile(file_path)

        if status != IFSelect_RetDone:
            raise CADLoadError(f"STEP file read failed with status: {status}")

        # Transfer roots
        reader.TransferRoots()

        # Get shape
        shape = reader.OneShape()

        if shape.IsNull():
            raise CADLoadError("STEP file contains no valid shapes")

        return shape

    @staticmethod
    def _load_iges(file_path: str) -> TopoDS_Shape:
        """Load IGES file using IGESControl_Reader."""
        reader = IGESControl_Reader()
        status = reader.ReadFile(file_path)

        if status != IFSelect_RetDone:
            raise CADLoadError(f"IGES file read failed with status: {status}")

        # Transfer roots
        reader.TransferRoots()

        # Get shape
        shape = reader.OneShape()

        if shape.IsNull():
            raise CADLoadError("IGES file contains no valid shapes")

        return shape

    @staticmethod
    def _load_brep(file_path: str) -> TopoDS_Shape:
        """Load BREP file using BRep_Builder."""
        shape = TopoDS_Shape()
        builder = BRep_Builder()

        # Read BREP file
        read_result = breptools.Read(shape, file_path, builder)

        if not read_result:
            raise CADLoadError("BREP file read failed")

        if shape.IsNull():
            raise CADLoadError("BREP file contains no valid shapes")

        return shape

    @staticmethod
    def validate(file_path: str, file_format: Optional[str] = None) -> bool:
        """
        Validate if a file can be loaded.

        Args:
            file_path: Path to the CAD file
            file_format: File format ('step', 'iges', 'brep'). If None, inferred from extension.

        Returns:
            bool: True if file can be loaded, False otherwise
        """
        try:
            shape = CADLoader.load(file_path, file_format)
            return not shape.IsNull()
        except (CADLoadError, FileNotFoundError):
            return False

    @staticmethod
    def get_format_from_extension(file_path: str) -> Optional[str]:
        """
        Get the CAD format from file extension.

        Args:
            file_path: Path to the file

        Returns:
            str: Format name ('step', 'iges', 'brep') or None if unsupported
        """
        ext = Path(file_path).suffix.lower()
        return CADLoader.SUPPORTED_FORMATS.get(ext)

    @staticmethod
    def is_supported_format(file_path: str) -> bool:
        """
        Check if the file format is supported.

        Args:
            file_path: Path to the file

        Returns:
            bool: True if format is supported
        """
        return CADLoader.get_format_from_extension(file_path) is not None
