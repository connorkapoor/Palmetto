/**
 * Fillet Recognizer
 * Based on Analysis Situs blend recognition (asiAlgo_RecognizeEBF)
 *
 * Algorithm:
 * 1. Find small cylindrical/toroidal faces
 * 2. Check for smooth edges (dihedral angle ≈ 180°)
 * 3. Check for spring edges (sharp transitions to support faces)
 * 4. Exclude faces that are holes (concave circular edges)
 */

#pragma once

#include "aag.h"
#include "engine.h"
#include <set>

namespace palmetto {

/**
 * Fillet recognizer using AAG-based methodology
 *
 * Fillets are small cylindrical/toroidal blend faces that:
 * - Have smooth edges connecting to adjacent faces (~180° dihedral)
 * - Have spring edges where they transition sharply
 * - Are NOT through-holes
 */
class FilletRecognizer {
public:
    explicit FilletRecognizer(const AAG& aag);

    /**
     * Run fillet recognition
     *
     * @param max_radius Maximum fillet radius to consider (default 10mm)
     */
    std::vector<Feature> Recognize(double max_radius = 10.0);

private:
    /**
     * Check if face is a fillet candidate
     * - Small cylindrical/toroidal surface
     * - Has smooth edges
     * - NOT a through-hole
     */
    bool IsFilletCandidate(int face_id, double max_radius);

    /**
     * Check if face has smooth edges (tangent connections)
     * Smooth edge: |dihedral_angle - 180°| < threshold
     */
    bool HasSmoothEdges(int face_id);

    /**
     * Check if face has quarter-circle edges (90° arc edges)
     * Fillets have quarter-circle edges, holes have semicircular edges
     * @return true if face has quarter-circle edges
     */
    bool HasQuarterCircleEdges(int face_id);

    /**
     * Check if cylindrical face is internal (concave) or external (convex)
     * Internal cylinders are holes, external cylinders are fillets/rounds
     *
     * Uses AS methodology: probe along normal to test geometry
     * @return true if internal (hole), false if external (fillet)
     */
    bool IsInternalCylinder(int face_id);

    /**
     * Get fillet radius from cylindrical face
     */
    double GetFilletRadius(int face_id);

    /**
     * Create fillet feature
     */
    Feature CreateFillet(int face_id, double radius);

    // Reference to AAG
    const AAG& aag_;

    // Feature ID counter
    static int feature_id_counter_;

    // Smooth edge threshold (degrees from 180°)
    static constexpr double SMOOTH_ANGLE_THRESHOLD = 10.0;
};

} // namespace palmetto
