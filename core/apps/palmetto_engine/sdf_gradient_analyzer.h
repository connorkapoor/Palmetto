#ifndef SDF_GRADIENT_ANALYZER_H
#define SDF_GRADIENT_ANALYZER_H

#include "sdf_generator.h"
#include <TopoDS_Shape.hxx>
#include <TopoDS_Face.hxx>
#include <map>
#include <vector>

using namespace palmetto;

/**
 * SDF Gradient Analyzer
 *
 * Computes stress concentration indicators from SDF thickness data by analyzing
 * gradient magnitude. Sharp changes in thickness (high gradient) indicate
 * potential stress concentration points.
 */
class SDFGradientAnalyzer {
public:
    SDFGradientAnalyzer(const SDF& sdf, const TopoDS_Shape& shape);

    /**
     * Compute stress concentration for all faces.
     * Returns normalized stress concentration index (0-1):
     * - 0 = uniform thickness (low stress)
     * - 1 = sharp thickness change (high stress concentration)
     *
     * @return Map of face_id -> stress_concentration (0-1)
     */
    std::map<int, double> ComputeStressConcentration();

private:
    const SDF& sdf_;
    const TopoDS_Shape& shape_;

    /**
     * Compute gradient magnitude at each voxel in the SDF.
     *
     * @return Vector of gradient magnitudes (nx * ny * nz values)
     */
    std::vector<double> ComputeGradients();

    /**
     * Map voxel gradient data back to faces by finding voxels
     * that intersect or are near each face.
     *
     * @param gradients Gradient magnitude at each voxel
     * @return Map of face_id -> average gradient magnitude
     */
    std::map<int, double> MapGradientsToFaces(const std::vector<double>& gradients);

    /**
     * Get voxel index from 3D coordinates.
     *
     * @param ix, iy, iz Voxel coordinates
     * @return Linear index in SDF arrays
     */
    int GetVoxelIndex(int ix, int iy, int iz) const;

    /**
     * Check if voxel coordinates are valid.
     */
    bool IsValidVoxel(int ix, int iy, int iz) const;
};

#endif // SDF_GRADIENT_ANALYZER_H
