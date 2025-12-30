/**
 * Chamfer Recognizer
 *
 * Algorithm:
 * 1. Find small planar faces
 * 2. Check for sharp edges (dihedral angle != 180°)
 * 3. Verify chamfer geometry (linear edges, beveled connection)
 * 4. Exclude faces that are primary features
 */

#pragma once

#include "aag.h"
#include "engine.h"
#include <set>

namespace palmetto {

/**
 * Chamfer recognizer using AAG-based methodology
 *
 * Chamfers are small planar beveled faces that:
 * - Have sharp edges connecting to adjacent faces
 * - Connect two surfaces at an angle (typically 45° but can vary)
 * - Have linear edges (not circular arcs)
 * - Small width (typically < 5mm)
 */
class ChamferRecognizer {
public:
    explicit ChamferRecognizer(const AAG& aag);

    /**
     * Run chamfer recognition
     *
     * @param max_width Maximum chamfer width to consider (default 5mm)
     */
    std::vector<Feature> Recognize(double max_width = 5.0);

private:
    /**
     * Check if face is a chamfer candidate
     * - Small planar surface
     * - Has sharp edges (not smooth)
     * - Linear edges
     */
    bool IsChamferCandidate(int face_id, double max_width);

    /**
     * Check if face has linear edges (straight lines)
     * Chamfers have line edges, fillets have circular arcs
     */
    bool HasLinearEdges(int face_id);

    /**
     * Check if face has sharp edges (non-tangent connections)
     * Sharp edge: dihedral angle significantly different from 180°
     */
    bool HasSharpEdges(int face_id);

    /**
     * Get chamfer width (maximum distance across the planar face)
     */
    double GetChamferWidth(int face_id);

    /**
     * Create chamfer feature
     */
    Feature CreateChamfer(int face_id, double width);

    // Reference to AAG
    const AAG& aag_;

    // Feature ID counter
    static int feature_id_counter_;

    // Sharp edge threshold (degrees from 180°)
    static constexpr double SHARP_ANGLE_THRESHOLD = 20.0;
};

} // namespace palmetto
