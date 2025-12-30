"""
glTF export with face metadata.

Exports tessellated meshes to glTF format with embedded face-to-triangle
mapping. This metadata enables face-level highlighting in the frontend viewer.
"""

from typing import Dict, List, Optional
import logging
import numpy as np
import struct

import pygltflib
from pygltflib import GLTF2, Scene, Node, Mesh, Primitive, Buffer, BufferView, Accessor
from pygltflib import ARRAY_BUFFER, ELEMENT_ARRAY_BUFFER, FLOAT, UNSIGNED_INT, VEC3, SCALAR

logger = logging.getLogger(__name__)


class GLTFExporter:
    """
    Exports mesh to glTF with face metadata.

    The critical feature is embedding the face_map in the glTF extras field,
    which allows the frontend to highlight specific faces by selecting their
    triangles.
    """

    def __init__(
        self,
        vertices: np.ndarray,
        triangles: np.ndarray,
        face_map: Dict[str, List[int]]
    ):
        """
        Initialize exporter with mesh data.

        Args:
            vertices: (N, 3) array of vertex positions
            triangles: (M, 3) array of triangle indices
            face_map: {face_id: [triangle_indices]}
        """
        self.vertices = vertices.astype(np.float32)
        self.triangles = triangles.astype(np.uint32)
        self.face_map = face_map

    def export(
        self,
        output_path: str,
        feature_highlights: Optional[Dict[str, List[str]]] = None
    ) -> None:
        """
        Export mesh to glTF file.

        Args:
            output_path: Output file path
            feature_highlights: Optional dict of {feature_id: [face_ids]}
                               for color-coding detected features

        The glTF file will contain:
        - Mesh geometry (vertices and triangles)
        - Face metadata in extras.face_map
        - Optional feature highlight metadata in extras.feature_highlights
        """
        logger.info(f"Exporting glTF to {output_path}")

        # Create glTF object
        gltf = GLTF2()

        # Convert data to binary
        vertices_binary = self.vertices.tobytes()
        triangles_binary = self.triangles.tobytes()

        # Create buffer
        buffer = Buffer()
        buffer.byteLength = len(vertices_binary) + len(triangles_binary)
        gltf.buffers.append(buffer)

        # Create buffer view for vertices
        vertices_buffer_view = BufferView()
        vertices_buffer_view.buffer = 0
        vertices_buffer_view.byteOffset = 0
        vertices_buffer_view.byteLength = len(vertices_binary)
        vertices_buffer_view.target = ARRAY_BUFFER
        gltf.bufferViews.append(vertices_buffer_view)

        # Create buffer view for triangles
        triangles_buffer_view = BufferView()
        triangles_buffer_view.buffer = 0
        triangles_buffer_view.byteOffset = len(vertices_binary)
        triangles_buffer_view.byteLength = len(triangles_binary)
        triangles_buffer_view.target = ELEMENT_ARRAY_BUFFER
        gltf.bufferViews.append(triangles_buffer_view)

        # Create accessor for vertices
        vertices_accessor = Accessor()
        vertices_accessor.bufferView = 0
        vertices_accessor.byteOffset = 0
        vertices_accessor.componentType = FLOAT
        vertices_accessor.count = len(self.vertices)
        vertices_accessor.type = VEC3

        # Compute bounding box
        if len(self.vertices) > 0:
            vertices_accessor.min = self.vertices.min(axis=0).tolist()
            vertices_accessor.max = self.vertices.max(axis=0).tolist()
        else:
            vertices_accessor.min = [0, 0, 0]
            vertices_accessor.max = [0, 0, 0]

        gltf.accessors.append(vertices_accessor)

        # Create accessor for triangles
        triangles_accessor = Accessor()
        triangles_accessor.bufferView = 1
        triangles_accessor.byteOffset = 0
        triangles_accessor.componentType = UNSIGNED_INT
        triangles_accessor.count = len(self.triangles) * 3
        triangles_accessor.type = SCALAR
        gltf.accessors.append(triangles_accessor)

        # Create mesh primitive
        primitive = Primitive()
        primitive.attributes.POSITION = 0
        primitive.indices = 1

        # Create mesh
        mesh = Mesh()
        mesh.primitives.append(primitive)
        gltf.meshes.append(mesh)

        # Create node
        node = Node()
        node.mesh = 0
        gltf.nodes.append(node)

        # Create scene
        scene = Scene()
        scene.nodes.append(0)
        gltf.scenes.append(scene)
        gltf.scene = 0

        # **CRITICAL: Embed face metadata in extras**
        # This is what enables face highlighting in the frontend
        gltf.extras = {
            'face_map': self.face_map,
            'feature_highlights': feature_highlights or {},
            'metadata': {
                'vertex_count': len(self.vertices),
                'triangle_count': len(self.triangles),
                'face_count': len(self.face_map),
                'exporter': 'Palmetto glTF Exporter v0.1'
            }
        }

        # Set binary blob
        gltf.set_binary_blob(vertices_binary + triangles_binary)

        # Save
        gltf.save(output_path)

        logger.info(f"glTF exported successfully: {len(self.vertices)} vertices, "
                   f"{len(self.triangles)} triangles, {len(self.face_map)} faces")

    def export_to_bytes(
        self,
        feature_highlights: Optional[Dict[str, List[str]]] = None
    ) -> bytes:
        """
        Export mesh to glTF binary format (GLB) as bytes.

        Args:
            feature_highlights: Optional feature highlight metadata

        Returns:
            GLB file as bytes
        """
        import tempfile
        import os

        # Create temporary file
        with tempfile.NamedTemporaryFile(suffix='.glb', delete=False) as tmp:
            tmp_path = tmp.name

        try:
            # Export to file
            self.export(tmp_path, feature_highlights)

            # Read bytes
            with open(tmp_path, 'rb') as f:
                data = f.read()

            return data

        finally:
            # Cleanup
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

    @staticmethod
    def create_feature_highlight_map(
        features: List[any],  # List of RecognizedFeature
    ) -> Dict[str, List[str]]:
        """
        Create feature highlight mapping from recognized features.

        Args:
            features: List of RecognizedFeature objects

        Returns:
            Dictionary mapping {feature_id: [face_ids]}
        """
        highlight_map = {}

        for feature in features:
            highlight_map[feature.feature_id] = feature.face_ids

        return highlight_map

    @staticmethod
    def get_metadata_from_gltf(file_path: str) -> Optional[Dict]:
        """
        Extract face_map metadata from a glTF file.

        Args:
            file_path: Path to glTF file

        Returns:
            Extras metadata dictionary or None
        """
        try:
            gltf = GLTF2().load(file_path)
            return gltf.extras
        except Exception as e:
            logger.error(f"Failed to read glTF metadata: {e}")
            return None
