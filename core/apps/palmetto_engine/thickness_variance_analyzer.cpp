#include "thickness_variance_analyzer.h"
#include <BRepAdaptor_Surface.hxx>
#include <BRepClass3d_SolidClassifier.hxx>
#include <IntCurvesFace_ShapeIntersector.hxx>
#include <TopExp_Explorer.hxx>
#include <TopoDS.hxx>
#include <gp_Pnt.hxx>
#include <gp_Vec.hxx>
#include <Precision.hxx>
#include <cmath>
#include <numeric>
#include <iostream>

ThicknessVarianceAnalyzer::ThicknessVarianceAnalyzer(const TopoDS_Shape& shape, double max_search_distance)
    : shape_(shape), max_search_distance_(max_search_distance) {
}

std::map<int, double> ThicknessVarianceAnalyzer::AnalyzeAll() {
    std::map<int, double> variance_map;

    int face_id = 0;
    for (TopExp_Explorer exp(shape_, TopAbs_FACE); exp.More(); exp.Next(), face_id++) {
        TopoDS_Face face = TopoDS::Face(exp.Current());
        double variance = AnalyzeFace(face, face_id);

        if (variance >= 0) {
            variance_map[face_id] = variance;
        }
    }

    std::cout << "Thickness variance analysis: " << variance_map.size() << " faces analyzed\n";
    return variance_map;
}

double ThicknessVarianceAnalyzer::AnalyzeFace(const TopoDS_Face& face, int face_id) {
    std::vector<double> thickness_samples;

    // Sample thickness at multiple points on face
    if (!SampleFaceThickness(face, thickness_samples)) {
        return -1.0;
    }

    // Need at least 3 samples for meaningful variance
    if (thickness_samples.size() < 3) {
        return -1.0;
    }

    // Compute standard deviation
    return ComputeStandardDeviation(thickness_samples);
}

bool ThicknessVarianceAnalyzer::SampleFaceThickness(const TopoDS_Face& face, std::vector<double>& samples) {
    try {
        BRepAdaptor_Surface surface(face);

        // Get parametric bounds
        double u_min = surface.FirstUParameter();
        double u_max = surface.LastUParameter();
        double v_min = surface.FirstVParameter();
        double v_max = surface.LastVParameter();

        // Sample 5x5 grid (25 points)
        const int grid_size = 5;
        samples.clear();
        samples.reserve(grid_size * grid_size);

        for (int i = 0; i < grid_size; i++) {
            double u = u_min + (u_max - u_min) * i / (grid_size - 1);

            for (int j = 0; j < grid_size; j++) {
                double v = v_min + (v_max - v_min) * j / (grid_size - 1);

                // Get point on surface
                gp_Pnt point = surface.Value(u, v);

                // Compute normal at this point
                gp_Vec du, dv;
                surface.D1(u, v, point, du, dv);
                gp_Vec normal = du.Crossed(dv);

                if (normal.Magnitude() < Precision::Confusion()) {
                    continue;  // Skip degenerate points
                }

                normal.Normalize();
                gp_Dir normal_dir(normal);

                // Cast rays in both directions along normal
                double dist_forward = CastRay(point, normal_dir);
                double dist_backward = CastRay(point, normal_dir.Reversed());

                // Thickness = minimum of forward/backward distances * 2
                double thickness = -1.0;
                if (dist_forward > 0 && dist_backward > 0) {
                    thickness = 2.0 * std::min(dist_forward, dist_backward);
                } else if (dist_forward > 0) {
                    thickness = 2.0 * dist_forward;
                } else if (dist_backward > 0) {
                    thickness = 2.0 * dist_backward;
                }

                if (thickness > 0 && thickness < max_search_distance_ * 2) {
                    samples.push_back(thickness);
                }
            }
        }

        return samples.size() >= 3;

    } catch (const Standard_Failure& e) {
        std::cerr << "Error sampling face thickness: " << e.GetMessageString() << "\n";
        return false;
    }
}

double ThicknessVarianceAnalyzer::ComputeStandardDeviation(const std::vector<double>& samples) {
    if (samples.empty()) {
        return 0.0;
    }

    // Compute mean
    double mean = std::accumulate(samples.begin(), samples.end(), 0.0) / samples.size();

    // Compute variance
    double variance = 0.0;
    for (double sample : samples) {
        double diff = sample - mean;
        variance += diff * diff;
    }
    variance /= samples.size();

    // Return standard deviation
    return std::sqrt(variance);
}

double ThicknessVarianceAnalyzer::CastRay(const gp_Pnt& point, const gp_Dir& direction) {
    try {
        IntCurvesFace_ShapeIntersector intersector;
        intersector.Load(shape_, Precision::Confusion());

        gp_Lin ray(point, direction);
        intersector.Perform(ray, 0.0, max_search_distance_);

        if (intersector.NbPnt() == 0) {
            return -1.0;
        }

        // Find closest intersection (skip self-intersections within 0.01mm)
        double min_distance = max_search_distance_;
        bool found = false;

        for (int i = 1; i <= intersector.NbPnt(); i++) {
            double param = intersector.WParameter(i);
            if (param > 0.01 && param < min_distance) {
                min_distance = param;
                found = true;
            }
        }

        return found ? min_distance : -1.0;

    } catch (const Standard_Failure& e) {
        return -1.0;
    }
}
