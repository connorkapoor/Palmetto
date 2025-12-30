/**
 * Fillet Recognizer Implementation
 */

#include "fillet_recognizer.h"

#include <iostream>
#include <cmath>
#include <sstream>
#include <iomanip>

// Define M_PI if not already defined
#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

// OpenCASCADE includes for geometry analysis
#include <BRepAdaptor_Surface.hxx>
#include <BRepAdaptor_Curve.hxx>
#include <BRepLProp_SLProps.hxx>
#include <gp_Dir.hxx>
#include <gp_Pnt.hxx>
#include <gp_Vec.hxx>
#include <gp_Lin.hxx>
#include <gp_Circ.hxx>
#include <TopAbs_Orientation.hxx>
#include <TopExp_Explorer.hxx>
#include <TopoDS.hxx>
#include <GeomAbs_CurveType.hxx>

namespace palmetto {

int FilletRecognizer::feature_id_counter_ = 0;

FilletRecognizer::FilletRecognizer(const AAG& aag)
    : aag_(aag)
{
}

std::vector<Feature> FilletRecognizer::Recognize(double max_radius) {
    std::vector<Feature> fillets;

    std::cout << "Fillet recognizer: Checking faces for fillets\n";

    // Get all cylindrical and toroidal faces
    std::vector<int> cyl_faces = aag_.GetCylindricalFaces();
    std::vector<int> tor_faces = aag_.GetToroidalFaces();

    std::cout << "  Found " << cyl_faces.size() << " cylindrical faces\n";
    std::cout << "  Found " << tor_faces.size() << " toroidal faces\n";

    // Check cylindrical faces (straight fillets)
    for (int face_id : cyl_faces) {
        if (IsFilletCandidate(face_id, max_radius)) {
            double radius = GetFilletRadius(face_id);
            Feature fillet = CreateFillet(face_id, radius);
            fillets.push_back(fillet);
        }
    }

    // Check toroidal faces (curved fillets)
    for (int face_id : tor_faces) {
        if (IsFilletCandidate(face_id, max_radius)) {
            double radius = GetFilletRadius(face_id);
            Feature fillet = CreateFillet(face_id, radius);
            fillets.push_back(fillet);
        }
    }

    std::cout << "Fillet recognizer: Recognized " << fillets.size() << " fillets\n";

    return fillets;
}

bool FilletRecognizer::IsFilletCandidate(int face_id, double max_radius) {
    // Get face attributes
    const FaceAttributes& attrs = aag_.GetFaceAttributes(face_id);

    // Must be cylindrical or toroidal
    if (!attrs.is_cylinder && !attrs.is_torus) {
        return false;
    }

    // Get the fillet radius (cylinder radius or torus minor radius)
    double radius = attrs.is_cylinder ? attrs.cylinder_radius : attrs.torus_minor_radius;

    // Must have small radius (fillets are typically < 10mm)
    if (radius > max_radius) {
        return false;
    }

    // Key distinction: Check edge pattern
    // Fillets have QUARTER-CIRCLE edges (90°)
    // Holes have SEMICIRCULAR edges (180°)
    if (!HasQuarterCircleEdges(face_id)) {
        return false;
    }

    return true;
}

bool FilletRecognizer::IsInternalCylinder(int face_id) {
    const FaceAttributes& attrs = aag_.GetFaceAttributes(face_id);

    if (!attrs.is_cylinder) {
        return false; // Not a cylinder
    }

    // Get cylinder parameters
    double radius = attrs.cylinder_radius;
    double diameter = 2.0 * radius;
    gp_Ax1 axis = attrs.cylinder_axis;

    // Get the TopoDS_Face to compute surface normal
    TopoDS_Face face = aag_.GetFace(face_id);

    // Get surface properties at center of face
    BRepAdaptor_Surface surface(face);
    double u_mid = (surface.FirstUParameter() + surface.LastUParameter()) / 2.0;
    double v_mid = (surface.FirstVParameter() + surface.LastVParameter()) / 2.0;

    BRepLProp_SLProps props(surface, u_mid, v_mid, 1, 1e-6);

    if (!props.IsNormalDefined()) {
        return false; // Cannot determine
    }

    // Get point on cylinder surface and its normal
    gp_Pnt cylPt = props.Value();
    gp_Dir cylNorm = props.Normal();

    // Account for face orientation
    if (face.Orientation() == TopAbs_REVERSED) {
        cylNorm.Reverse();
    }

    // Take a probe point along the normal (outward from surface)
    // Probe distance = 5% of diameter (AS methodology)
    gp_Pnt normProbe = cylPt.XYZ() + cylNorm.XYZ() * diameter * 0.05;

    // Compute distances to cylinder axis
    gp_Lin axisLin(axis);
    double probeDist = axisLin.Distance(normProbe);
    double cylDist = axisLin.Distance(cylPt);

    // If probe is closer to axis, normal points INWARD → internal cylinder (hole)
    // If probe is farther from axis, normal points OUTWARD → external cylinder (fillet)
    if (probeDist < cylDist) {
        return true; // Internal (hole/concave)
    }

    return false; // External (fillet/convex)
}

bool FilletRecognizer::HasQuarterCircleEdges(int face_id) {
    const FaceAttributes& attrs = aag_.GetFaceAttributes(face_id);
    if (!attrs.is_cylinder && !attrs.is_torus) return false;

    // Get edges bounding this face
    const TopoDS_Face& face = aag_.GetFace(face_id);

    int quarter_circle_count = 0;

    // Check edge arc angles
    for (TopExp_Explorer exp(face, TopAbs_EDGE); exp.More(); exp.Next()) {
        TopoDS_Edge edge = TopoDS::Edge(exp.Current());

        try {
            BRepAdaptor_Curve curve(edge);

            // Check if circular
            if (curve.GetType() == GeomAbs_Circle) {
                // Get parameter range to determine arc angle
                double first_param = curve.FirstParameter();
                double last_param = curve.LastParameter();
                double param_range = last_param - first_param;
                double arc_angle = param_range * 180.0 / M_PI;

                // Check if it's a full circle (360°)
                bool is_full = (std::abs(param_range - 2.0 * M_PI) < 1e-6);

                if (!is_full) {
                    // It's an arc - check if quarter-circle (90°)
                    if (std::abs(arc_angle - 90.0) < 5.0) {
                        quarter_circle_count++;
                    }
                }
            }
        } catch (...) {
            continue;
        }
    }

    // Fillets typically have 1-2 quarter-circle edges
    return (quarter_circle_count > 0);
}

bool FilletRecognizer::HasSmoothEdges(int face_id) {
    // Get neighbors
    std::vector<int> neighbors = aag_.GetNeighbors(face_id);

    int smooth_edge_count = 0;

    for (int neighbor_id : neighbors) {
        double dihedral = aag_.GetDihedralAngle(face_id, neighbor_id);

        // Smooth edge: dihedral angle close to 0° OR 180° (±threshold)
        // 0° = tangent connection (normals parallel)
        // 180° = smooth blend (normals opposite)
        double deviation_from_0 = std::abs(dihedral);
        double deviation_from_180 = std::abs(dihedral - 180.0);

        bool is_smooth = (deviation_from_0 < SMOOTH_ANGLE_THRESHOLD) ||
                        (deviation_from_180 < SMOOTH_ANGLE_THRESHOLD);

        if (is_smooth) {
            smooth_edge_count++;
        }
    }

    // Fillets typically have at least 2 smooth edges
    // (connecting tangentially to support faces)
    return smooth_edge_count >= 2;
}

double FilletRecognizer::GetFilletRadius(int face_id) {
    const FaceAttributes& attrs = aag_.GetFaceAttributes(face_id);

    // Return cylinder radius for straight fillets, torus minor radius for curved fillets
    if (attrs.is_cylinder) {
        return attrs.cylinder_radius;
    } else if (attrs.is_torus) {
        return attrs.torus_minor_radius;
    }

    return 0.0;
}

Feature FilletRecognizer::CreateFillet(int face_id, double radius) {
    const FaceAttributes& attrs = aag_.GetFaceAttributes(face_id);

    Feature feature;

    // Generate ID
    std::ostringstream oss;
    oss << "fillet_" << std::setfill('0') << std::setw(4) << feature_id_counter_++;
    feature.id = oss.str();

    feature.type = "fillet";
    feature.subtype = "blend";
    feature.source = "fillet_recognizer";
    feature.confidence = 0.85;

    // Face IDs
    feature.face_ids.push_back(face_id);

    // Parameters
    feature.params["radius_mm"] = radius;

    if (attrs.is_cylinder) {
        feature.subtype = "blend";  // Straight fillet
        feature.params["axis_x"] = attrs.cylinder_axis.Direction().X();
        feature.params["axis_y"] = attrs.cylinder_axis.Direction().Y();
        feature.params["axis_z"] = attrs.cylinder_axis.Direction().Z();
    } else if (attrs.is_torus) {
        feature.subtype = "curved_blend";  // Curved fillet (around corner)
        feature.params["axis_x"] = attrs.torus_axis.Direction().X();
        feature.params["axis_y"] = attrs.torus_axis.Direction().Y();
        feature.params["axis_z"] = attrs.torus_axis.Direction().Z();
        feature.params["major_radius_mm"] = attrs.torus_major_radius;
    }

    return feature;
}

} // namespace palmetto
