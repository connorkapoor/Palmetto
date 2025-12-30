/**
 * Viewer3D Component
 * Renders CAD models using Three.js and handles face highlighting
 */

import { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { FaceMap } from '../types/features';
import './Viewer3D.css';

interface TopologyData {
  vertices: Array<{ id: number; position: [number, number, number] }>;
  edges: Array<{
    id: number;
    vertices: [number, number];
    points: Array<[number, number, number]>;
  }>;
}

interface Viewer3DProps {
  gltfUrl: string;
  triFaceMapUrl: string;
  topologyUrl: string;
  highlightedFaceIds: string[];
  highlightedVertexIds?: string[];
  highlightedEdgeIds?: string[];
  onFaceClick?: (faceId: string, multiSelect?: boolean) => void;
}

export default function Viewer3D({ gltfUrl, triFaceMapUrl, topologyUrl, highlightedFaceIds, highlightedVertexIds = [], highlightedEdgeIds = [], onFaceClick }: Viewer3DProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const sceneRef = useRef<THREE.Scene | null>(null);
  const meshRef = useRef<THREE.Mesh | null>(null);
  const faceMapRef = useRef<FaceMap | null>(null);
  const triFaceMapArrayRef = useRef<Uint32Array | null>(null);
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const controlsRef = useRef<OrbitControls | null>(null);
  const [loading, setLoading] = useState(true);
  const raycasterRef = useRef<THREE.Raycaster>(new THREE.Raycaster());
  const mouseRef = useRef<THREE.Vector2>(new THREE.Vector2());
  const onFaceClickRef = useRef(onFaceClick);
  const topologyDataRef = useRef<TopologyData | null>(null);
  const edgeLinesRef = useRef<THREE.LineSegments | null>(null);
  const vertexPointsRef = useRef<THREE.Points | null>(null);
  const edgeSegmentMapRef = useRef<Map<number, number[]>>(new Map()); // edge ID -> segment indices

  // Keep ref up to date
  useEffect(() => {
    onFaceClickRef.current = onFaceClick;
  }, [onFaceClick]);

  // Initialize Three.js scene
  useEffect(() => {
    if (!containerRef.current) return;

    const container = containerRef.current;

    // Scene
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0xf1f5f9);
    sceneRef.current = scene;

    // Camera
    const camera = new THREE.PerspectiveCamera(
      45,
      container.clientWidth / container.clientHeight,
      0.1,
      1000
    );
    camera.position.set(5, 5, 5);
    cameraRef.current = camera;

    // Renderer
    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(container.clientWidth, container.clientHeight);
    renderer.setPixelRatio(window.devicePixelRatio);
    container.appendChild(renderer.domElement);
    rendererRef.current = renderer;

    // Controls
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.05;
    controlsRef.current = controls;

    // Lighting - Enhanced for better shading
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.5);
    scene.add(ambientLight);

    // Key light
    const directionalLight = new THREE.DirectionalLight(0xffffff, 1.0);
    directionalLight.position.set(10, 10, 10);
    directionalLight.castShadow = true;
    scene.add(directionalLight);

    // Fill light
    const directionalLight2 = new THREE.DirectionalLight(0xffffff, 0.5);
    directionalLight2.position.set(-10, 5, -10);
    scene.add(directionalLight2);

    // Rim light
    const directionalLight3 = new THREE.DirectionalLight(0xffffff, 0.3);
    directionalLight3.position.set(0, -10, 5);
    scene.add(directionalLight3);

    // Hemisphere light for better ambient feel
    const hemiLight = new THREE.HemisphereLight(0xffffff, 0x444444, 0.3);
    hemiLight.position.set(0, 20, 0);
    scene.add(hemiLight);

    // Animation loop
    const animate = () => {
      requestAnimationFrame(animate);
      controls.update();
      renderer.render(scene, camera);
    };
    animate();

    // Handle resize
    const handleResize = () => {
      if (!container) return;
      camera.aspect = container.clientWidth / container.clientHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(container.clientWidth, container.clientHeight);
    };
    window.addEventListener('resize', handleResize);

    // Cleanup
    return () => {
      window.removeEventListener('resize', handleResize);
      renderer.dispose();
      container.removeChild(renderer.domElement);
    };
  }, []);

  // Handle click for face selection (separate effect to avoid recreating scene)
  useEffect(() => {
    if (!rendererRef.current) return;

    const handleClick = (event: MouseEvent) => {
      if (!meshRef.current || !triFaceMapArrayRef.current || !cameraRef.current || !containerRef.current) {
        return;
      }

      const rect = containerRef.current.getBoundingClientRect();
      const mouse = mouseRef.current;
      mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
      mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

      const raycaster = raycasterRef.current;
      raycaster.setFromCamera(mouse, cameraRef.current);

      const intersects = raycaster.intersectObject(meshRef.current);
      if (intersects.length > 0) {
        const intersection = intersects[0];
        if (intersection.faceIndex !== undefined) {
          // Get the face ID from the tri_face_map
          const faceId = triFaceMapArrayRef.current[intersection.faceIndex];
          const multiSelect = event.ctrlKey || event.metaKey;
          console.log('Clicked face:', faceId, multiSelect ? '(multi-select)' : '');
          if (onFaceClickRef.current) {
            onFaceClickRef.current(faceId.toString(), multiSelect);
          }
        }
      }
    };

    rendererRef.current.domElement.addEventListener('click', handleClick);

    return () => {
      if (rendererRef.current) {
        rendererRef.current.domElement.removeEventListener('click', handleClick);
      }
    };
  }, []);

  // Load tri_face_map.bin
  useEffect(() => {
    if (!triFaceMapUrl) return;

    fetch(triFaceMapUrl)
      .then(response => response.arrayBuffer())
      .then(arrayBuffer => {
        const uint32Array = new Uint32Array(arrayBuffer);
        triFaceMapArrayRef.current = uint32Array;
        console.log(`Loaded tri_face_map.bin: ${uint32Array.length} triangles`);

        // Build face map: { faceId: [triangleIndices] }
        const faceMap: FaceMap = {};
        for (let i = 0; i < uint32Array.length; i++) {
          const faceId = uint32Array[i].toString();
          if (!faceMap[faceId]) {
            faceMap[faceId] = [];
          }
          faceMap[faceId].push(i);
        }
        faceMapRef.current = faceMap;
        console.log(`Built face map: ${Object.keys(faceMap).length} faces`);
      })
      .catch(error => {
        console.error('Error loading tri_face_map.bin:', error);
      });
  }, [triFaceMapUrl]);

  // Load glTF model
  useEffect(() => {
    if (!gltfUrl || !sceneRef.current) return;

    setLoading(true);

    const loader = new GLTFLoader();
    loader.load(
      gltfUrl,
      (gltf) => {
        console.log('glTF loaded:', gltf);

        // Remove old mesh if exists
        if (meshRef.current && sceneRef.current) {
          sceneRef.current.remove(meshRef.current);
        }

        // Get mesh
        const mesh = gltf.scene.children[0] as THREE.Mesh;
        if (!mesh) {
          console.error('No mesh found in glTF');
          setLoading(false);
          return;
        }

        meshRef.current = mesh;

        // Set up material with vertex colors and better shading
        const material = new THREE.MeshStandardMaterial({
          vertexColors: true,
          metalness: 0.2,
          roughness: 0.6,
          side: THREE.DoubleSide,
          flatShading: false,
        });
        mesh.material = material;

        // Initialize colors (all gray with slight warmth)
        initializeColors(mesh);

        // Add to scene
        sceneRef.current?.add(mesh);

        // Center camera on model
        centerCamera(mesh);

        setLoading(false);
        // Topology overlay will be created by the effect above
      },
      undefined,
      (error) => {
        console.error('Error loading glTF:', error);
        setLoading(false);
      }
    );
  }, [gltfUrl]);

  // Update highlights when highlightedFaceIds changes
  useEffect(() => {
    if (!meshRef.current || !faceMapRef.current) return;

    highlightFaces(meshRef.current, faceMapRef.current, highlightedFaceIds);
  }, [highlightedFaceIds]);

  // Load topology data
  useEffect(() => {
    if (!topologyUrl) return;

    console.log('Loading topology from:', topologyUrl);
    fetch(topologyUrl + '?t=' + Date.now()) // Cache-busting
      .then(response => {
        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
        return response.json();
      })
      .then(data => {
        console.log('Topology data received:', data);

        // Validate the data structure
        if (!data || !data.vertices || !data.edges) {
          console.error('Invalid topology data structure:', data);
          console.error('Expected: { vertices: [...], edges: [...] }');
          throw new Error('Invalid topology data structure - missing vertices or edges');
        }

        // Check if edges have discretized points
        const edgesWithPoints = data.edges.filter((e: any) => e.points && e.points.length > 0);
        console.log(`Topology validation: ${edgesWithPoints.length}/${data.edges.length} edges have discretized points`);
        if (edgesWithPoints.length > 0) {
          console.log('Sample edge with points:', edgesWithPoints[0]);
        }

        topologyDataRef.current = data;
        console.log(`Loaded topology: ${data.vertices.length} vertices, ${data.edges.length} edges`);
        // Topology overlay will be created by the effect below
      })
      .catch(error => {
        console.error('Error loading topology:', error);
        console.error('URL was:', topologyUrl);
        console.error('You may need to re-upload the model to generate topology.json with the new engine version');
      });
  }, [topologyUrl]);

  // Create topology overlay whenever both scene and topology data are ready
  useEffect(() => {
    console.log('Checking if ready to create topology overlay:', {
      scene: !!sceneRef.current,
      topology: !!topologyDataRef.current,
      mesh: !!meshRef.current,
      topologyUrl,
      gltfUrl
    });

    if (!sceneRef.current || !topologyDataRef.current || !meshRef.current) {
      console.warn('Not ready yet, waiting...');
      return;
    }

    console.log('All ready, creating topology overlay NOW...');
    createTopologyOverlay();

    console.log('After createTopologyOverlay, refs:', {
      edgeLines: !!edgeLinesRef.current,
      vertexPoints: !!vertexPointsRef.current
    });
  }, [topologyUrl, gltfUrl, loading]); // Also trigger after loading completes

  // Create edge lines and vertex points overlay
  const createTopologyOverlay = () => {
    console.log('[createTopologyOverlay] Starting...');

    if (!topologyDataRef.current || !sceneRef.current) {
      console.error('[createTopologyOverlay] FAILED - missing refs:', {
        topology: !!topologyDataRef.current,
        scene: !!sceneRef.current
      });
      return;
    }

    console.log('[createTopologyOverlay] Creating with', topologyDataRef.current.vertices.length, 'vertices and', topologyDataRef.current.edges.length, 'edges');

    // Remove old overlays if they exist
    if (edgeLinesRef.current) {
      console.log('[createTopologyOverlay] Removing old edge lines');
      sceneRef.current.remove(edgeLinesRef.current);
      edgeLinesRef.current.geometry.dispose();
      (edgeLinesRef.current.material as THREE.Material).dispose();
      edgeLinesRef.current = null;
    }
    if (vertexPointsRef.current) {
      console.log('[createTopologyOverlay] Removing old vertex points');
      sceneRef.current.remove(vertexPointsRef.current);
      vertexPointsRef.current.geometry.dispose();
      (vertexPointsRef.current.material as THREE.Material).dispose();
      vertexPointsRef.current = null;
    }

    const topology = topologyDataRef.current;

    // Create edge lines using discretized points
    const edgePositions: number[] = [];
    const edgeColors: number[] = [];
    const defaultEdgeColor = new THREE.Color(0x333333); // Dark gray, subtle
    const edgeSegmentMap = new Map<number, number[]>();

    let segmentIndex = 0;
    let edgesWithPoints = 0;
    let edgesWithoutPoints = 0;

    topology.edges.forEach(edge => {
      // Use discretized points if available, otherwise fall back to vertices
      const points = edge.points && edge.points.length > 0 ? edge.points : (() => {
        const v1 = topology.vertices.find(v => v.id === edge.vertices[0]);
        const v2 = topology.vertices.find(v => v.id === edge.vertices[1]);
        return v1 && v2 ? [v1.position, v2.position] : [];
      })();

      if (edge.points && edge.points.length > 0) {
        edgesWithPoints++;
      } else {
        edgesWithoutPoints++;
      }

      const segmentIndices: number[] = [];

      // Create line segments between consecutive points
      for (let i = 0; i < points.length - 1; i++) {
        edgePositions.push(...points[i], ...points[i + 1]);
        edgeColors.push(defaultEdgeColor.r, defaultEdgeColor.g, defaultEdgeColor.b);
        edgeColors.push(defaultEdgeColor.r, defaultEdgeColor.g, defaultEdgeColor.b);
        segmentIndices.push(segmentIndex);
        segmentIndex++;
      }

      edgeSegmentMap.set(edge.id, segmentIndices);
    });

    console.log(`[createTopologyOverlay] Edge discretization: ${edgesWithPoints} with points, ${edgesWithoutPoints} without points`);

    edgeSegmentMapRef.current = edgeSegmentMap;

    const edgeGeometry = new THREE.BufferGeometry();
    edgeGeometry.setAttribute('position', new THREE.Float32BufferAttribute(edgePositions, 3));
    edgeGeometry.setAttribute('color', new THREE.Float32BufferAttribute(edgeColors, 3));

    const edgeMaterial = new THREE.LineBasicMaterial({
      vertexColors: true,
      linewidth: 1,
      depthTest: true,
      depthWrite: false,
      transparent: true,
      opacity: 0.3
    });

    const edgeLines = new THREE.LineSegments(edgeGeometry, edgeMaterial);
    edgeLines.renderOrder = 1;
    sceneRef.current.add(edgeLines);
    edgeLinesRef.current = edgeLines;
    console.log('[createTopologyOverlay] Edge lines created and added to scene');

    // Create vertex points
    const vertexPositions: number[] = [];
    const vertexColors: number[] = [];
    const defaultVertexColor = new THREE.Color(0x444444); // Dark gray, subtle

    topology.vertices.forEach(vertex => {
      vertexPositions.push(...vertex.position);
      vertexColors.push(defaultVertexColor.r, defaultVertexColor.g, defaultVertexColor.b);
    });

    const vertexGeometry = new THREE.BufferGeometry();
    vertexGeometry.setAttribute('position', new THREE.Float32BufferAttribute(vertexPositions, 3));
    vertexGeometry.setAttribute('color', new THREE.Float32BufferAttribute(vertexColors, 3));

    const vertexMaterial = new THREE.PointsMaterial({
      vertexColors: true,
      size: 3,
      sizeAttenuation: false,
      depthTest: true,
      depthWrite: false,
      transparent: true,
      opacity: 0.4
    });

    const vertexPoints = new THREE.Points(vertexGeometry, vertexMaterial);
    vertexPoints.renderOrder = 2;
    sceneRef.current.add(vertexPoints);
    vertexPointsRef.current = vertexPoints;
    console.log('[createTopologyOverlay] Vertex points created and added to scene');

    console.log('[createTopologyOverlay] SUCCESS! Overlay created:', {
      edgeCount: edgeGeometry.attributes.position.count / 2,
      vertexCount: vertexGeometry.attributes.position.count,
      edgeLinesRef: !!edgeLinesRef.current,
      vertexPointsRef: !!vertexPointsRef.current
    });
  };

  // Update vertex and edge highlights
  useEffect(() => {
    console.log('[Highlight Effect] Triggered with:', {
      highlightedVertexIds,
      highlightedEdgeIds,
      topology: !!topologyDataRef.current,
      edges: !!edgeLinesRef.current,
      vertices: !!vertexPointsRef.current
    });

    if (!topologyDataRef.current || !edgeLinesRef.current || !vertexPointsRef.current) {
      console.warn('[Highlight Effect] NOT READY - Topology overlay not ready for highlighting:', {
        topology: !!topologyDataRef.current,
        edges: !!edgeLinesRef.current,
        vertices: !!vertexPointsRef.current
      });
      return;
    }

    console.log('[Highlight Effect] Applying highlights:', {
      vertices: highlightedVertexIds,
      edges: highlightedEdgeIds
    });

    const topology = topologyDataRef.current;
    const highlightColor = new THREE.Color(0xff6600); // Orange for visibility
    const defaultEdgeColor = new THREE.Color(0x333333); // Dark gray, subtle
    const defaultVertexColor = new THREE.Color(0x444444); // Dark gray, subtle

    // Update edge colors using segment map
    const edgeColors = edgeLinesRef.current.geometry.attributes.color as THREE.BufferAttribute;
    const segmentMap = edgeSegmentMapRef.current;

    topology.edges.forEach(edge => {
      const isHighlighted = highlightedEdgeIds.includes(`edge_${edge.id}`);
      const color = isHighlighted ? highlightColor : defaultEdgeColor;
      const segmentIndices = segmentMap.get(edge.id) || [];

      // Update color for all segments of this edge
      segmentIndices.forEach(segIdx => {
        edgeColors.setXYZ(segIdx * 2, color.r, color.g, color.b);
        edgeColors.setXYZ(segIdx * 2 + 1, color.r, color.g, color.b);
      });
    });
    edgeColors.needsUpdate = true;

    // Update edge material opacity for highlighted edges
    if (highlightedEdgeIds.length > 0) {
      (edgeLinesRef.current.material as THREE.LineBasicMaterial).opacity = 0.9;
    } else {
      (edgeLinesRef.current.material as THREE.LineBasicMaterial).opacity = 0.3;
    }

    // Update vertex colors
    const vertexColors = vertexPointsRef.current.geometry.attributes.color as THREE.BufferAttribute;
    topology.vertices.forEach((vertex, idx) => {
      const isHighlighted = highlightedVertexIds.includes(`vertex_${vertex.id}`);
      const color = isHighlighted ? highlightColor : defaultVertexColor;
      vertexColors.setXYZ(idx, color.r, color.g, color.b);
    });
    vertexColors.needsUpdate = true;

    // Update vertex material for highlighted vertices
    if (highlightedVertexIds.length > 0) {
      (vertexPointsRef.current.material as THREE.PointsMaterial).size = 8;
      (vertexPointsRef.current.material as THREE.PointsMaterial).opacity = 0.9;
    } else {
      (vertexPointsRef.current.material as THREE.PointsMaterial).size = 3;
      (vertexPointsRef.current.material as THREE.PointsMaterial).opacity = 0.4;
    }

    console.log('Highlights applied');
  }, [highlightedVertexIds, highlightedEdgeIds]);

  const initializeColors = (mesh: THREE.Mesh) => {
    const geometry = mesh.geometry;
    const count = geometry.attributes.position.count;
    const colors = new Float32Array(count * 3);

    // Set all vertices to default light gray color with warmth
    for (let i = 0; i < count; i++) {
      colors[i * 3] = 0.85;     // R (slightly more red)
      colors[i * 3 + 1] = 0.85; // G
      colors[i * 3 + 2] = 0.9;  // B (slightly more blue for cool tone)
    }

    geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
    geometry.computeVertexNormals(); // Compute normals for proper shading
  };

  const highlightFaces = (
    mesh: THREE.Mesh,
    faceMap: FaceMap,
    faceIds: string[]
  ) => {
    console.log('Highlighting faces:', faceIds);
    console.log('Face map available:', faceMap ? 'yes' : 'no');

    const geometry = mesh.geometry;
    const positions = geometry.attributes.position;
    const indices = geometry.index;

    if (!indices) {
      console.error('Geometry has no index buffer');
      return;
    }

    const colors = new Float32Array(positions.count * 3);

    // Set all to default light gray
    for (let i = 0; i < positions.count; i++) {
      colors[i * 3] = 0.85;
      colors[i * 3 + 1] = 0.85;
      colors[i * 3 + 2] = 0.9;
    }

    // Highlight selected faces
    if (faceIds.length > 0 && faceMap) {
      console.log('Applying highlights for', faceIds.length, 'faces');

      for (const faceId of faceIds) {
        const triangleIndices = faceMap[faceId];

        if (!triangleIndices) {
          console.warn('No triangles found for face:', faceId);
          continue;
        }

        console.log(`Face ${faceId} has ${triangleIndices.length} triangles`);

        for (const triIdx of triangleIndices) {
          // Each triangle has 3 vertices in the index buffer
          // Get the actual vertex indices from the index buffer
          const idx0 = indices.getX(triIdx * 3);
          const idx1 = indices.getX(triIdx * 3 + 1);
          const idx2 = indices.getX(triIdx * 3 + 2);

          // Set highlight color for all 3 vertices of this triangle
          [idx0, idx1, idx2].forEach((vertexIdx) => {
            if (vertexIdx < positions.count) {
              colors[vertexIdx * 3] = 0.3;     // R
              colors[vertexIdx * 3 + 1] = 0.6; // G
              colors[vertexIdx * 3 + 2] = 1.0; // B (bright blue highlight)
            }
          });
        }
      }
    }

    geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
    geometry.attributes.color.needsUpdate = true;
    console.log('Highlight applied');
  };

  const centerCamera = (mesh: THREE.Mesh) => {
    if (!cameraRef.current || !controlsRef.current) {
      console.warn('Camera or controls not initialized');
      return;
    }

    const box = new THREE.Box3().setFromObject(mesh);
    const center = box.getCenter(new THREE.Vector3());
    const size = box.getSize(new THREE.Vector3());

    const maxDim = Math.max(size.x, size.y, size.z);
    const fov = 45 * (Math.PI / 180);
    let cameraZ = Math.abs(maxDim / 2 / Math.tan(fov / 2));
    cameraZ *= 2.0; // Add padding for better view

    const camera = cameraRef.current;
    const controls = controlsRef.current;

    // Position camera at an angle above and to the side
    camera.position.set(
      center.x + cameraZ * 0.7,
      center.y + cameraZ * 0.7,
      center.z + cameraZ * 0.7
    );

    // Point camera at center of model
    camera.lookAt(center);

    // Update controls target to center of model
    controls.target.copy(center);
    controls.update();

    console.log('Camera centered on model:', { center, size, cameraZ });
  };

  return (
    <div className="viewer3d" ref={containerRef}>
      {loading && (
        <div className="viewer-loading">
          <div className="spinner"></div>
          <p>Loading 3D model...</p>
        </div>
      )}
    </div>
  );
}
