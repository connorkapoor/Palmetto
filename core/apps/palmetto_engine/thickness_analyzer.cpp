/**
 * Thickness Analyzer Implementation
 */

#include "thickness_analyzer.h"

#include <iostream>
#include <sstream>
#include <iomanip>
#include <cmath>
#include <algorithm>
#include <cfloat>

// OpenCASCADE includes
#include <BRepAdaptor_Surface.hxx>
#include <BRepGProp.hxx>
#include <GProp_GProps.hxx>
#include <IntCurvesFace_ShapeIntersector.hxx>
#include <Precision.hxx>
#include <gp_Lin.hxx>
#include <TopExp_Explorer.hxx>
#include <TopoDS.hxx>
#include <BRep_Tool.hxx>

namespace palmetto {

ThicknessAnalyzer::ThicknessAnalyzer(const AAG& aag, const TopoDS_Shape& shape)
    : aag_(aag)
    , shape_(shape)
{
}

std::map<int, ThicknessResult> ThicknessAnalyzer::AnalyzeAllFaces(double max_search_distance) {
    std::map<int, ThicknessResult> results;

    int face_count = aag_.GetFaceCount();
    std::cout << "Thickness analyzer: analyzing " << face_count << " faces\n";
    std::cout << "  Max search distance: " << max_search_distance << "mm\n";

    int measured_count = 0;
    int failed_count = 0;

    for (int i = 0; i < face_count; i++) {
        ThicknessResult result = AnalyzeFace(i, max_search_distance);
        results[i] = result;

        if (result.has_measurement) {
            measured_count++;
        } else {
            failed_count++;
        }

        // Progress indicator every 50 faces
        if ((i + 1) % 50 == 0) {
            std::cout << "  Progress: " << (i + 1) << "/" << face_count << " faces analyzed\n";
        }
    }

    std::cout << "  Complete: " << measured_count << " measured, "
              << failed_count << " failed\n";

    return results;
}

ThicknessResult ThicknessAnalyzer::AnalyzeFace(int face_id, double max_search_distance) {
    try {
        // Get face centroid and normal
        gp_Pnt centroid = ComputeFaceCentroid(face_id);
        gp_Vec normal_vec = ComputeFaceNormal(face_id);

        if (normal_vec.Magnitude() < Precision::Confusion()) {
            return ThicknessResult(face_id, -1.0);
        }

        gp_Dir normal_dir(normal_vec);

        // Cast rays in both directions (forward and backward along normal)
        double dist_forward = CastRay(centroid, normal_dir, max_search_distance);
        double dist_backward = CastRay(centroid, normal_dir.Reversed(), max_search_distance);

        // Take the minimum valid distance as thickness
        double thickness = -1.0;

        if (dist_forward > 0.0 && dist_backward > 0.0) {
            thickness = std::min(dist_forward, dist_backward);
        } else if (dist_forward > 0.0) {
            thickness = dist_forward;
        } else if (dist_backward > 0.0) {
            thickness = dist_backward;
        }

        return ThicknessResult(face_id, thickness);
    }
    catch (const std::exception& e) {
        std::cerr << "  Error analyzing face " << face_id << ": " << e.what() << "\n";
        return ThicknessResult(face_id, -1.0);
    }
    catch (...) {
        std::cerr << "  Unknown error analyzing face " << face_id << "\n";
        return ThicknessResult(face_id, -1.0);
    }
}

double ThicknessAnalyzer::CastRay(const gp_Pnt& origin, const gp_Dir& direction, double max_distance) {
    try {
        gp_Lin ray(origin, direction);

        IntCurvesFace_ShapeIntersector intersector;
        intersector.Load(shape_, Precision::Confusion());
        intersector.Perform(ray, 0.0, max_distance);

        if (!intersector.IsDone() || intersector.NbPnt() == 0) {
            return -1.0;
        }

        // Find closest valid intersection (ignore self-intersections)
        double min_dist = DBL_MAX;

        for (int i = 1; i <= intersector.NbPnt(); i++) {
            gp_Pnt hit = intersector.Pnt(i);
            double dist = origin.Distance(hit);

            // Filter out self-intersections (hits very close to origin)
            if (dist > MIN_SELF_DISTANCE && dist < min_dist) {
                min_dist = dist;
            }
        }

        return (min_dist < DBL_MAX) ? min_dist : -1.0;
    }
    catch (...) {
        return -1.0;
    }
}

gp_Pnt ThicknessAnalyzer::ComputeFaceCentroid(int face_id) {
    const TopoDS_Face& face = aag_.GetFace(face_id);

    GProp_GProps props;
    BRepGProp::SurfaceProperties(face, props);

    return props.CentreOfMass();
}

gp_Vec ThicknessAnalyzer::ComputeFaceNormal(int face_id) {
    const TopoDS_Face& face = aag_.GetFace(face_id);
    const FaceAttributes& attr = aag_.GetFaceAttributes(face_id);

    // For planar faces, use the stored normal
    if (attr.is_planar) {
        gp_Vec normal = attr.plane_normal;

        // Account for face orientation
        if (face.Orientation() == TopAbs_REVERSED) {
            normal.Reverse();
        }

        return normal;
    }

    // For curved faces, sample at the center
    try {
        BRepAdaptor_Surface surf(face);

        double u_mid = (surf.FirstUParameter() + surf.LastUParameter()) / 2.0;
        double v_mid = (surf.FirstVParameter() + surf.LastVParameter()) / 2.0;

        gp_Pnt point;
        gp_Vec du, dv;
        surf.D1(u_mid, v_mid, point, du, dv);

        gp_Vec normal = du.Crossed(dv);
        if (normal.Magnitude() > Precision::Confusion()) {
            normal.Normalize();

            if (face.Orientation() == TopAbs_REVERSED) {
                normal.Reverse();
            }

            return normal;
        }
    }
    catch (...) {
        // Fall back to zero vector
    }

    return gp_Vec(0, 0, 1);  // Default upward
}

std::string ThicknessAnalyzer::GenerateStatistics(const std::map<int, ThicknessResult>& results) {
    std::ostringstream oss;

    // Count measurements
    int total = results.size();
    int measured = 0;
    int failed = 0;

    std::vector<double> thicknesses;

    for (const auto& pair : results) {
        const ThicknessResult& result = pair.second;
        if (result.has_measurement) {
            measured++;
            thicknesses.push_back(result.thickness);
        } else {
            failed++;
        }
    }

    oss << "Thickness Analysis Statistics:\n";
    oss << "  Total faces: " << total << "\n";
    oss << "  Measured: " << measured << " (" << std::fixed << std::setprecision(1)
        << (100.0 * measured / total) << "%)\n";
    oss << "  Failed: " << failed << "\n";

    if (!thicknesses.empty()) {
        std::sort(thicknesses.begin(), thicknesses.end());

        double min_thickness = thicknesses.front();
        double max_thickness = thicknesses.back();
        double sum = 0.0;
        for (double t : thicknesses) {
            sum += t;
        }
        double avg_thickness = sum / thicknesses.size();
        double median_thickness = thicknesses[thicknesses.size() / 2];

        oss << "\n";
        oss << "  Min thickness: " << std::fixed << std::setprecision(2) << min_thickness << "mm\n";
        oss << "  Max thickness: " << max_thickness << "mm\n";
        oss << "  Avg thickness: " << avg_thickness << "mm\n";
        oss << "  Median thickness: " << median_thickness << "mm\n";

        // Distribution histogram
        oss << "\n";
        oss << "  Distribution:\n";

        std::vector<std::pair<double, std::string>> bins = {
            {1.0, "0-1mm"},
            {2.0, "1-2mm"},
            {3.0, "2-3mm"},
            {5.0, "3-5mm"},
            {10.0, "5-10mm"},
            {DBL_MAX, ">10mm"}
        };

        std::vector<int> counts(bins.size(), 0);

        for (double t : thicknesses) {
            for (size_t i = 0; i < bins.size(); i++) {
                if (t < bins[i].first) {
                    counts[i]++;
                    break;
                }
            }
        }

        for (size_t i = 0; i < bins.size(); i++) {
            if (counts[i] > 0) {
                double percent = 100.0 * counts[i] / thicknesses.size();
                oss << "    " << std::setw(8) << bins[i].second << ": "
                    << std::setw(4) << counts[i] << " faces ("
                    << std::fixed << std::setprecision(1) << percent << "%)\n";
            }
        }
    }

    return oss.str();
}

} // namespace palmetto
