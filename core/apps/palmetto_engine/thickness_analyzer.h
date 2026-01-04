/**
 * Thickness Analyzer
 * Computes local thickness for all faces in a CAD model
 */

#pragma once

#include "aag.h"
#include <map>
#include <TopoDS_Shape.hxx>

namespace palmetto {

/**
 * Result of thickness analysis for a single face
 */
struct ThicknessResult {
    int face_id;
    double thickness;           // Local thickness in mm (-1 if no measurement)
    bool has_measurement;       // True if thickness was successfully measured

    ThicknessResult()
        : face_id(-1)
        , thickness(-1.0)
        , has_measurement(false)
    {}

    ThicknessResult(int id, double t)
        : face_id(id)
        , thickness(t)
        , has_measurement(t > 0.0)
    {}
};

/**
 * Thickness analyzer - computes local thickness for all faces
 *
 * Algorithm:
 * 1. For each face, compute centroid and normal
 * 2. Cast ray along normal (both directions)
 * 3. Find closest intersection with model
 * 4. Store distance as local thickness
 *
 * Use cases:
 * - Identify all regions below thickness threshold
 * - Generate thickness distribution histograms
 * - Color-code model by thickness in visualization
 */
class ThicknessAnalyzer {
public:
    /**
     * Constructor
     * @param aag Reference to Attributed Adjacency Graph
     * @param shape The complete CAD model shape
     */
    explicit ThicknessAnalyzer(const AAG& aag, const TopoDS_Shape& shape);

    /**
     * Analyze thickness for all faces
     * @param max_search_distance Maximum ray casting distance in mm (default: 50mm)
     * @return Map of face_id -> ThicknessResult
     */
    std::map<int, ThicknessResult> AnalyzeAllFaces(double max_search_distance = 50.0);

    /**
     * Analyze thickness for a single face
     * @param face_id Face ID in AAG
     * @param max_search_distance Maximum ray casting distance in mm
     * @return ThicknessResult for this face
     */
    ThicknessResult AnalyzeFace(int face_id, double max_search_distance = 50.0);

    /**
     * Generate statistics about thickness distribution
     * @param results Map of thickness results
     * @return String with summary statistics
     */
    static std::string GenerateStatistics(const std::map<int, ThicknessResult>& results);

private:
    /**
     * Cast ray from a point along a direction to find closest intersection
     * @param origin Starting point
     * @param direction Ray direction
     * @param max_distance Maximum search distance
     * @return Distance to closest intersection, or -1 if none found
     */
    double CastRay(const gp_Pnt& origin, const gp_Dir& direction, double max_distance);

    /**
     * Compute face centroid
     */
    gp_Pnt ComputeFaceCentroid(int face_id);

    /**
     * Compute face normal at centroid (accounting for orientation)
     */
    gp_Vec ComputeFaceNormal(int face_id);

    // References
    const AAG& aag_;
    const TopoDS_Shape& shape_;

    // Configuration
    static constexpr double MIN_SELF_DISTANCE = 0.1;  // Ignore hits closer than 0.1mm (self-intersection)
};

} // namespace palmetto
