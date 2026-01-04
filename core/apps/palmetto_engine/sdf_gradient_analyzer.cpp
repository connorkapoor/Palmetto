#include "sdf_gradient_analyzer.h"
#include <GProp_GProps.hxx>
#include <BRepGProp.hxx>
#include <TopExp_Explorer.hxx>
#include <TopoDS.hxx>
#include <gp_Pnt.hxx>
#include <cmath>
#include <algorithm>
#include <numeric>
#include <iostream>

SDFGradientAnalyzer::SDFGradientAnalyzer(const SDF& sdf, const TopoDS_Shape& shape)
    : sdf_(sdf), shape_(shape) {
}

std::map<int, double> SDFGradientAnalyzer::ComputeStressConcentration() {
    std::cout << "Computing SDF gradients for stress concentration analysis...\n";

    // Compute gradient magnitude at each voxel
    std::vector<double> gradients = ComputeGradients();

    // Map gradients to faces
    std::map<int, double> stress_map = MapGradientsToFaces(gradients);

    // Normalize to [0, 1]
    if (!stress_map.empty()) {
        double max_stress = 0.0;
        for (const auto& pair : stress_map) {
            max_stress = std::max(max_stress, pair.second);
        }

        if (max_stress > 0.0) {
            for (auto& pair : stress_map) {
                pair.second /= max_stress;
            }
        }
    }

    std::cout << "Stress concentration analysis: " << stress_map.size() << " faces analyzed\n";
    return stress_map;
}

std::vector<double> SDFGradientAnalyzer::ComputeGradients() {
    std::vector<double> gradients(sdf_.nx * sdf_.ny * sdf_.nz, 0.0);

    // Compute gradient magnitude using central differences
    // ∇f = (df/dx, df/dy, df/dz)
    // |∇f| = sqrt((df/dx)² + (df/dy)² + (df/dz)²)

    for (int iz = 1; iz < sdf_.nz - 1; iz++) {
        for (int iy = 1; iy < sdf_.ny - 1; iy++) {
            for (int ix = 1; ix < sdf_.nx - 1; ix++) {
                int idx = GetVoxelIndex(ix, iy, iz);

                // Skip invalid voxels (outside shape or no thickness data)
                if (sdf_.thickness[idx] < 0) {
                    continue;
                }

                // Get neighboring voxel indices
                int idx_xp = GetVoxelIndex(ix + 1, iy, iz);
                int idx_xm = GetVoxelIndex(ix - 1, iy, iz);
                int idx_yp = GetVoxelIndex(ix, iy + 1, iz);
                int idx_ym = GetVoxelIndex(ix, iy - 1, iz);
                int idx_zp = GetVoxelIndex(ix, iy, iz + 1);
                int idx_zm = GetVoxelIndex(ix, iy, iz - 1);

                // Skip if neighbors are invalid
                if (sdf_.thickness[idx_xp] < 0 || sdf_.thickness[idx_xm] < 0 ||
                    sdf_.thickness[idx_yp] < 0 || sdf_.thickness[idx_ym] < 0 ||
                    sdf_.thickness[idx_zp] < 0 || sdf_.thickness[idx_zm] < 0) {
                    continue;
                }

                // Central difference gradients
                double grad_x = (sdf_.thickness[idx_xp] - sdf_.thickness[idx_xm]) / (2.0 * sdf_.voxel_size);
                double grad_y = (sdf_.thickness[idx_yp] - sdf_.thickness[idx_ym]) / (2.0 * sdf_.voxel_size);
                double grad_z = (sdf_.thickness[idx_zp] - sdf_.thickness[idx_zm]) / (2.0 * sdf_.voxel_size);

                // Gradient magnitude
                gradients[idx] = std::sqrt(grad_x * grad_x + grad_y * grad_y + grad_z * grad_z);
            }
        }
    }

    return gradients;
}

std::map<int, double> SDFGradientAnalyzer::MapGradientsToFaces(const std::vector<double>& gradients) {
    std::map<int, double> face_stress_map;
    std::map<int, int> face_sample_count;

    // For each face, find nearby voxels and average their gradients
    int face_id = 0;
    for (TopExp_Explorer exp(shape_, TopAbs_FACE); exp.More(); exp.Next(), face_id++) {
        TopoDS_Face face = TopoDS::Face(exp.Current());

        // Get face centroid
        GProp_GProps props;
        BRepGProp::SurfaceProperties(face, props);
        gp_Pnt centroid = props.CentreOfMass();

        // Find voxel containing centroid
        int ix = static_cast<int>((centroid.X() - sdf_.min_x) / sdf_.voxel_size);
        int iy = static_cast<int>((centroid.Y() - sdf_.min_y) / sdf_.voxel_size);
        int iz = static_cast<int>((centroid.Z() - sdf_.min_z) / sdf_.voxel_size);

        if (!IsValidVoxel(ix, iy, iz)) {
            continue;
        }

        // Sample gradient in 3x3x3 neighborhood around centroid
        double total_gradient = 0.0;
        int sample_count = 0;

        for (int dz = -1; dz <= 1; dz++) {
            for (int dy = -1; dy <= 1; dy++) {
                for (int dx = -1; dx <= 1; dx++) {
                    int nx = ix + dx;
                    int ny = iy + dy;
                    int nz = iz + dz;

                    if (!IsValidVoxel(nx, ny, nz)) {
                        continue;
                    }

                    int idx = GetVoxelIndex(nx, ny, nz);

                    if (sdf_.thickness[idx] >= 0 && gradients[idx] > 0) {
                        total_gradient += gradients[idx];
                        sample_count++;
                    }
                }
            }
        }

        if (sample_count > 0) {
            face_stress_map[face_id] = total_gradient / sample_count;
            face_sample_count[face_id] = sample_count;
        }
    }

    return face_stress_map;
}

int SDFGradientAnalyzer::GetVoxelIndex(int ix, int iy, int iz) const {
    return iz * sdf_.ny * sdf_.nx + iy * sdf_.nx + ix;
}

bool SDFGradientAnalyzer::IsValidVoxel(int ix, int iy, int iz) const {
    return ix >= 0 && ix < sdf_.nx &&
           iy >= 0 && iy < sdf_.ny &&
           iz >= 0 && iz < sdf_.nz;
}
