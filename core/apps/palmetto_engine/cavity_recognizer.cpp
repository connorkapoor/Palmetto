/**
 * Cavity Recognizer Implementation
 */

#include "cavity_recognizer.h"

#include <iostream>
#include <queue>
#include <sstream>
#include <iomanip>
#include <algorithm>

// OpenCASCADE includes
#include <TopExp_Explorer.hxx>
#include <TopoDS.hxx>
#include <BRepTools.hxx>
#include <TopExp.hxx>

namespace palmetto {

int CavityRecognizer::feature_id_counter_ = 0;

CavityRecognizer::CavityRecognizer(const AAG& aag)
    : aag_(aag)
{
}

std::vector<Feature> CavityRecognizer::Recognize(double max_volume) {
    std::vector<Feature> cavities;

    std::cout << "Cavity recognizer: Finding cavity features\n";

    // Find seed faces (faces with convex edges indicating cavity boundaries)
    std::vector<int> seeds = FindSeedFaces();
    std::cout << "  Found " << seeds.size() << " seed faces\n";

    std::set<int> global_traversed;

    for (int seed_id : seeds) {
        if (global_traversed.count(seed_id)) {
            continue;  // Already part of a recognized cavity
        }

        // Propagate from seed to find connected cavity faces
        std::set<int> traversed;
        std::set<int> cavity_faces = PropagateFromSeed(seed_id, traversed);

        // Add traversed faces to global set
        global_traversed.insert(traversed.begin(), traversed.end());

        // Validate cavity
        if (ValidateCavity(cavity_faces, max_volume)) {
            Feature cavity = CreateCavity(cavity_faces);
            cavities.push_back(cavity);
            std::cout << "  ✓ Recognized cavity with " << cavity_faces.size() << " faces\n";
        } else {
            // Debug: log why validation failed
            if (cavity_faces.size() < 3) {
                // Skip logging for single-face cavities (too noisy)
            } else if (cavity_faces.size() >= (size_t)(aag_.GetFaceCount() * 0.25)) {
                std::cout << "  × Rejected cavity (too large: " << cavity_faces.size() << "/" << aag_.GetFaceCount() << " faces = " << (100.0 * cavity_faces.size() / aag_.GetFaceCount()) << "%, limit 25%)\n";
            } else {
                // Calculate why it failed for debugging
                int boundary_count = 0;
                for (int face_id : cavity_faces) {
                    std::vector<int> neighbors = aag_.GetNeighbors(face_id);
                    for (int neighbor_id : neighbors) {
                        if (cavity_faces.find(neighbor_id) == cavity_faces.end()) {
                            double dihedral = aag_.GetDihedralAngle(face_id, neighbor_id);
                            if (dihedral < -CONVEX_ANGLE_THRESHOLD && std::abs(dihedral) < 177.0) {
                                boundary_count++;
                                break;
                            }
                        }
                    }
                }
                double boundary_ratio = (double)boundary_count / cavity_faces.size();
                std::cout << "  × Rejected cavity (" << cavity_faces.size() << " faces, "
                          << boundary_count << " boundaries = " << (boundary_ratio * 100) << "%, need ≥20%)\n";
            }
        }
    }

    std::cout << "Cavity recognizer: Recognized " << cavities.size() << " cavities\n";

    return cavities;
}

std::vector<int> CavityRecognizer::FindSeedFaces() {
    std::vector<int> seeds;

    int face_count = aag_.GetFaceCount();

    for (int i = 0; i < face_count; i++) {
        // Find faces that are inside cavities (have mostly/all concave edges to neighbors)
        // Concave edges point "outward" from the material, indicating we're inside a depression
        std::vector<int> neighbors = aag_.GetNeighbors(i);

        if (neighbors.empty()) continue;

        int concave_edge_count = 0;
        int convex_edge_count = 0;

        for (int neighbor_id : neighbors) {
            double dihedral = aag_.GetDihedralAngle(i, neighbor_id);

            // In AAG convention:
            // Positive angle = CONCAVE edge (material bends outward, inside a pocket)
            // Negative angle = CONVEX edge (material bends inward, pocket boundary)

            if (dihedral > CONVEX_ANGLE_THRESHOLD && std::abs(dihedral) < 177.0) {
                // Positive, not smooth → concave edge (inside pocket)
                concave_edge_count++;
            }
            else if (dihedral < -CONVEX_ANGLE_THRESHOLD && std::abs(dihedral) < 177.0) {
                // Negative, not smooth → convex edge (pocket boundary)
                convex_edge_count++;
            }
        }

        // Seed faces should have MOSTLY concave edges (inside a depression)
        // Require 60% concave edges for reasonable selectivity
        double concave_ratio = (double)concave_edge_count / neighbors.size();
        if (concave_ratio >= 0.6 && concave_edge_count >= 2) {
            seeds.push_back(i);
        }
    }

    return seeds;
}

std::set<int> CavityRecognizer::PropagateFromSeed(int seed_id, std::set<int>& traversed) {
    std::set<int> cavity_faces;
    std::queue<int> to_visit;

    to_visit.push(seed_id);
    traversed.insert(seed_id);

    while (!to_visit.empty()) {
        int current_id = to_visit.front();
        to_visit.pop();

        cavity_faces.insert(current_id);

        // Get neighbors
        std::vector<int> neighbors = aag_.GetNeighbors(current_id);

        for (int neighbor_id : neighbors) {
            if (traversed.count(neighbor_id)) {
                continue;  // Already visited
            }

            // Check if we should propagate through this edge
            if (ShouldPropagate(current_id, neighbor_id)) {
                to_visit.push(neighbor_id);
                traversed.insert(neighbor_id);
            }
        }
    }

    return cavity_faces;
}

bool CavityRecognizer::ShouldPropagate(int face1_id, int face2_id) {
    double dihedral = aag_.GetDihedralAngle(face1_id, face2_id);

    // Propagate through:
    // 1. Smooth edges (|angle| ≈ 180°) - continuous surface
    // 2. Concave edges (angle > 0, not smooth) - inside cavity
    // DO NOT propagate through convex edges (angle < 0) - these are cavity boundaries

    double abs_angle = std::abs(dihedral);

    // Smooth edge: very close to ±180°
    bool is_smooth = abs_angle > 177.0;

    // Concave edge: positive angle, not smooth
    bool is_concave = (dihedral > CONVEX_ANGLE_THRESHOLD && abs_angle < 177.0);

    return is_smooth || is_concave;
}

bool CavityRecognizer::ValidateCavity(const std::set<int>& cavity_faces, double max_volume) {
    // Check 1: Must have at least 3 faces
    if (cavity_faces.size() < 3) {
        return false;
    }

    // Check 2: Must not be too large
    int total_faces = aag_.GetFaceCount();
    // Cavities should be <25% of total faces (pockets are localized features)
    if (cavity_faces.size() >= (size_t)(total_faces * 0.25)) {
        return false;
    }

    // Additional check: Cavities with >15 faces need very strong boundary definition
    if (cavity_faces.size() > 15) {
        // For large cavity candidates, require 25% boundary ratio
        int boundary_count = 0;
        for (int face_id : cavity_faces) {
            std::vector<int> neighbors = aag_.GetNeighbors(face_id);
            for (int neighbor_id : neighbors) {
                if (cavity_faces.find(neighbor_id) == cavity_faces.end()) {
                    double dihedral = aag_.GetDihedralAngle(face_id, neighbor_id);
                    if (dihedral < -CONVEX_ANGLE_THRESHOLD && std::abs(dihedral) < 177.0) {
                        boundary_count++;
                        break;
                    }
                }
            }
        }
        double boundary_ratio = (double)boundary_count / cavity_faces.size();
        if (boundary_ratio < 0.25) {
            return false;  // Large cavities need strong boundaries
        }
    }

    // Check 3: Volume threshold
    double volume = EstimateCavityVolume(cavity_faces);
    if (volume > max_volume) {
        return false;
    }

    // Check 4: Must have boundary faces (faces with convex edges)
    // At least 30% of cavity faces should have clear convex boundaries
    int boundary_face_count = 0;
    for (int face_id : cavity_faces) {
        std::vector<int> neighbors = aag_.GetNeighbors(face_id);

        for (int neighbor_id : neighbors) {
            // Check if neighbor is outside cavity
            if (cavity_faces.find(neighbor_id) == cavity_faces.end()) {
                double dihedral = aag_.GetDihedralAngle(face_id, neighbor_id);

                // Convex edge to outside face = cavity boundary (negative angle)
                if (dihedral < -CONVEX_ANGLE_THRESHOLD && std::abs(dihedral) < 177.0) {
                    boundary_face_count++;
                    break;
                }
            }
        }
    }

    // Require at least 20% of faces to have clear boundaries
    double boundary_ratio = (double)boundary_face_count / cavity_faces.size();
    if (boundary_ratio < 0.2) {
        return false;  // Not a well-defined cavity
    }

    return true;
}

double CavityRecognizer::EstimateCavityVolume(const std::set<int>& cavity_faces) {
    // Rough volume estimate: sum of face areas
    // This is a simplified approximation
    double total_area = 0.0;

    for (int face_id : cavity_faces) {
        const FaceAttributes& attrs = aag_.GetFaceAttributes(face_id);
        total_area += attrs.area;
    }

    // Assume average depth proportional to sqrt(area)
    double estimated_depth = std::sqrt(total_area);

    return total_area * estimated_depth * 0.1;  // Rough estimate
}

Feature CavityRecognizer::CreateCavity(const std::set<int>& cavity_faces) {
    Feature feature;

    // Generate ID
    std::ostringstream oss;
    oss << "cavity_" << std::setfill('0') << std::setw(4) << feature_id_counter_++;
    feature.id = oss.str();

    feature.type = "cavity";
    feature.subtype = "pocket";  // Default subtype
    feature.source = "cavity_recognizer";
    feature.confidence = 0.70;  // Lower confidence for cavity detection

    // Add all cavity faces
    feature.face_ids = std::vector<int>(cavity_faces.begin(), cavity_faces.end());

    // Calculate parameters
    double total_area = 0.0;
    for (int face_id : cavity_faces) {
        const FaceAttributes& attrs = aag_.GetFaceAttributes(face_id);
        total_area += attrs.area;
    }

    feature.params["face_count"] = static_cast<double>(cavity_faces.size());
    feature.params["total_area_mm2"] = total_area;
    feature.params["estimated_volume_mm3"] = EstimateCavityVolume(cavity_faces);

    return feature;
}

} // namespace palmetto
