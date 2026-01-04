/**
 * Accessibility Analyzer
 *
 * Determines which faces are accessible for manufacturing:
 * - Molding: Can face be reached by straight mold pull?
 * - CNC: Can cutting tool access face from standard directions?
 * - 3D Printing: Does face require support structures?
 *
 * Uses volumetric ray-based visibility analysis to detect TRUE undercuts.
 */

#pragma once

#include "aag.h"
#include "sdf_generator.h"

#ifdef USE_EMBREE
#include "embree_ray_tracer.h"
#endif

#include <TopoDS_Shape.hxx>
#include <TopoDS_Face.hxx>
#include <gp_Dir.hxx>
#include <gp_Pnt.hxx>

#include <map>
#include <vector>
#include <set>

namespace palmetto {

/**
 * Accessibility result for a single face
 */
struct AccessibilityResult {
    int face_id;
    bool is_accessible_molding;     // Can be demolded in draft direction
    bool is_accessible_cnc;         // Can be reached by tool from at least one axis
    bool requires_side_action;      // Requires complex molding (side action/lifter)
    double accessibility_score;     // 0-1 (0=completely blocked, 1=fully accessible)

    // Detailed accessibility per direction
    std::map<std::string, bool> accessible_from_direction;  // "+X", "-X", "+Y", "-Y", "+Z", "-Z"

    AccessibilityResult()
        : face_id(-1), is_accessible_molding(true), is_accessible_cnc(true),
          requires_side_action(false), accessibility_score(1.0) {}
};

/**
 * Main accessibility analyzer class
 */
class AccessibilityAnalyzer {
public:
    /**
     * Constructor
     * @param shape The solid shape to analyze
     * @param aag The attributed adjacency graph
     */
    AccessibilityAnalyzer(const TopoDS_Shape& shape, const AAG& aag);

    /**
     * Analyze molding accessibility (undercut detection)
     * @param draft_direction Mold separation direction (typically +Z)
     * @return Map of face_id -> accessibility result
     */
    std::map<int, AccessibilityResult> AnalyzeMoldingAccessibility(const gp_Dir& draft_direction);

    /**
     * Analyze CNC machining accessibility
     * Tests accessibility from 6 standard directions (+/-X, +/-Y, +/-Z)
     * @return Map of face_id -> accessibility result
     */
    std::map<int, AccessibilityResult> AnalyzeCNCAccessibility();

    /**
     * Compute detailed accessibility scores
     * Uses ray casting to determine how "exposed" each face is
     * @return Map of face_id -> score (0-1)
     */
    std::map<int, double> ComputeAccessibilityScores();

private:
    const TopoDS_Shape& shape_;
    const AAG& aag_;
    std::vector<TopoDS_Face> index_to_face_;

#ifdef USE_EMBREE
    std::unique_ptr<EmbreeRayTracer> ray_tracer_;
#endif

    /**
     * Check if a face is accessible from a specific direction using ray casting
     * @param face The face to test
     * @param direction Direction to test from
     * @return true if face is visible from direction (no obstruction)
     */
    bool IsFaceAccessibleFromDirection(const TopoDS_Face& face, const gp_Dir& direction);

    /**
     * Cast ray from face centroid in given direction to detect obstructions
     * @param face_id Face index
     * @param direction Ray direction
     * @return Distance to nearest obstruction (negative if none)
     */
    double CastAccessibilityRay(int face_id, const gp_Dir& direction);

    /**
     * Get face normal at centroid
     */
    gp_Dir GetFaceNormal(const TopoDS_Face& face);

    /**
     * Get face centroid
     */
    gp_Pnt GetFaceCentroid(const TopoDS_Face& face);

    /**
     * Build face index (deterministic face ordering)
     */
    void BuildFaceIndex();

    /**
     * Compute shadow volume - which faces are "shadowed" by other faces
     * relative to a direction
     */
    std::set<int> ComputeShadowVolume(const gp_Dir& direction);

    /**
     * Check if face requires side action (complex undercut)
     * Based on combination of draft angle and accessibility
     */
    bool RequiresSideAction(int face_id, const gp_Dir& draft_direction,
                           double draft_angle, bool accessible);
};

} // namespace palmetto
