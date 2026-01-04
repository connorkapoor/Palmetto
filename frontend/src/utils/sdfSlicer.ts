/**
 * SDF Slicing Utility
 *
 * Extracts cross-sections from volumetric Signed Distance Fields (SDFs)
 * at arbitrary slice planes. Much simpler and faster than tet mesh slicing.
 */

/**
 * SDF data structure
 */
export interface SDF {
  version: string;
  type: string;
  metadata: {
    nx: number;
    ny: number;
    nz: number;
    voxel_count: number;
    voxel_size: number;
    valid_voxels: number;
    thickness_range: [number, number];
    bbox: {
      min: [number, number, number];
      max: [number, number, number];
    };
  };
  thickness: number[];  // Flat array in row-major order: thickness[z * nx * ny + y * nx + x]
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
 * Trilinearly interpolate thickness at world position
 *
 * @param sdf SDF data
 * @param pos World position [x, y, z]
 * @returns Interpolated thickness value
 */
export function sampleSDF(sdf: SDF, pos: [number, number, number]): number {
  const { nx, ny, nz, voxel_size, bbox } = sdf.metadata;

  // Convert world position to grid coordinates
  const gx = (pos[0] - bbox.min[0]) / voxel_size;
  const gy = (pos[1] - bbox.min[1]) / voxel_size;
  const gz = (pos[2] - bbox.min[2]) / voxel_size;

  // Check bounds
  if (gx < 0 || gx >= nx - 1 || gy < 0 || gy >= ny - 1 || gz < 0 || gz >= nz - 1) {
    return -1; // Outside grid
  }

  // Get integer and fractional parts
  const ix = Math.floor(gx);
  const iy = Math.floor(gy);
  const iz = Math.floor(gz);
  const fx = gx - ix;
  const fy = gy - iy;
  const fz = gz - iz;

  // Sample 8 corners of voxel
  const getThickness = (x: number, y: number, z: number) => {
    const idx = z * nx * ny + y * nx + x;
    return sdf.thickness[idx];
  };

  const c000 = getThickness(ix, iy, iz);
  const c100 = getThickness(ix + 1, iy, iz);
  const c010 = getThickness(ix, iy + 1, iz);
  const c110 = getThickness(ix + 1, iy + 1, iz);
  const c001 = getThickness(ix, iy, iz + 1);
  const c101 = getThickness(ix + 1, iy, iz + 1);
  const c011 = getThickness(ix, iy + 1, iz + 1);
  const c111 = getThickness(ix + 1, iy + 1, iz + 1);

  // Trilinear interpolation
  const c00 = c000 * (1 - fx) + c100 * fx;
  const c01 = c001 * (1 - fx) + c101 * fx;
  const c10 = c010 * (1 - fx) + c110 * fx;
  const c11 = c011 * (1 - fx) + c111 * fx;

  const c0 = c00 * (1 - fy) + c10 * fy;
  const c1 = c01 * (1 - fy) + c11 * fy;

  return c0 * (1 - fz) + c1 * fz;
}

/**
 * Extract slice triangles from SDF at given plane
 *
 * Algorithm:
 * 1. Generate a regular grid of vertices on the slice plane
 * 2. For each vertex, sample the SDF to get thickness
 * 3. Generate triangles from the grid
 *
 * @param sdf SDF data
 * @param plane Slice plane
 * @param resolution Grid resolution (vertices per axis)
 * @returns Array of triangles with thickness values
 */
export function sliceSDF(
  sdf: SDF,
  plane: SlicePlane,
  resolution: number = 50
): SliceTriangle[] {
  const triangles: SliceTriangle[] = [];
  const { bbox } = sdf.metadata;

  // Determine which axes are in the slice plane
  const [nx, ny, nz] = plane.normal;
  const absNormal = [Math.abs(nx), Math.abs(ny), Math.abs(nz)];
  const maxIdx = absNormal.indexOf(Math.max(...absNormal));

  // Create local 2D coordinate system on the plane
  let u: [number, number, number];
  let v: [number, number, number];

  if (maxIdx === 0) {
    // Normal mostly along X, use YZ plane
    u = [0, 1, 0];
    v = [0, 0, 1];
  } else if (maxIdx === 1) {
    // Normal mostly along Y, use XZ plane
    u = [1, 0, 0];
    v = [0, 0, 1];
  } else {
    // Normal mostly along Z, use XY plane
    u = [1, 0, 0];
    v = [0, 1, 0];
  }

  // Compute extent of slice plane (use bounding box dimensions)
  const size = Math.max(
    bbox.max[0] - bbox.min[0],
    bbox.max[1] - bbox.min[1],
    bbox.max[2] - bbox.min[2]
  );

  const step = size / resolution;

  // Grid starts at corner, offset by half the grid size in the u,v directions
  // This centers the grid on the plane point
  const halfSize = size / 2;

  // Generate grid vertices - all vertices lie ON the plane
  const vertices: Array<{ pos: [number, number, number]; thickness: number }> = [];

  for (let i = 0; i <= resolution; i++) {
    for (let j = 0; j <= resolution; j++) {
      // Calculate position: start at plane.point, then offset in u,v directions
      // Grid goes from -halfSize to +halfSize in each direction
      const uOffset = (i * step - halfSize);
      const vOffset = (j * step - halfSize);

      const pos: [number, number, number] = [
        plane.point[0] + uOffset * u[0] + vOffset * v[0],
        plane.point[1] + uOffset * u[1] + vOffset * v[1],
        plane.point[2] + uOffset * u[2] + vOffset * v[2]
      ];

      const thickness = sampleSDF(sdf, pos);
      vertices.push({ pos, thickness });
    }
  }

  // Generate triangles from grid
  for (let i = 0; i < resolution; i++) {
    for (let j = 0; j < resolution; j++) {
      const idx00 = i * (resolution + 1) + j;
      const idx10 = (i + 1) * (resolution + 1) + j;
      const idx01 = i * (resolution + 1) + (j + 1);
      const idx11 = (i + 1) * (resolution + 1) + (j + 1);

      const v00 = vertices[idx00];
      const v10 = vertices[idx10];
      const v01 = vertices[idx01];
      const v11 = vertices[idx11];

      // Only create triangles if at least one vertex has valid thickness
      if (v00.thickness >= 0 || v10.thickness >= 0 || v01.thickness >= 0) {
        triangles.push({
          vertices: [v00.pos, v10.pos, v01.pos],
          thicknesses: [v00.thickness, v10.thickness, v01.thickness]
        });
      }

      if (v10.thickness >= 0 || v11.thickness >= 0 || v01.thickness >= 0) {
        triangles.push({
          vertices: [v10.pos, v11.pos, v01.pos],
          thicknesses: [v10.thickness, v11.thickness, v01.thickness]
        });
      }
    }
  }

  console.log(`Generated ${triangles.length} slice triangles from SDF (${resolution}x${resolution} grid)`);

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
