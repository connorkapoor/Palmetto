/**
 * Signed Distance Field Generator for Thickness Analysis
 *
 * Generates a regular 3D grid of signed distance values from a CAD shape.
 * Much more efficient and accurate than tetrahedral meshing.
 */

#pragma once

#include <TopoDS_Shape.hxx>
#include <vector>
#include <string>

#ifdef USE_EMBREE
#include "embree_ray_tracer.h"
#endif

namespace palmetto {

/**
 * 3D Signed Distance Field
 */
struct SDF {
    // Grid dimensions
    int nx, ny, nz;

    // Bounding box
    double min_x, max_x;
    double min_y, max_y;
    double min_z, max_z;

    // Voxel size
    double voxel_size;

    // Thickness values at grid points (nx * ny * nz values)
    // Row-major order: thickness[z * nx * ny + y * nx + x]
    std::vector<double> thickness;

    // Statistics
    double min_thickness;
    double max_thickness;
    int valid_count;
    int invalid_count;
};

/**
 * SDF Generator
 */
class SDFGenerator {
public:
    SDFGenerator();
    ~SDFGenerator();

    /**
     * Generate signed distance field from CAD shape (uniform dense grid)
     *
     * @param shape Input CAD shape
     * @param resolution Target number of voxels along longest axis (e.g., 100)
     * @param max_search_distance Maximum distance to search for thickness (mm)
     * @param use_embree Use Intel Embree GPU acceleration if available (default: true)
     * @return SDF structure with thickness values
     */
    SDF GenerateSDF(
        const TopoDS_Shape& shape,
        int resolution = 100,
        double max_search_distance = 50.0,
        bool use_embree = true
    );

    /**
     * Generate adaptive SDF with narrow-band level set (only near boundaries)
     *
     * Uses a two-pass approach:
     * 1. Coarse pass to identify boundary region
     * 2. Fine pass to compute accurate thickness only near surface
     *
     * This reduces 100³ = 1M voxels to ~50k-100k surface voxels (10-20x speedup)
     *
     * @param shape Input CAD shape
     * @param resolution Fine resolution near boundaries (e.g., 200)
     * @param narrow_band_width Width of narrow band in mm (e.g., 10mm)
     * @param use_embree Use Intel Embree GPU acceleration if available (default: true)
     * @return SDF structure with sparse thickness values
     */
    SDF GenerateAdaptiveSDF(
        const TopoDS_Shape& shape,
        int resolution = 200,
        double narrow_band_width = 10.0,
        bool use_embree = true
    );

    /**
     * Export SDF to JSON format for web rendering
     *
     * @param sdf Signed distance field
     * @param output_path Output .json file path
     * @return true if successful
     */
    bool ExportToJSON(const SDF& sdf, const std::string& output_path);
};

} // namespace palmetto
