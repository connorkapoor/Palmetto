/**
 * Cavity Recognizer
 * Based on Analysis Situs asiAlgo_RecognizeCavities
 *
 * Algorithm:
 * 1. Find seed faces with inner loops having convex dihedral angles
 * 2. Propagate recursively through convex edges
 * 3. Validate cavity terminates at another inner loop
 * 4. Check cavity is not the entire shape
 * 5. Check cavity size is below threshold
 */

#pragma once

#include "aag.h"
#include "engine.h"
#include <set>
#include <vector>
#include <map>

namespace palmetto {

/**
 * Cavity recognizer using AAG-based methodology
 *
 * Cavities are negative features (pockets, slots, recesses) that:
 * - Start from faces with inner loops having convex edges
 * - Propagate through connected faces via convex edges
 * - Terminate at another inner loop with convex adjacency
 * - Do not comprise the entire shape
 * - Have size below threshold (infinite by default)
 */
class CavityRecognizer {
public:
    explicit CavityRecognizer(const AAG& aag);

    /**
     * Run cavity recognition
     *
     * @param max_volume Maximum cavity volume (default: infinite)
     */
    std::vector<Feature> Recognize(double max_volume = 1e9);

private:
    /**
     * Find seed faces for cavity recognition
     * Seeds are faces with inner loops having ONLY convex dihedral angles
     */
    std::vector<int> FindSeedFaces();

    /**
     * Check if face has inner loops (non-outer wire edges)
     * Inner loops indicate potential cavity boundaries
     */
    bool HasInnerLoop(int face_id);

    /**
     * Check if all edges in inner loop have convex dihedral angles
     * Convex: dihedral angle < 180° (material bends inward)
     */
    bool HasConvexInnerLoop(int face_id);

    /**
     * Propagate from seed face through convex edges
     * Recursively visit connected faces while maintaining convexity
     *
     * @param seed_id Starting face
     * @param traversed Set of already visited faces
     * @return Set of faces comprising the cavity
     */
    std::set<int> PropagateFromSeed(int seed_id, std::set<int>& traversed);

    /**
     * Check if propagation should continue through this edge
     * Continue if edge has convex dihedral angle
     */
    bool ShouldPropagate(int face1_id, int face2_id);

    /**
     * Validate cavity feature
     * - Must terminate at inner loop
     * - Must not be entire shape
     * - Must be below size threshold
     */
    bool ValidateCavity(const std::set<int>& cavity_faces, double max_volume);

    /**
     * Estimate cavity volume based on face areas
     */
    double EstimateCavityVolume(const std::set<int>& cavity_faces);

    /**
     * Create cavity feature from face set
     */
    Feature CreateCavity(const std::set<int>& cavity_faces);

    // Reference to AAG
    const AAG& aag_;

    // Feature ID counter
    static int feature_id_counter_;

    // Convex angle threshold (dihedral < 180° - threshold)
    static constexpr double CONVEX_ANGLE_THRESHOLD = 5.0;
};

} // namespace palmetto
