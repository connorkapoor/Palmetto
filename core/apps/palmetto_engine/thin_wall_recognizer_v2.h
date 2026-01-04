/**
 * Graph-Aware Thin Wall Recognizer (Version 2)
 *
 * Uses AAG topology, dihedral angles, and Analysis Situs thickness checking
 */

#pragma once

#include "aag.h"
#include "engine.h"
#include "thin_wall_recognizer.h"  // Reuse ThicknessMeasurement struct
#include <set>
#include <vector>
#include <map>

namespace palmetto {

/**
 * Thin wall region identified via graph traversal
 */
struct ThinWallRegion {
    std::set<int> face_ids;              // All faces in the thin wall region
    std::set<int> opposing_face_pairs;   // Pairs of opposing faces
    double min_thickness;
    double max_thickness;
    double avg_thickness;
    double variance;
    gp_Vec dominant_normal;              // Primary wall orientation
};

/**
 * Graph-aware thin wall recognizer using AAG topology
 */
class ThinWallRecognizerV2 {
public:
    explicit ThinWallRecognizerV2(const AAG& aag, const TopoDS_Shape& shape);

    /**
     * Run graph-aware thin wall recognition
     * @param threshold Maximum wall thickness in mm
     * @param use_as_validation Use Analysis Situs thickness validation
     */
    std::vector<Feature> Recognize(double threshold = 5.0, bool use_as_validation = true);

private:
    // Phase 1: Graph-based seed identification
    std::vector<int> FindSeedFaces();
    bool IsThinWallSeedCandidate(int face_id);

    // Phase 2: Region growing via BFS
    ThinWallRegion GrowRegionFromSeed(int seed_id, std::set<int>& global_traversed);
    bool ShouldPropagate(int from_face, int to_face);

    // Phase 3: Opposing face identification using dihedral angles
    std::map<int, int> FindOpposingFacePairs(const ThinWallRegion& region);
    bool AreOpposingFaces(int face1_id, int face2_id);

    // Phase 4: Thickness measurement
    ThicknessMeasurement MeasureRegionThickness(const ThinWallRegion& region);
    ThicknessMeasurement MeasureFacePairThickness(int face1_id, int face2_id);

    // Phase 5: Analysis Situs validation
    bool ValidateWithAnalysisSitus(const ThinWallRegion& region, double threshold);

    // Phase 6: Validation
    bool ValidateRegion(const ThinWallRegion& region, double threshold);

    // Phase 7: Feature creation
    Feature CreateFeature(const ThinWallRegion& region);
    std::string ClassifySubtype(const ThinWallRegion& region);

    // Helper methods
    double ComputeDihedralAngleBetween(int face1_id, int face2_id);
    bool AreFacesAdjacent(int face1_id, int face2_id);
    gp_Vec ComputeDominantNormal(const std::set<int>& face_ids);
    double EstimateThicknessAlongNormal(int face_id, const gp_Vec& normal);

    const AAG& aag_;
    const TopoDS_Shape& shape_;
    double threshold_;
    bool use_as_validation_;

    static int feature_id_counter_;

    // Constants
    static constexpr double PARALLEL_NORMAL_THRESHOLD = 0.80;      // cos(~37°) for parallel faces
    static constexpr double ANTIPARALLEL_THRESHOLD = -0.80;        // cos(~143°) for opposing faces
    static constexpr double SMOOTH_EDGE_THRESHOLD = 177.0;         // Near-tangent edges
    static constexpr double THICKNESS_VARIANCE_LIMIT = 0.60;       // 60% CV (more permissive for graph-based regions)
    static constexpr double MIN_REGION_AREA = 50.0;                // 50 mm² minimum
};

} // namespace palmetto
