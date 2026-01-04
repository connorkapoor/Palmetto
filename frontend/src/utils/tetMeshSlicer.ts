/**
 * Tetrahedral Mesh Slicing Utility
 *
 * Implements marching tets algorithm to extract cross-sections from
 * volumetric tetrahedral meshes at arbitrary slice planes.
 */

/**
 * Tetrahedral mesh data structure
 */
export interface TetMesh {
  version: string;
  type: string;
  metadata: {
    node_count: number;
    element_count: number;
    boundary_nodes: number;
    interior_nodes: number;
    thickness_range: [number, number];
    bbox: {
      min: [number, number, number];
      max: [number, number, number];
    };
  };
  nodes: Array<{
    id: number;
    pos: [number, number, number];
    thickness: number;
    boundary: boolean;
  }>;
  elements: Array<{
    id: number;
    nodes: [number, number, number, number];
  }>;
}

/**
 * Plane definition (point + normal)
 */
export interface SlicePlane {
  point: [number, number, number];  // Point on plane
  normal: [number, number, number]; // Plane normal (unit vector)
}

/**
 * Slice triangle with interpolated thickness
 */
export interface SliceTriangle {
  vertices: [[number, number, number], [number, number, number], [number, number, number]];
  thicknesses: [number, number, number];
}

/**
 * Intersection point on edge
 */
interface EdgeIntersection {
  pos: [number, number, number];
  thickness: number;
}

/**
 * Compute signed distance from point to plane
 */
function signedDistance(
  point: [number, number, number],
  plane: SlicePlane
): number {
  const [px, py, pz] = point;
  const [ox, oy, oz] = plane.point;
  const [nx, ny, nz] = plane.normal;

  return (px - ox) * nx + (py - oy) * ny + (pz - oz) * nz;
}

/**
 * Interpolate thickness at plane intersection
 */
function interpolateThickness(
  thickness1: number,
  thickness2: number,
  t: number
): number {
  // Handle invalid thickness values
  if (thickness1 < 0 && thickness2 < 0) return -1;
  if (thickness1 < 0) return thickness2;
  if (thickness2 < 0) return thickness1;

  return thickness1 + t * (thickness2 - thickness1);
}

/**
 * Intersect tet edge with plane
 */
function intersectEdge(
  node1: TetMesh['nodes'][0],
  node2: TetMesh['nodes'][0],
  plane: SlicePlane
): EdgeIntersection | null {
  const d1 = signedDistance(node1.pos, plane);
  const d2 = signedDistance(node2.pos, plane);

  // Edge doesn't cross plane (both nodes on same side)
  if (d1 * d2 > 0) return null;

  // Avoid division by zero
  const denom = Math.abs(d1) + Math.abs(d2);
  if (denom < 1e-10) return null;

  // Parametric interpolation: p = p1 + t * (p2 - p1)
  const t = Math.abs(d1) / denom;

  const pos: [number, number, number] = [
    node1.pos[0] + t * (node2.pos[0] - node1.pos[0]),
    node1.pos[1] + t * (node2.pos[1] - node1.pos[1]),
    node1.pos[2] + t * (node2.pos[2] - node1.pos[2])
  ];

  const thickness = interpolateThickness(node1.thickness, node2.thickness, t);

  return { pos, thickness };
}

/**
 * Extract sectioned volume from tet mesh at given plane
 *
 * Algorithm:
 * 1. For each tetrahedron, check if it's on the "keep" side of plane (distance < 0)
 * 2. Extract boundary triangles (faces on exterior or at cut plane)
 * 3. Color by interpolated thickness
 *
 * @param mesh Tetrahedral mesh
 * @param plane Slice plane
 * @returns Array of triangles with thickness values showing sectioned volume
 */
export function sliceTetMesh(
  mesh: TetMesh,
  plane: SlicePlane
): SliceTriangle[] {
  const triangles: SliceTriangle[] = [];

  console.log(`Extracting sectioned volume from ${mesh.elements.length} tetrahedra...`);

  // Tet faces (4 triangular faces per tet)
  const tetFaces: [number, number, number][] = [
    [0, 2, 1], // Face opposite to node 3
    [0, 1, 3], // Face opposite to node 2
    [0, 3, 2], // Face opposite to node 1
    [1, 2, 3]  // Face opposite to node 0
  ];

  let kept_tets = 0;
  let boundary_faces = 0;

  for (const elem of mesh.elements) {
    // Get the 4 nodes of this tet
    const nodes = elem.nodes.map(nid => mesh.nodes[nid]);

    // Compute signed distances to plane
    const distances = nodes.map(n => signedDistance(n.pos, plane));

    // Check if any nodes are on the "keep" side (negative distance)
    const hasKeepNode = distances.some(d => d < 0);
    const hasCutNode = distances.some(d => d > 0);

    if (!hasKeepNode) {
      // Entire tet is on the cut side, skip it
      continue;
    }

    kept_tets++;

    if (!hasCutNode) {
      // Entire tet is on the keep side - show all boundary faces
      // (In reality, interior faces shared with other tets won't show due to depth testing)
      for (const [i, j, k] of tetFaces) {
        // Check if this face is on the boundary (at least one node is a boundary node)
        if (nodes[i].boundary || nodes[j].boundary || nodes[k].boundary) {
          triangles.push({
            vertices: [nodes[i].pos, nodes[j].pos, nodes[k].pos],
            thicknesses: [nodes[i].thickness, nodes[j].thickness, nodes[k].thickness]
          });
          boundary_faces++;
        }
      }
    } else {
      // Tet intersects the plane - generate cut triangles
      const edges: [number, number][] = [
        [0, 1], [0, 2], [0, 3],
        [1, 2], [1, 3], [2, 3]
      ];

      const intersections: EdgeIntersection[] = [];
      for (const [i, j] of edges) {
        const intersection = intersectEdge(nodes[i], nodes[j], plane);
        if (intersection) {
          intersections.push(intersection);
        }
      }

      // Generate triangles at the cut plane
      if (intersections.length === 3) {
        triangles.push({
          vertices: [intersections[0].pos, intersections[1].pos, intersections[2].pos],
          thicknesses: [intersections[0].thickness, intersections[1].thickness, intersections[2].thickness]
        });
      } else if (intersections.length === 4) {
        triangles.push({
          vertices: [intersections[0].pos, intersections[1].pos, intersections[2].pos],
          thicknesses: [intersections[0].thickness, intersections[1].thickness, intersections[2].thickness]
        });
        triangles.push({
          vertices: [intersections[0].pos, intersections[2].pos, intersections[3].pos],
          thicknesses: [intersections[0].thickness, intersections[2].thickness, intersections[3].thickness]
        });
      }
    }
  }

  console.log(`  Generated ${triangles.length} triangles (${boundary_faces} boundary, rest from cut) from ${kept_tets} tets`);

  return triangles;
}

/**
 * Convert thickness value to RGB color (heatmap)
 * Blue (thick) → Cyan → Green → Yellow → Red (thin)
 */
export function thicknessToColor(
  thickness: number,
  range: [number, number]
): [number, number, number] {
  const [min, max] = range;

  // Handle invalid thickness
  if (thickness < 0) {
    return [0.5, 0.5, 0.5];  // Gray for unmeasured
  }

  // Normalize to [0, 1], invert so thin = red
  const normalized = Math.max(0, Math.min(1, (thickness - min) / (max - min)));
  const inverted = 1.0 - normalized;  // Invert: thin=1.0 (red), thick=0.0 (blue)

  let r: number, g: number, b: number;

  if (inverted < 0.25) {
    // Blue to Cyan (0.0 - 0.25)
    r = 0.0;
    g = inverted * 4.0;
    b = 1.0;
  } else if (inverted < 0.5) {
    // Cyan to Green (0.25 - 0.5)
    r = 0.0;
    g = 1.0;
    b = 1.0 - (inverted - 0.25) * 4.0;
  } else if (inverted < 0.75) {
    // Green to Yellow (0.5 - 0.75)
    r = (inverted - 0.5) * 4.0;
    g = 1.0;
    b = 0.0;
  } else {
    // Yellow to Red (0.75 - 1.0)
    r = 1.0;
    g = 1.0 - (inverted - 0.75) * 4.0;
    b = 0.0;
  }

  return [r, g, b];
}

/**
 * Create slice plane from axis and position
 *
 * @param axis Slice axis ('x', 'y', or 'z')
 * @param position Position along axis (0-1 normalized)
 * @param bbox Bounding box
 * @returns Slice plane
 */
export function createSlicePlane(
  axis: 'x' | 'y' | 'z',
  position: number,
  bbox: { min: [number, number, number]; max: [number, number, number] }
): SlicePlane {
  const point: [number, number, number] = [
    (bbox.min[0] + bbox.max[0]) / 2,
    (bbox.min[1] + bbox.max[1]) / 2,
    (bbox.min[2] + bbox.max[2]) / 2
  ];

  const normal: [number, number, number] = [0, 0, 0];

  if (axis === 'x') {
    point[0] = bbox.min[0] + position * (bbox.max[0] - bbox.min[0]);
    normal[0] = 1;
  } else if (axis === 'y') {
    point[1] = bbox.min[1] + position * (bbox.max[1] - bbox.min[1]);
    normal[1] = 1;
  } else {
    point[2] = bbox.min[2] + position * (bbox.max[2] - bbox.min[2]);
    normal[2] = 1;
  }

  return { point, normal };
}
