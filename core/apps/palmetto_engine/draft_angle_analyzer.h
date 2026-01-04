#ifndef DRAFT_ANGLE_ANALYZER_H
#define DRAFT_ANGLE_ANALYZER_H

#include <TopoDS_Shape.hxx>
#include <TopoDS_Face.hxx>
#include <gp_Dir.hxx>
#include <map>

/**
 * Draft Angle and Overhang Analyzer
 *
 * Analyzes face orientations for manufacturing processes:
 * - Draft angles: for injection molding (angle from vertical draft direction)
 * - Overhang angles: for 3D printing (angle from horizontal)
 * - Undercut detection: faces that prevent demolding
 */
class DraftAngleAnalyzer {
public:
    DraftAngleAnalyzer(const TopoDS_Shape& shape, const gp_Dir& draft_direction);

    /**
     * Analyze draft angles for all faces.
     * Draft angle > 0 = good, can be demolded
     * Draft angle < 0 = undercut, requires side action
     *
     * @return Map of face_id -> draft_angle (degrees)
     */
    std::map<int, double> AnalyzeDraftAngles();

    /**
     * Analyze overhang angles for 3D printing.
     * Overhang > 45° requires support structures.
     *
     * @return Map of face_id -> overhang_angle (degrees from horizontal)
     */
    std::map<int, double> AnalyzeOverhangs();

    /**
     * Detect undercuts (faces with negative draft).
     *
     * @return Map of face_id -> is_undercut (boolean)
     */
    std::map<int, bool> DetectUndercuts();

    /**
     * Compute draft angle for a single face.
     *
     * @param face Face to analyze
     * @return Draft angle in degrees (positive = good, negative = undercut)
     */
    double ComputeDraftAngle(const TopoDS_Face& face);

    /**
     * Compute overhang angle for a single face.
     *
     * @param face Face to analyze
     * @return Overhang angle in degrees from horizontal (0° = horizontal, 90° = vertical)
     */
    double ComputeOverhangAngle(const TopoDS_Face& face);

private:
    const TopoDS_Shape& shape_;
    gp_Dir draft_direction_;  // Typical: (0, 0, 1) for Z-axis

    /**
     * Get face normal at centroid.
     *
     * @param face Face to analyze
     * @return Face normal direction
     */
    gp_Dir GetFaceNormal(const TopoDS_Face& face);
};

#endif // DRAFT_ANGLE_ANALYZER_H
