/**
 * Signed Distance Field Generator Implementation
 */

#include "sdf_generator.h"

// OpenCASCADE for geometry processing
#include <BRepBndLib.hxx>
#include <Bnd_Box.hxx>
#include <BRepClass3d_SolidClassifier.hxx>
#include <BRepExtrema_DistShapeShape.hxx>
#include <BRepBuilderAPI_MakeVertex.hxx>
#include <TopoDS_Vertex.hxx>
#include <gp_Pnt.hxx>
#include <gp_Dir.hxx>
#include <gp_Lin.hxx>
#include <IntCurvesFace_ShapeIntersector.hxx>
#include <Precision.hxx>

// Standard library
#include <iostream>
#include <fstream>
#include <sstream>
#include <iomanip>
#include <cmath>
#include <limits>
#include <algorithm>
#include <atomic>

namespace palmetto {

SDFGenerator::SDFGenerator() {
}

SDFGenerator::~SDFGenerator() {
}

SDF SDFGenerator::GenerateSDF(
    const TopoDS_Shape& shape,
    int resolution,
    double max_search_distance,
    bool use_embree
) {
    std::cout << "  Generating " << resolution << "³ voxel grid...\n";

    SDF sdf;

    // Compute bounding box
    Bnd_Box bbox;
    BRepBndLib::Add(shape, bbox);
    bbox.Get(sdf.min_x, sdf.min_y, sdf.min_z, sdf.max_x, sdf.max_y, sdf.max_z);

    // Add small padding
    double padding = 0.1;
    sdf.min_x -= padding;
    sdf.min_y -= padding;
    sdf.min_z -= padding;
    sdf.max_x += padding;
    sdf.max_y += padding;
    sdf.max_z += padding;

    // Compute grid dimensions (uniform voxels)
    double size_x = sdf.max_x - sdf.min_x;
    double size_y = sdf.max_y - sdf.min_y;
    double size_z = sdf.max_z - sdf.min_z;
    double max_size = std::max({size_x, size_y, size_z});

    sdf.voxel_size = max_size / resolution;

    // Grid dimensions
    sdf.nx = static_cast<int>(std::ceil(size_x / sdf.voxel_size)) + 1;
    sdf.ny = static_cast<int>(std::ceil(size_y / sdf.voxel_size)) + 1;
    sdf.nz = static_cast<int>(std::ceil(size_z / sdf.voxel_size)) + 1;

    int total_voxels = sdf.nx * sdf.ny * sdf.nz;
    sdf.thickness.resize(total_voxels, -1.0);

    std::cout << "  Grid: " << sdf.nx << " × " << sdf.ny << " × " << sdf.nz
              << " = " << total_voxels << " voxels\n";
    std::cout << "  Voxel size: " << sdf.voxel_size << " mm\n";
    std::cout << "  Computing thickness at each voxel center...\n";

    // Compute thickness at each voxel center
    sdf.min_thickness = std::numeric_limits<double>::max();
    sdf.max_thickness = 0.0;
    sdf.valid_count = 0;
    sdf.invalid_count = 0;

    int progress_interval = total_voxels / 20;  // Report every 5%

    // Build Embree acceleration structure if enabled
#ifdef USE_EMBREE
    EmbreeRayTracer embree_tracer;
    bool embree_available = false;
    if (use_embree) {
        std::cout << "  Building Embree acceleration structure...\n";
        embree_available = embree_tracer.Build(shape, 0.05);
        if (!embree_available) {
            std::cout << "  Embree build failed, falling back to CPU mode\n";
        } else {
            std::cout << "  Embree acceleration enabled (5-10x speedup expected)\n";
        }
    }
#endif

    // Use all 6 ray directions for accurate thickness measurement
    static const gp_Dir directions[6] = {
        gp_Dir(1, 0, 0),   // +X
        gp_Dir(-1, 0, 0),  // -X
        gp_Dir(0, 1, 0),   // +Y
        gp_Dir(0, -1, 0),  // -Y
        gp_Dir(0, 0, 1),   // +Z
        gp_Dir(0, 0, -1)   // -Z
    };

    // TODO: Future optimization - Adaptive/sparse voxelization
    // Instead of uniform dense grid, use:
    // - Octree subdivision (fine near boundaries, coarse in interior)
    // - Narrow-band level set (only compute within shell distance of surface)
    // - Skip deep interior voxels entirely (we already know they're inside)
    // This would reduce 100³ = 1M voxels to ~50k-100k surface voxels (10-20x speedup)

    #pragma omp parallel
    {
        // Thread-local variables to reduce contention
        double local_min_thickness = std::numeric_limits<double>::max();
        double local_max_thickness = 0.0;
        int local_valid_count = 0;
        int local_invalid_count = 0;

        // Thread-local intersector for CPU fallback (always needed even when Embree is available)
        IntCurvesFace_ShapeIntersector thread_intersector;
        thread_intersector.Load(shape, Precision::Confusion());

        #pragma omp for collapse(3) schedule(dynamic)
        for (int iz = 0; iz < sdf.nz; iz++) {
            for (int iy = 0; iy < sdf.ny; iy++) {
                for (int ix = 0; ix < sdf.nx; ix++) {
                    int idx = iz * sdf.nx * sdf.ny + iy * sdf.nx + ix;

                    // Voxel center position
                    double x = sdf.min_x + ix * sdf.voxel_size;
                    double y = sdf.min_y + iy * sdf.voxel_size;
                    double z = sdf.min_z + iz * sdf.voxel_size;

                    gp_Pnt point(x, y, z);

                    // Check if point is inside using Embree (much faster than BRepClass3d!)
                    bool is_inside = false;
#ifdef USE_EMBREE
                    if (embree_available) {
                        is_inside = embree_tracer.IsInside(point);
                    } else
#endif
                    {
                        // CPU fallback: use BREP classifier
                        BRepClass3d_SolidClassifier classifier(shape, point, 1e-6);
                        TopAbs_State state = classifier.State();
                        is_inside = (state == TopAbs_IN);
                    }

                    if (is_inside) {
                        // Point is inside - use ray casting to find distance to wall
                        double min_distance = max_search_distance;
                        bool found_hit = false;

                        for (int dir = 0; dir < 6; dir++) {
                            double distance = -1.0;

#ifdef USE_EMBREE
                            if (embree_available) {
                                distance = embree_tracer.CastRay(point, directions[dir], max_search_distance);
                            } else
#endif
                            {
                                // CPU fallback
                                gp_Lin ray(point, directions[dir]);
                                thread_intersector.Perform(ray, 0.0, max_search_distance);

                                if (thread_intersector.NbPnt() > 0) {
                                    double closest = max_search_distance;
                                    for (int i = 1; i <= thread_intersector.NbPnt(); i++) {
                                        double param = thread_intersector.WParameter(i);
                                        if (param > 0.01 && param < closest) {
                                            closest = param;
                                            found_hit = true;
                                        }
                                    }
                                    distance = closest;
                                }
                            }

                            if (distance > 0 && distance < min_distance) {
                                min_distance = distance;
                                found_hit = true;
                            }

                            // Early termination: if after 3 rays we're still very thick, skip remaining rays
                            // This saves ~50% of ray casts for deep interior voxels
                            if (dir >= 2 && min_distance > max_search_distance * 0.8) {
                                break;  // Deep inside, no need for more rays
                            }
                        }

                        if (found_hit && min_distance < max_search_distance) {
                            // Thickness = 2 × distance to nearest wall
                            double thickness = 2.0 * min_distance;
                            sdf.thickness[idx] = thickness;

                            local_valid_count++;
                            local_min_thickness = std::min(local_min_thickness, thickness);
                            local_max_thickness = std::max(local_max_thickness, thickness);
                        } else {
                            local_invalid_count++;
                        }
                    } else {
                        // Point is outside or on boundary - mark as invalid
                        local_invalid_count++;
                    }

                    // Progress reporting
                    if (progress_interval > 0 && idx % progress_interval == 0) {
                        #pragma omp critical
                        {
                            std::cout << "    Progress: " << (idx * 100 / total_voxels) << "%\r" << std::flush;
                        }
                    }
                }
            }
        }

        // Merge thread-local results
        #pragma omp critical
        {
            sdf.valid_count += local_valid_count;
            sdf.invalid_count += local_invalid_count;
            sdf.min_thickness = std::min(sdf.min_thickness, local_min_thickness);
            sdf.max_thickness = std::max(sdf.max_thickness, local_max_thickness);
        }
    }

    std::cout << "    Progress: 100%\n";
    std::cout << "  ✓ Valid voxels: " << sdf.valid_count << " ("
              << (sdf.valid_count * 100.0 / total_voxels) << "%)\n";
    std::cout << "  Thickness range: " << sdf.min_thickness << " - " << sdf.max_thickness << " mm\n";

    return sdf;
}

SDF SDFGenerator::GenerateAdaptiveSDF(
    const TopoDS_Shape& shape,
    int resolution,
    double narrow_band_width,
    bool use_embree
) {
    std::cout << "  Generating adaptive SDF with narrow-band level set...\n";
    std::cout << "  Fine resolution: " << resolution << "³ near boundaries\n";
    std::cout << "  Narrow band width: " << narrow_band_width << " mm\n";

    SDF sdf;

    // Compute bounding box
    Bnd_Box bbox;
    BRepBndLib::Add(shape, bbox);
    bbox.Get(sdf.min_x, sdf.min_y, sdf.min_z, sdf.max_x, sdf.max_y, sdf.max_z);

    // Add small padding
    double padding = 0.1;
    sdf.min_x -= padding;
    sdf.min_y -= padding;
    sdf.min_z -= padding;
    sdf.max_x += padding;
    sdf.max_y += padding;
    sdf.max_z += padding;

    // Compute grid dimensions (uniform voxels for fine resolution)
    double size_x = sdf.max_x - sdf.min_x;
    double size_y = sdf.max_y - sdf.min_y;
    double size_z = sdf.max_z - sdf.min_z;
    double max_size = std::max({size_x, size_y, size_z});

    sdf.voxel_size = max_size / resolution;

    // Grid dimensions
    sdf.nx = static_cast<int>(std::ceil(size_x / sdf.voxel_size)) + 1;
    sdf.ny = static_cast<int>(std::ceil(size_y / sdf.voxel_size)) + 1;
    sdf.nz = static_cast<int>(std::ceil(size_z / sdf.voxel_size)) + 1;

    int total_voxels = sdf.nx * sdf.ny * sdf.nz;
    sdf.thickness.resize(total_voxels, -1.0);

    std::cout << "  Full grid: " << sdf.nx << " × " << sdf.ny << " × " << sdf.nz
              << " = " << total_voxels << " voxels\n";
    std::cout << "  Voxel size: " << sdf.voxel_size << " mm\n";

    // PASS 1: Coarse identification of boundary region using distance to surface
    std::cout << "  [Pass 1/2] Identifying boundary region (coarse)...\n";

    // Use a coarse grid (1/4 resolution) to quickly find near-surface voxels
    int coarse_factor = 4;
    int coarse_nx = sdf.nx / coarse_factor;
    int coarse_ny = sdf.ny / coarse_factor;
    int coarse_nz = sdf.nz / coarse_factor;
    double coarse_voxel_size = sdf.voxel_size * coarse_factor;

    std::vector<bool> boundary_region(coarse_nx * coarse_ny * coarse_nz, false);

    #pragma omp parallel for collapse(3)
    for (int iz = 0; iz < coarse_nz; iz++) {
        for (int iy = 0; iy < coarse_ny; iy++) {
            for (int ix = 0; ix < coarse_nx; ix++) {
                int idx = iz * coarse_nx * coarse_ny + iy * coarse_nx + ix;

                // Coarse voxel center
                double x = sdf.min_x + (ix + 0.5) * coarse_voxel_size;
                double y = sdf.min_y + (iy + 0.5) * coarse_voxel_size;
                double z = sdf.min_z + (iz + 0.5) * coarse_voxel_size;

                gp_Pnt point(x, y, z);

                // Quick distance check to surface
                BRepExtrema_DistShapeShape distCalc(BRepBuilderAPI_MakeVertex(point), shape);
                distCalc.Perform();

                if (distCalc.IsDone() && distCalc.NbSolution() > 0) {
                    double dist = distCalc.Value();

                    // Mark as boundary region if within narrow band
                    if (dist <= narrow_band_width) {
                        boundary_region[idx] = true;
                    }
                }
            }
        }
    }

    int boundary_voxels = std::count(boundary_region.begin(), boundary_region.end(), true);
    std::cout << "  Found " << boundary_voxels << " coarse voxels near boundary ("
              << (boundary_voxels * 100.0 / (coarse_nx * coarse_ny * coarse_nz)) << "%)\n";

    // PASS 2: Fine thickness computation only in boundary regions
    std::cout << "  [Pass 2/2] Computing thickness in boundary region (fine)...\n";

    // Build Embree acceleration structure if enabled
#ifdef USE_EMBREE
    EmbreeRayTracer embree_tracer;
    bool embree_available = false;
    if (use_embree) {
        std::cout << "  Building Embree acceleration structure...\n";
        embree_available = embree_tracer.Build(shape, 0.05);
        if (!embree_available) {
            std::cout << "  Embree build failed, falling back to CPU mode\n";
        } else {
            std::cout << "  Embree acceleration enabled\n";
        }
    }
#endif

    // Use all 6 ray directions
    static const gp_Dir directions[6] = {
        gp_Dir(1, 0, 0),   // +X
        gp_Dir(-1, 0, 0),  // -X
        gp_Dir(0, 1, 0),   // +Y
        gp_Dir(0, -1, 0),  // -Y
        gp_Dir(0, 0, 1),   // +Z
        gp_Dir(0, 0, -1)   // -Z
    };

    sdf.min_thickness = std::numeric_limits<double>::max();
    sdf.max_thickness = 0.0;
    sdf.valid_count = 0;
    sdf.invalid_count = 0;

    std::atomic<int> voxels_processed(0);
    int voxels_to_process = 0;

    // Count voxels to process
    for (int iz = 0; iz < sdf.nz; iz++) {
        for (int iy = 0; iy < sdf.ny; iy++) {
            for (int ix = 0; ix < sdf.nx; ix++) {
                int coarse_ix = ix / coarse_factor;
                int coarse_iy = iy / coarse_factor;
                int coarse_iz = iz / coarse_factor;

                if (coarse_ix >= coarse_nx) coarse_ix = coarse_nx - 1;
                if (coarse_iy >= coarse_ny) coarse_iy = coarse_ny - 1;
                if (coarse_iz >= coarse_nz) coarse_iz = coarse_nz - 1;

                int coarse_idx = coarse_iz * coarse_nx * coarse_ny + coarse_iy * coarse_nx + coarse_ix;

                if (boundary_region[coarse_idx]) {
                    voxels_to_process++;
                }
            }
        }
    }

    std::cout << "  Processing " << voxels_to_process << " fine voxels ("
              << (voxels_to_process * 100.0 / total_voxels) << "% of grid)\\n";

    #pragma omp parallel
    {
        // Thread-local variables
        double local_min_thickness = std::numeric_limits<double>::max();
        double local_max_thickness = 0.0;
        int local_valid_count = 0;
        int local_invalid_count = 0;

        // Thread-local intersector for CPU fallback
        IntCurvesFace_ShapeIntersector thread_intersector;
        thread_intersector.Load(shape, Precision::Confusion());

        #pragma omp for collapse(3) schedule(dynamic)
        for (int iz = 0; iz < sdf.nz; iz++) {
            for (int iy = 0; iy < sdf.ny; iy++) {
                for (int ix = 0; ix < sdf.nx; ix++) {
                    // Map to coarse grid
                    int coarse_ix = ix / coarse_factor;
                    int coarse_iy = iy / coarse_factor;
                    int coarse_iz = iz / coarse_factor;

                    if (coarse_ix >= coarse_nx) coarse_ix = coarse_nx - 1;
                    if (coarse_iy >= coarse_ny) coarse_iy = coarse_ny - 1;
                    if (coarse_iz >= coarse_nz) coarse_iz = coarse_nz - 1;

                    int coarse_idx = coarse_iz * coarse_nx * coarse_ny + coarse_iy * coarse_nx + coarse_ix;

                    // Skip if not in boundary region
                    if (!boundary_region[coarse_idx]) {
                        continue;
                    }

                    int idx = iz * sdf.nx * sdf.ny + iy * sdf.nx + ix;

                    // Fine voxel center position
                    double x = sdf.min_x + ix * sdf.voxel_size;
                    double y = sdf.min_y + iy * sdf.voxel_size;
                    double z = sdf.min_z + iz * sdf.voxel_size;

                    gp_Pnt point(x, y, z);

                    // Check if point is inside using Embree (much faster than BRepClass3d!)
                    bool is_inside = false;
#ifdef USE_EMBREE
                    if (embree_available) {
                        is_inside = embree_tracer.IsInside(point);
                    } else
#endif
                    {
                        // CPU fallback: use BREP classifier
                        BRepClass3d_SolidClassifier classifier(shape, point, 1e-6);
                        TopAbs_State state = classifier.State();
                        is_inside = (state == TopAbs_IN);
                    }

                    if (is_inside) {
                        // Point is inside - use ray casting to find distance to wall
                        double min_distance = narrow_band_width;
                        bool found_hit = false;

                        for (int dir = 0; dir < 6; dir++) {
                            double distance = -1.0;

#ifdef USE_EMBREE
                            if (embree_available) {
                                distance = embree_tracer.CastRay(point, directions[dir], narrow_band_width);
                            } else
#endif
                            {
                                // CPU fallback
                                gp_Lin ray(point, directions[dir]);
                                thread_intersector.Perform(ray, 0.0, narrow_band_width);

                                if (thread_intersector.NbPnt() > 0) {
                                    double closest = narrow_band_width;
                                    for (int i = 1; i <= thread_intersector.NbPnt(); i++) {
                                        double param = thread_intersector.WParameter(i);
                                        if (param > 0.01 && param < closest) {
                                            closest = param;
                                            found_hit = true;
                                        }
                                    }
                                    distance = closest;
                                }
                            }

                            if (distance > 0 && distance < min_distance) {
                                min_distance = distance;
                                found_hit = true;
                            }

                            // Early termination
                            if (dir >= 2 && min_distance > narrow_band_width * 0.8) {
                                break;
                            }
                        }

                        if (found_hit && min_distance < narrow_band_width) {
                            // Thickness = 2 × distance to nearest wall
                            double thickness = 2.0 * min_distance;
                            sdf.thickness[idx] = thickness;

                            local_valid_count++;
                            local_min_thickness = std::min(local_min_thickness, thickness);
                            local_max_thickness = std::max(local_max_thickness, thickness);
                        } else {
                            local_invalid_count++;
                        }
                    } else {
                        // Point is outside or on boundary - mark as invalid
                        local_invalid_count++;
                    }

                    // Progress reporting
                    voxels_processed++;
                    int processed = voxels_processed.load();
                    if (processed % (voxels_to_process / 20) == 0) {
                        #pragma omp critical
                        {
                            std::cout << "    Progress: " << (processed * 100 / voxels_to_process) << "%\r" << std::flush;
                        }
                    }
                }
            }
        }

        // Merge thread-local results
        #pragma omp critical
        {
            sdf.valid_count += local_valid_count;
            sdf.invalid_count += local_invalid_count;
            sdf.min_thickness = std::min(sdf.min_thickness, local_min_thickness);
            sdf.max_thickness = std::max(sdf.max_thickness, local_max_thickness);
        }
    }

    std::cout << "    Progress: 100%\n";
    std::cout << "  ✓ Valid voxels: " << sdf.valid_count << " ("
              << (sdf.valid_count * 100.0 / voxels_to_process) << "% of processed)\n";
    std::cout << "  ✓ Sparse coverage: " << (voxels_to_process * 100.0 / total_voxels)
              << "% of full grid\n";
    std::cout << "  Thickness range: " << sdf.min_thickness << " - " << sdf.max_thickness << " mm\n";

    return sdf;
}

bool SDFGenerator::ExportToJSON(const SDF& sdf, const std::string& output_path) {
    std::ofstream file(output_path);
    if (!file.is_open()) {
        std::cerr << "ERROR: Cannot write to " << output_path << "\n";
        return false;
    }

    file << std::fixed << std::setprecision(6);

    file << "{\n";
    file << "  \"version\": \"1.0\",\n";
    file << "  \"type\": \"thickness_sdf\",\n";

    // Metadata
    file << "  \"metadata\": {\n";
    file << "    \"nx\": " << sdf.nx << ",\n";
    file << "    \"ny\": " << sdf.ny << ",\n";
    file << "    \"nz\": " << sdf.nz << ",\n";
    file << "    \"voxel_count\": " << (sdf.nx * sdf.ny * sdf.nz) << ",\n";
    file << "    \"voxel_size\": " << sdf.voxel_size << ",\n";
    file << "    \"valid_voxels\": " << sdf.valid_count << ",\n";
    file << "    \"thickness_range\": [" << sdf.min_thickness << ", " << sdf.max_thickness << "],\n";
    file << "    \"bbox\": {\n";
    file << "      \"min\": [" << sdf.min_x << ", " << sdf.min_y << ", " << sdf.min_z << "],\n";
    file << "      \"max\": [" << sdf.max_x << ", " << sdf.max_y << ", " << sdf.max_z << "]\n";
    file << "    }\n";
    file << "  },\n";

    // Thickness data (flat array in row-major order)
    file << "  \"thickness\": [";
    for (size_t i = 0; i < sdf.thickness.size(); i++) {
        if (i > 0) file << ",";
        if (i % sdf.nx == 0) file << "\n    ";  // New row
        file << sdf.thickness[i];
    }
    file << "\n  ]\n";

    file << "}\n";
    file.close();

    return true;
}

} // namespace palmetto
