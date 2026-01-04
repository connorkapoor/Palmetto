/**
 * Pocket Depth Analyzer
 *
 * Enhances cavity recognition with:
 * - Depth calculation
 * - Through-hole vs blind pocket classification
 * - Opening/entrance detection
 * - Accessibility metrics (narrow vs wide, shallow vs deep)
 */

#pragma once

#include "aag.h"

#include <TopoDS_Shape.hxx>
#include <TopoDS_Face.hxx>
#include <Bnd_Box.hxx>

#include <map>
#include <set>
#include <vector>

namespace palmetto {

/**
 * Pocket/cavity classification
 */
enum class PocketType {
    THROUGH_HOLE,      // Penetrates completely through part
    BLIND_POCKET,      // Closed bottom, doesn't penetrate
    SHALLOW_RECESS,    // Depth < 2x opening diameter
    DEEP_CAVITY        // Depth >= 2x opening diameter
};

/**
 * Pocket depth analysis result
 */
struct PocketDepthResult {
    int pocket_id;
    std::set<int> face_ids;

    // Geometric metrics
    double depth;                  // Maximum depth from opening plane (mm)
    double opening_diameter;       // Effective diameter of opening (mm)
    double aspect_ratio;           // depth / opening_diameter
    double volume;                 // Approximate pocket volume (mm³)

    // Classification
    PocketType type;
    bool is_through_hole;
    bool is_deep;                  // aspect_ratio > 2.0
    bool is_narrow;                // opening_diameter < 5mm

    // Opening information
    std::set<int> opening_faces;   // Faces that form the opening/entrance
    gp_Pnt opening_centroid;       // Center point of opening
    gp_Dir opening_normal;         // Direction of opening

    // Accessibility
    double accessibility_score;    // 0-1 (0=hard to machine, 1=easy)

    PocketDepthResult()
        : pocket_id(-1), depth(0), opening_diameter(0), aspect_ratio(0), volume(0),
          type(PocketType::SHALLOW_RECESS), is_through_hole(false),
          is_deep(false), is_narrow(false), accessibility_score(0.5) {}
};

/**
 * Pocket depth analyzer
 */
class PocketDepthAnalyzer {
public:
    /**
     * Constructor
     * @param shape The solid shape
     * @param aag The attributed adjacency graph
     */
    PocketDepthAnalyzer(const TopoDS_Shape& shape, const AAG& aag);

    /**
     * Analyze depth and classification for all recognized cavities/pockets
     * @param cavity_face_sets List of face sets representing cavities
     * @return Map of pocket_id -> depth analysis result
     */
    std::map<int, PocketDepthResult> AnalyzePockets(
        const std::vector<std::set<int>>& cavity_face_sets);

    /**
     * Analyze a single pocket
     */
    PocketDepthResult AnalyzeSinglePocket(const std::set<int>& face_ids);

private:
    const TopoDS_Shape& shape_;
    const AAG& aag_;
    std::vector<TopoDS_Face> index_to_face_;

    /**
     * Find opening faces (faces with most external adjacencies)
     */
    std::set<int> FindOpeningFaces(const std::set<int>& cavity_faces);

    /**
     * Compute opening plane from opening faces
     */
    gp_Pln ComputeOpeningPlane(const std::set<int>& opening_faces);

    /**
     * Compute maximum depth from opening plane
     */
    double ComputeMaxDepth(const std::set<int>& cavity_faces, const gp_Pln& opening_plane);

    /**
     * Estimate opening diameter (effective width of entrance)
     */
    double EstimateOpeningDiameter(const std::set<int>& opening_faces);

    /**
     * Check if pocket is a through-hole (penetrates part)
     */
    bool IsThroughHole(const std::set<int>& cavity_faces);

    /**
     * Classify pocket type based on metrics
     */
    PocketType ClassifyPocket(double depth, double opening_diameter, bool is_through);

    /**
     * Compute accessibility score for machining
     * Based on aspect ratio, opening size, and depth
     */
    double ComputeAccessibilityScore(double depth, double opening_diameter);

    /**
     * Estimate pocket volume
     */
    double EstimateVolume(const std::set<int>& cavity_faces);

    /**
     * Get bounding box of face set
     */
    Bnd_Box GetBoundingBox(const std::set<int>& face_ids);

    /**
     * Get face centroid
     */
    gp_Pnt GetFaceCentroid(const TopoDS_Face& face);

    /**
     * Get face normal
     */
    gp_Dir GetFaceNormal(const TopoDS_Face& face);

    /**
     * Build face index
     */
    void BuildFaceIndex();
};

} // namespace palmetto
