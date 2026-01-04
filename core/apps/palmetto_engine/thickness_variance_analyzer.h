#ifndef THICKNESS_VARIANCE_ANALYZER_H
#define THICKNESS_VARIANCE_ANALYZER_H

#include <TopoDS_Shape.hxx>
#include <TopoDS_Face.hxx>
#include <map>
#include <vector>

/**
 * Thickness Variance Analyzer
 *
 * Analyzes wall thickness uniformity across each face by sampling multiple points
 * and computing standard deviation. High variance indicates non-uniform thickness
 * which can cause manufacturing issues (warping, sink marks, etc.).
 */
class ThicknessVarianceAnalyzer {
public:
    ThicknessVarianceAnalyzer(const TopoDS_Shape& shape, double max_search_distance);

    /**
     * Analyze thickness variance for all faces in the shape.
     *
     * @return Map of face_id -> thickness_variance (standard deviation in mm)
     */
    std::map<int, double> AnalyzeAll();

    /**
     * Analyze thickness variance for a single face.
     *
     * @param face Face to analyze
     * @param face_id Face identifier
     * @return Thickness variance (standard deviation) in mm, or -1 if analysis failed
     */
    double AnalyzeFace(const TopoDS_Face& face, int face_id);

private:
    const TopoDS_Shape& shape_;
    double max_search_distance_;

    /**
     * Sample thickness at multiple points on face using parametric grid.
     *
     * @param face Face to sample
     * @param samples Output vector of thickness measurements
     * @return True if sampling succeeded
     */
    bool SampleFaceThickness(const TopoDS_Face& face, std::vector<double>& samples);

    /**
     * Compute standard deviation from thickness samples.
     *
     * @param samples Vector of thickness measurements
     * @return Standard deviation in mm
     */
    double ComputeStandardDeviation(const std::vector<double>& samples);

    /**
     * Cast ray from point along direction to find nearest intersection.
     *
     * @param point Origin point
     * @param direction Ray direction
     * @return Distance to nearest intersection, or -1 if no hit
     */
    double CastRay(const gp_Pnt& point, const gp_Dir& direction);
};

#endif // THICKNESS_VARIANCE_ANALYZER_H
