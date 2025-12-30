/**
 * Hole Recognizer
 * Based on Analysis Situs asiAlgo_RecognizeDrillHoles
 */

#pragma once

#include "aag.h"
#include "engine.h"
#include <set>

namespace palmetto {

/**
 * Hole recognizer using AAG-based methodology
 *
 * Algorithm (from Analysis Situs):
 * 1. Find cylindrical faces
 * 2. Check if internal (hole) vs external (shaft)
 * 3. Validate concave circular concentric edges
 * 4. Collect coaxial cylinders (counterbored)
 * 5. Detect coaxial cones (countersunk)
 */
class HoleRecognizer {
public:
    explicit HoleRecognizer(const AAG& aag);

    /**
     * Run hole recognition
     * @param excluded_faces Set of face IDs to exclude (e.g., already identified as fillets)
     */
    std::vector<Feature> Recognize(const std::set<int>& excluded_faces = {});

private:
    /**
     * Check if cylinder is internal (hole) vs external (shaft)
     *
     * Internal: normal points toward axis (dot < 0)
     * External: normal points away from axis (dot > 0)
     */
    bool IsInternal(int face_id);

    /**
     * Check if face has concave circular concentric edges
     *
     * Following Analysis Situs IsConcaveConcentric():
     * 1. Find concave neighbors
     * 2. Check if shared edges are circular
     * 3. Verify circles are concentric with cylinder axis
     */
    bool HasConcaveCircularEdges(int face_id);

    /**
     * Find coaxial cylinders (counterbored pattern)
     */
    std::vector<int> FindCoaxialCylinders(int seed_face_id, std::set<int>& traversed);

    /**
     * Check if two axes are coincident
     */
    bool AreAxesCoincident(const gp_Ax1& axis1, const gp_Ax1& axis2);

    /**
     * Create simple hole feature
     */
    Feature CreateSimpleHole(int face_id);

    /**
     * Create counterbored hole feature
     */
    Feature CreateCounterboredHole(const std::vector<int>& face_ids);

    // Reference to AAG
    const AAG& aag_;

    // Feature ID counter
    static int feature_id_counter_;
};

} // namespace palmetto
