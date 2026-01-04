/**
 * Graph-Aware Thin Wall Recognizer Implementation
 */

#include "thin_wall_recognizer_v2.h"

#include <iostream>
#include <queue>
#include <cmath>
#include <algorithm>
#include <float.h>

// OpenCASCADE includes
#include <BRepAdaptor_Surface.hxx>
#include <BRepBndLib.hxx>
#include <BRepGProp.hxx>
#include <GProp_GProps.hxx>
#include <IntCurvesFace_ShapeIntersector.hxx>
#include <TopExp_Explorer.hxx>
#include <TopoDS.hxx>
#include <gp_Lin.hxx>
#include <Precision.hxx>

// Analysis Situs includes
// TODO: Properly configure Analysis Situs build dependencies
// #include <AnalysisSitus/src/asiAlgo/auxiliary/asiAlgo_CheckThickness.h>

namespace palmetto {

int ThinWallRecognizerV2::feature_id_counter_ = 0;

ThinWallRecognizerV2::ThinWallRecognizerV2(const AAG& aag, const TopoDS_Shape& shape)
    : aag_(aag)
    , shape_(shape)
    , threshold_(5.0)
    , use_as_validation_(true)
{
}

std::vector<Feature> ThinWallRecognizerV2::Recognize(double threshold, bool use_as_validation) {
    threshold_ = threshold;
    use_as_validation_ = use_as_validation;

    std::vector<Feature> thin_walls;
    std::cout << "Graph-aware thin wall recognizer: threshold=" << threshold_ << "mm\n";

    // Phase 1: Find seed faces using graph topology
    std::vector<int> seeds = FindSeedFaces();
    std::cout << "  Found " << seeds.size() << " seed faces via graph analysis\n";

    std::set<int> global_traversed;

    // Phase 2: Grow regions from seeds
    for (int seed_id : seeds) {
        if (global_traversed.count(seed_id)) {
            continue;  // Already part of another region
        }

        // Grow region via BFS
        ThinWallRegion region = GrowRegionFromSeed(seed_id, global_traversed);

        std::cout << "    Seed " << seed_id << " grew to " << region.face_ids.size() << " faces\n";

        if (region.face_ids.size() < 2) {
            std::cout << "      ✗ Too small (need 2+ faces)\n";
            continue;  // Need at least 2 faces
        }

        // Phase 3 & 4: Measure thickness
        ThicknessMeasurement measurement = MeasureRegionThickness(region);
        region.min_thickness = measurement.min_thickness;
        region.max_thickness = measurement.max_thickness;
        region.avg_thickness = measurement.avg_thickness;
        region.variance = measurement.variance;

        std::cout << "      Thickness: avg=" << region.avg_thickness
                  << "mm, min=" << region.min_thickness
                  << "mm, max=" << region.max_thickness << "mm\n";

        // Phase 5: Validate (optionally with Analysis Situs)
        if (!ValidateRegion(region, threshold_)) {
            std::cout << "      ✗ Failed validation\n";
            continue;
        }

        // Phase 6: Create feature
        Feature feature = CreateFeature(region);
        thin_walls.push_back(feature);

        std::cout << "  ✓ Thin wall " << feature.id << ": " << feature.subtype
                  << ", " << region.face_ids.size() << " faces, thickness="
                  << region.avg_thickness << "mm\n";
    }

    std::cout << "  Recognized " << thin_walls.size() << " thin walls\n";
    return thin_walls;
}

// ========================================================================================
// Phase 1: Graph-Based Seed Identification
// ========================================================================================

std::vector<int> ThinWallRecognizerV2::FindSeedFaces() {
    std::vector<int> seeds;
    int face_count = aag_.GetFaceCount();

    for (int i = 0; i < face_count; i++) {
        if (IsThinWallSeedCandidate(i)) {
            seeds.push_back(i);
        }
    }

    return seeds;
}

bool ThinWallRecognizerV2::IsThinWallSeedCandidate(int face_id) {
    const FaceAttributes& attrs = aag_.GetFaceAttributes(face_id);

    // Must be planar (primary criterion for thin walls)
    if (!attrs.is_planar) {
        return false;
    }

    // Check area threshold
    if (attrs.area < MIN_REGION_AREA) {
        return false;
    }

    // Analyze edge characteristics via AAG
    std::vector<int> neighbors = aag_.GetNeighbors(face_id);
    if (neighbors.empty()) {
        return false;
    }

    int smooth_edge_count = 0;
    int convex_edge_count = 0;
    int concave_edge_count = 0;

    for (int neighbor_id : neighbors) {
        double dihedral = aag_.GetDihedralAngle(face_id, neighbor_id);

        if (std::abs(dihedral) > SMOOTH_EDGE_THRESHOLD) {
            smooth_edge_count++;  // Nearly tangent - typical of thin sheets
        }
        else if (dihedral < 0) {
            convex_edge_count++;  // Material bends inward
        }
        else {
            concave_edge_count++;  // Material bends outward
        }
    }

    // Thin wall faces typically have:
    // 1. Some smooth edges (parallel surfaces connected by thickness)
    // 2. Mix of convex/concave at boundaries
    // 3. Not all deeply concave (would be cavity)

    double smooth_ratio = (double)smooth_edge_count / neighbors.size();
    double concave_ratio = (double)concave_edge_count / neighbors.size();

    // Seed criteria: some smooth edges OR low concavity (not a deep cavity)
    bool has_smooth_edges = (smooth_ratio >= 0.25);  // At least 25% smooth
    bool not_deep_cavity = (concave_ratio < 0.70);   // Less than 70% concave

    return (has_smooth_edges || not_deep_cavity);
}

// ========================================================================================
// Phase 2: Region Growing via BFS
// ========================================================================================

ThinWallRegion ThinWallRecognizerV2::GrowRegionFromSeed(int seed_id, std::set<int>& global_traversed) {
    ThinWallRegion region;
    std::queue<int> to_visit;

    to_visit.push(seed_id);
    global_traversed.insert(seed_id);
    region.face_ids.insert(seed_id);

    const FaceAttributes& seed_attrs = aag_.GetFaceAttributes(seed_id);
    gp_Vec seed_normal = seed_attrs.is_planar ? seed_attrs.plane_normal : seed_attrs.normal;

    int propagation_attempts = 0;
    int propagation_rejections = 0;

    while (!to_visit.empty()) {
        int current_id = to_visit.front();
        to_visit.pop();

        // Get adjacent faces via AAG
        std::vector<int> neighbors = aag_.GetNeighbors(current_id);

        for (int neighbor_id : neighbors) {
            propagation_attempts++;

            if (global_traversed.count(neighbor_id)) {
                continue;  // Already visited
            }

            // Check if we should propagate to this neighbor
            if (ShouldPropagate(current_id, neighbor_id)) {
                // For simplicity, just add all neighbors that pass ShouldPropagate
                // The thickness measurement will validate if it's actually a thin wall
                to_visit.push(neighbor_id);
                global_traversed.insert(neighbor_id);
                region.face_ids.insert(neighbor_id);
            } else {
                propagation_rejections++;
            }
        }
    }

    // Debug output
    if (propagation_attempts > 0 && region.face_ids.size() == 1) {
        std::cout << "      DEBUG: " << propagation_attempts << " propagation attempts, "
                  << propagation_rejections << " rejections\n";
    }

    // Compute dominant normal for the region
    region.dominant_normal = ComputeDominantNormal(region.face_ids);

    return region;
}

bool ThinWallRecognizerV2::ShouldPropagate(int from_face, int to_face) {
    const FaceAttributes& to_attrs = aag_.GetFaceAttributes(to_face);

    // Only propagate to planar faces
    if (!to_attrs.is_planar) {
        // std::cout << "        Reject " << to_face << ": not planar\n";
        return false;
    }

    // Check area
    if (to_attrs.area < MIN_REGION_AREA * 0.5) {  // Allow smaller adjacent faces
        // std::cout << "        Reject " << to_face << ": area=" << to_attrs.area << " < " << (MIN_REGION_AREA * 0.5) << "\n";
        return false;
    }

    // Check dihedral angle - propagate along non-smooth edges
    // Smooth edges (near ±180°) are boundaries between wall sides
    double dihedral = aag_.GetDihedralAngle(from_face, to_face);

    bool is_smooth = (std::abs(dihedral) >= SMOOTH_EDGE_THRESHOLD);
    if (is_smooth) {
        // std::cout << "        Reject " << to_face << ": smooth edge (dihedral=" << dihedral << "°)\n";
        return false;
    }

    // std::cout << "        Accept " << to_face << ": dihedral=" << dihedral << "°, area=" << to_attrs.area << "\n";
    return true;
}

// ========================================================================================
// Phase 3 & 4: Thickness Measurement
// ========================================================================================

ThicknessMeasurement ThinWallRecognizerV2::MeasureRegionThickness(const ThinWallRegion& region) {
    ThicknessMeasurement result;

    std::vector<double> thickness_samples;

    // Sample thickness for each face in the region
    for (int face_id : region.face_ids) {
        // Cast ray along dominant normal to find opposite surface
        double thickness = EstimateThicknessAlongNormal(face_id, region.dominant_normal);

        if (thickness > 0.01 && thickness < threshold_ * 2.0) {
            thickness_samples.push_back(thickness);
        }
    }

    if (thickness_samples.empty()) {
        return result;  // No valid measurements
    }

    // Compute statistics
    double sum = 0.0, sum_sq = 0.0;
    double min_t = DBL_MAX, max_t = 0.0;

    for (double t : thickness_samples) {
        sum += t;
        sum_sq += t * t;
        min_t = std::min(min_t, t);
        max_t = std::max(max_t, t);
    }

    result.avg_thickness = sum / thickness_samples.size();
    result.min_thickness = min_t;
    result.max_thickness = max_t;
    result.variance = (sum_sq / thickness_samples.size()) - (result.avg_thickness * result.avg_thickness);
    result.overlap_ratio = (double)thickness_samples.size() / region.face_ids.size();

    return result;
}

double ThinWallRecognizerV2::EstimateThicknessAlongNormal(int face_id, const gp_Vec& normal) {
    const TopoDS_Face& face = aag_.GetFace(face_id);
    const FaceAttributes& attrs = aag_.GetFaceAttributes(face_id);

    try {
        // Get face centroid
        GProp_GProps props;
        BRepGProp::SurfaceProperties(face, props);
        gp_Pnt centroid = props.CentreOfMass();

        // Cast ray along normal in both directions
        gp_Dir dir(normal);
        gp_Lin ray_forward(centroid, dir);
        gp_Lin ray_backward(centroid, dir.Reversed());

        // Try forward direction
        IntCurvesFace_ShapeIntersector intersector;
        intersector.Load(shape_, Precision::Confusion());

        double min_dist_forward = DBL_MAX;
        intersector.Perform(ray_forward, 0, threshold_ * 10.0);

        if (intersector.IsDone() && intersector.NbPnt() > 0) {
            for (int i = 1; i <= intersector.NbPnt(); i++) {
                gp_Pnt hit = intersector.Pnt(i);
                double dist = centroid.Distance(hit);
                if (dist > 0.1 && dist < min_dist_forward) {  // Ignore self-hits
                    min_dist_forward = dist;
                }
            }
        }

        // Try backward direction
        double min_dist_backward = DBL_MAX;
        intersector.Perform(ray_backward, 0, threshold_ * 10.0);

        if (intersector.IsDone() && intersector.NbPnt() > 0) {
            for (int i = 1; i <= intersector.NbPnt(); i++) {
                gp_Pnt hit = intersector.Pnt(i);
                double dist = centroid.Distance(hit);
                if (dist > 0.1 && dist < min_dist_backward) {
                    min_dist_backward = dist;
                }
            }
        }

        // Return the minimum valid thickness
        double thickness = std::min(min_dist_forward, min_dist_backward);
        return (thickness < DBL_MAX) ? thickness : 0.0;
    }
    catch (...) {
        return 0.0;
    }
}

// ========================================================================================
// Phase 5: Analysis Situs Validation
// ========================================================================================

bool ThinWallRecognizerV2::ValidateWithAnalysisSitus(const ThinWallRegion& region, double threshold) {
    // TODO: Integrate asiAlgo_CheckThickness when needed
    // Currently using geometric validation only
    return true;
}

// ========================================================================================
// Phase 6: Validation
// ========================================================================================

bool ThinWallRecognizerV2::ValidateRegion(const ThinWallRegion& region, double threshold) {
    // Criterion 1: Thickness within threshold
    if (region.avg_thickness <= 0.0 || region.avg_thickness > threshold) {
        std::cout << "      ✗ Validation failed: avg_thickness=" << region.avg_thickness << " (must be 0 < t <= " << threshold << ")\n";
        return false;
    }

    // Criterion 2: Reasonable variance
    if (region.avg_thickness > 0.0) {
        double cv = std::sqrt(region.variance) / region.avg_thickness;
        if (cv > THICKNESS_VARIANCE_LIMIT) {
            std::cout << "      ✗ Validation failed: CV=" << cv << " > " << THICKNESS_VARIANCE_LIMIT << " (variance too high)\n";
            return false;
        }
    }

    // Criterion 3: Minimum area
    double total_area = 0.0;
    for (int face_id : region.face_ids) {
        total_area += aag_.GetFaceAttributes(face_id).area;
    }

    if (total_area < MIN_REGION_AREA) {
        std::cout << "      ✗ Validation failed: total_area=" << total_area << " < " << MIN_REGION_AREA << "mm²\n";
        return false;
    }

    // Optional: Analysis Situs validation
    if (use_as_validation_) {
        return ValidateWithAnalysisSitus(region, threshold);
    }

    return true;
}

// ========================================================================================
// Phase 7: Feature Creation
// ========================================================================================

Feature ThinWallRecognizerV2::CreateFeature(const ThinWallRegion& region) {
    Feature feature;
    feature.id = "thin_wall_" + std::to_string(feature_id_counter_++);
    feature.type = "thin_wall";
    feature.subtype = ClassifySubtype(region);
    feature.source = "thin_wall_recognizer_v2";
    feature.confidence = 0.85;

    // Collect face IDs
    feature.face_ids.assign(region.face_ids.begin(), region.face_ids.end());

    // Parameters
    feature.params["avg_thickness"] = region.avg_thickness;
    feature.params["min_thickness"] = region.min_thickness;
    feature.params["max_thickness"] = region.max_thickness;
    feature.params["variance"] = region.variance;

    // Compute total area
    double total_area = 0.0;
    for (int face_id : region.face_ids) {
        total_area += aag_.GetFaceAttributes(face_id).area;
    }
    feature.params["total_area"] = total_area;

    return feature;
}

std::string ThinWallRecognizerV2::ClassifySubtype(const ThinWallRegion& region) {
    // Simple classification based on region characteristics
    if (region.face_ids.size() >= 4) {
        return "sheet";  // Large thin region
    } else if (region.face_ids.size() == 2) {
        return "web";    // Simple rib
    } else {
        return "wall";   // Generic thin wall
    }
}

// ========================================================================================
// Helper Methods
// ========================================================================================

gp_Vec ThinWallRecognizerV2::ComputeDominantNormal(const std::set<int>& face_ids) {
    gp_Vec sum_normal(0, 0, 0);
    int count = 0;

    for (int face_id : face_ids) {
        const FaceAttributes& attrs = aag_.GetFaceAttributes(face_id);
        gp_Vec normal = attrs.is_planar ? attrs.plane_normal : attrs.normal;
        sum_normal += normal;
        count++;
    }

    if (count > 0) {
        sum_normal /= count;
        double mag = sum_normal.Magnitude();
        if (mag > Precision::Confusion()) {
            sum_normal.Normalize();
        }
    }

    return sum_normal;
}

} // namespace palmetto
