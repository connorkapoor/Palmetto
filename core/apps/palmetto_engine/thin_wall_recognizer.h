/**
 * Thin Wall Recognizer
 * Detects thin-walled features using face pairing and thickness analysis
 */

#pragma once

#include "aag.h"
#include "engine.h"
#include <set>
#include <vector>

// OpenCASCADE includes
#include <Bnd_Box.hxx>
#include <TopoDS_Face.hxx>
#include <gp_Pnt.hxx>
#include <gp_Vec.hxx>
#include <gp_Dir.hxx>
#include <gp_Ax1.hxx>

namespace palmetto {

/**
 * Face pair candidate for thin wall analysis
 */
struct FacePair {
    int face1_id;
    int face2_id;
    double estimated_distance;
    double normal_alignment;  // -1 = anti-parallel (opposing faces)

    FacePair() : face1_id(-1), face2_id(-1), estimated_distance(0.0), normal_alignment(0.0) {}
    FacePair(int f1, int f2, double dist, double align)
        : face1_id(f1), face2_id(f2), estimated_distance(dist), normal_alignment(align) {}
};

/**
 * Thickness measurement between two faces
 */
struct ThicknessMeasurement {
    double avg_thickness;
    double min_thickness;
    double max_thickness;
    double variance;
    double overlap_ratio;  // 0.0 to 1.0
    std::vector<gp_Pnt> sample_points;
    std::vector<double> sample_thicknesses;

    ThicknessMeasurement()
        : avg_thickness(0.0)
        , min_thickness(0.0)
        , max_thickness(0.0)
        , variance(0.0)
        , overlap_ratio(0.0)
    {}
};

/**
 * Thin wall recognizer using AAG-based methodology
 *
 * Algorithm:
 * 1. Find opposing face pairs using normal anti-parallelism
 * 2. Measure thickness via sampling or radial distance (cylindrical)
 * 3. Validate uniform thickness within threshold
 * 4. Classify subtype: sheet (flat), web (ribs), shell (curved), concentric (nested cylinders)
 * 5. Optional: Ray casting fallback for complex regions
 */
class ThinWallRecognizer {
public:
    explicit ThinWallRecognizer(const AAG& aag);

    /**
     * Run thin wall recognition
     * @param threshold Maximum wall thickness in mm (default: 3.0)
     * @param enable_ray_casting Use Analysis Situs ray casting as fallback (default: false)
     */
    std::vector<Feature> Recognize(double threshold = 3.0, bool enable_ray_casting = false);

private:
    // Phase 1: Candidate identification
    std::vector<FacePair> FindOpposingFacePairs(double max_distance);

    // Phase 2: Thickness measurement
    ThicknessMeasurement MeasureThicknessBetweenFaces(int face1_id, int face2_id);
    double CastRayToFace(const gp_Pnt& origin, const gp_Dir& direction, const TopoDS_Face& target);

    // Phase 3: Validation
    bool ValidateThinWall(const FacePair& pair, const ThicknessMeasurement& measurement);

    // Phase 4: Subtype classification
    std::string ClassifyThinWallSubtype(const std::vector<int>& face_ids);

    // Helper methods - geometric computations
    Bnd_Box ComputeFaceBoundingBox(int face_id);
    gp_Pnt ComputeFaceCentroid(int face_id);
    gp_Vec ComputeAverageFaceNormal(int face_id);
    double BBoxDistance(const Bnd_Box& box1, const Bnd_Box& box2);
    bool AreAxesParallel(const gp_Ax1& axis1, const gp_Ax1& axis2, double tolerance = 0.017);
    bool AreAxesCoincident(const gp_Ax1& axis1, const gp_Ax1& axis2);

    // Feature creation
    Feature CreateThinWallFeature(const std::vector<int>& face_ids,
                                 const ThicknessMeasurement& measurement,
                                 const std::string& subtype);

    // Reference to AAG
    const AAG& aag_;

    // Configuration
    double threshold_;
    bool enable_ray_casting_;

    // Tracking
    std::set<int> excluded_faces_;  // Faces already classified

    // Feature ID counter
    static int feature_id_counter_;

    // Constants
    static constexpr double NORMAL_ANTIPARALLEL_THRESHOLD = -0.80;  // cos(143°)
    static constexpr double THICKNESS_VARIANCE_LIMIT = 0.35;        // 35% coefficient of variation (allows slight taper)
    static constexpr double OVERLAP_RATIO_MIN = 0.20;               // 20% sample overlap required (allows significant face size mismatch)
    static constexpr double MIN_FACE_AREA = 10.0;                   // 10 mm² minimum face area
};

} // namespace palmetto
