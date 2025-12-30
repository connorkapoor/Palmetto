/**
 * Hole Recognizer Implementation
 */

#include "hole_recognizer.h"

#include <iostream>
#include <cmath>
#include <sstream>
#include <iomanip>
#include <functional>

// Define M_PI if not already defined
#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

// OpenCASCADE includes
#include <BRepAdaptor_Surface.hxx>
#include <BRepAdaptor_Curve.hxx>
#include <BRepLProp_SLProps.hxx>
#include <GeomAbs_CurveType.hxx>
#include <gp_Lin.hxx>
#include <gp_Circ.hxx>
#include <TopExp_Explorer.hxx>
#include <TopoDS.hxx>
#include <BRep_Tool.hxx>
#include <TopTools_ListIteratorOfListOfShape.hxx>
#include <TopTools_IndexedDataMapOfShapeListOfShape.hxx>
#include <TopExp.hxx>

namespace palmetto {

int HoleRecognizer::feature_id_counter_ = 0;

HoleRecognizer::HoleRecognizer(const AAG& aag)
    : aag_(aag)
{
}

std::vector<Feature> HoleRecognizer::Recognize(const std::set<int>& excluded_faces) {
    std::vector<Feature> holes;
    std::set<int> traversed;

    // Get all cylindrical faces
    std::vector<int> cyl_faces = aag_.GetCylindricalFaces();

    std::cout << "Hole recognizer: Found " << cyl_faces.size() << " cylindrical faces" << std::endl;

    for (int face_id : cyl_faces) {
        if (traversed.count(face_id)) continue;

        // Skip faces that are already classified as something else (e.g., fillets)
        if (excluded_faces.count(face_id)) {
            std::cout << "  Face " << face_id << ": Excluded (already classified)" << std::endl;
            continue;
        }

        // Check if internal (hole) vs external (shaft)
        if (!IsInternal(face_id)) {
            std::cout << "  Face " << face_id << ": Not internal (external cylinder)" << std::endl;
            continue;
        }

        // Check for concave circular concentric edges
        if (!HasConcaveCircularEdges(face_id)) {
            std::cout << "  Face " << face_id << ": No concave circular edges (likely fillet)" << std::endl;
            continue;
        }

        const FaceAttributes& attrs = aag_.GetFaceAttributes(face_id);
        std::cout << "  Face " << face_id << ": ✓ HOLE VALIDATED (radius="
                  << attrs.cylinder_radius << "mm)" << std::endl;

        // Find coaxial cylinders (counterbored pattern)
        std::vector<int> coaxial = FindCoaxialCylinders(face_id, traversed);

        if (coaxial.size() > 1) {
            // Counterbored hole
            for (int f : coaxial) {
                traversed.insert(f);
            }
            holes.push_back(CreateCounterboredHole(coaxial));
        } else {
            // Simple hole
            traversed.insert(face_id);
            holes.push_back(CreateSimpleHole(face_id));
        }
    }

    std::cout << "Hole recognizer: Recognized " << holes.size() << " holes" << std::endl;

    return holes;
}

bool HoleRecognizer::IsInternal(int face_id) {
    const TopoDS_Face& face = aag_.GetFace(face_id);
    const FaceAttributes& attrs = aag_.GetFaceAttributes(face_id);

    if (!attrs.is_cylinder) return false;

    try {
        BRepAdaptor_Surface surface(face);

        // Sample at mid-parameter
        double u_mid = (surface.FirstUParameter() + surface.LastUParameter()) / 2.0;
        double v_mid = (surface.FirstVParameter() + surface.LastVParameter()) / 2.0;

        // Compute normal at sample point
        BRepLProp_SLProps props(surface, u_mid, v_mid, 1, 1e-6);
        if (!props.IsNormalDefined()) return false;

        gp_Dir normal = props.Normal();

        // Account for face orientation
        if (face.Orientation() == TopAbs_REVERSED) {
            normal.Reverse();
        }

        gp_Pnt point = props.Value();

        // Vector from point to axis
        const gp_Ax1& axis = attrs.cylinder_axis;
        gp_Pnt axis_loc = axis.Location();
        gp_Dir axis_dir = axis.Direction();

        // Project point onto axis
        gp_Vec vec_to_point(axis_loc, point);
        double projection_length = vec_to_point.Dot(gp_Vec(axis_dir));
        gp_Pnt closest_on_axis = axis_loc.Translated(gp_Vec(axis_dir).Multiplied(projection_length));

        // Radial vector from axis to point
        gp_Vec radial(closest_on_axis, point);
        double radial_mag = radial.Magnitude();

        if (radial_mag < 1e-9) return false;

        gp_Dir radial_dir(radial.X() / radial_mag, radial.Y() / radial_mag, radial.Z() / radial_mag);

        // If normal points toward axis (dot < 0), it's internal (hole)
        double dot = normal.Dot(radial_dir);

        return dot < 0;

    } catch (...) {
        return false;
    }
}

bool HoleRecognizer::HasConcaveCircularEdges(int face_id) {
    const FaceAttributes& attrs = aag_.GetFaceAttributes(face_id);
    if (!attrs.is_cylinder) return false;

    // Get edges bounding this face
    const TopoDS_Face& face = aag_.GetFace(face_id);
    gp_Lin axis_line(attrs.cylinder_axis);

    int semicircle_count = 0;
    int quarter_circle_count = 0;

    // Check edge arc angles
    for (TopExp_Explorer exp(face, TopAbs_EDGE); exp.More(); exp.Next()) {
        TopoDS_Edge edge = TopoDS::Edge(exp.Current());

        try {
            BRepAdaptor_Curve curve(edge);

            // Check if circular
            if (curve.GetType() == GeomAbs_Circle) {
                gp_Circ circle = curve.Circle();
                gp_Pnt circle_center = circle.Location();

                // Check if concentric with axis (distance < tolerance)
                double distance = axis_line.Distance(circle_center);

                if (distance < 1e-3) {  // 0.001mm tolerance
                    // Get parameter range to determine arc angle
                    double first_param = curve.FirstParameter();
                    double last_param = curve.LastParameter();
                    double param_range = last_param - first_param;
                    double arc_angle = param_range * 180.0 / M_PI;

                    // Check if it's a full circle (360°)
                    bool is_full = (std::abs(param_range - 2.0 * M_PI) < 1e-6);

                    if (!is_full) {
                        // It's an arc - check if semicircle (180°) or quarter-circle (90°)
                        if (std::abs(arc_angle - 180.0) < 5.0) {
                            semicircle_count++;
                        } else if (std::abs(arc_angle - 90.0) < 5.0) {
                            quarter_circle_count++;
                        }
                    }
                }
            }
        } catch (...) {
            continue;
        }
    }

    // Holes have multiple semicircular edges (typically 2 or 4)
    // Fillets have quarter-circle edges
    // Return true only if we found semicircular edges and NO quarter-circle edges
    return (semicircle_count > 0 && quarter_circle_count == 0);
}

std::vector<int> HoleRecognizer::FindCoaxialCylinders(int seed_face_id, std::set<int>& traversed) {
    std::vector<int> collected = {seed_face_id};

    const FaceAttributes& seed_attrs = aag_.GetFaceAttributes(seed_face_id);
    const gp_Ax1& ref_axis = seed_attrs.cylinder_axis;

    // Recursive visitor
    std::function<void(int)> visit_recursive = [&](int current_id) {
        std::vector<int> neighbors = aag_.GetNeighbors(current_id);

        for (int neighbor_id : neighbors) {
            if (traversed.count(neighbor_id)) continue;
            if (std::find(collected.begin(), collected.end(), neighbor_id) != collected.end()) continue;

            const FaceAttributes& neighbor_attrs = aag_.GetFaceAttributes(neighbor_id);

            // Check if cylindrical
            if (!neighbor_attrs.is_cylinder) continue;

            // Check if coaxial (same axis)
            if (!AreAxesCoincident(ref_axis, neighbor_attrs.cylinder_axis)) continue;

            // Check if internal
            if (!IsInternal(neighbor_id)) continue;

            // Add to collection and recurse
            collected.push_back(neighbor_id);
            visit_recursive(neighbor_id);
        }
    };

    visit_recursive(seed_face_id);

    return collected;
}

bool HoleRecognizer::AreAxesCoincident(const gp_Ax1& axis1, const gp_Ax1& axis2) {
    const double ang_tol = 1.0 / 180.0 * M_PI;  // 1 degree
    const double lin_tol = 1e-6;

    // Check parallel directions
    gp_Dir dir1 = axis1.Direction();
    gp_Dir dir2 = axis2.Direction();
    double dot = std::abs(dir1.Dot(dir2));

    if (std::abs(dot - 1.0) > std::sin(ang_tol)) {
        return false;
    }

    // Check if axes are on same line
    gp_Pnt loc1 = axis1.Location();
    gp_Pnt loc2 = axis2.Location();

    double dx = loc2.X() - loc1.X();
    double dy = loc2.Y() - loc1.Y();
    double dz = loc2.Z() - loc1.Z();
    double dist = std::sqrt(dx*dx + dy*dy + dz*dz);

    if (dist < lin_tol) return true;

    // Cross product magnitude gives distance between parallel lines
    gp_Vec vec(loc1, loc2);
    gp_Vec cross = vec.Crossed(gp_Vec(dir1));
    double cross_mag = cross.Magnitude();

    return cross_mag < lin_tol;
}

Feature HoleRecognizer::CreateSimpleHole(int face_id) {
    Feature feature;

    // Generate ID
    std::ostringstream oss;
    oss << "hole_" << std::setfill('0') << std::setw(4) << feature_id_counter_++;
    feature.id = oss.str();

    feature.type = "hole";
    feature.subtype = "simple";
    feature.confidence = 0.95;
    feature.source = "hole_recognizer";

    // Add face
    feature.face_ids.push_back(face_id);

    // Extract parameters
    const FaceAttributes& attrs = aag_.GetFaceAttributes(face_id);
    feature.params["diameter_mm"] = 2.0 * attrs.cylinder_radius;
    feature.params["radius_mm"] = attrs.cylinder_radius;

    // Add axis direction
    gp_Dir axis_dir = attrs.cylinder_axis.Direction();
    feature.params["axis_x"] = axis_dir.X();
    feature.params["axis_y"] = axis_dir.Y();
    feature.params["axis_z"] = axis_dir.Z();

    return feature;
}

Feature HoleRecognizer::CreateCounterboredHole(const std::vector<int>& face_ids) {
    Feature feature;

    // Generate ID
    std::ostringstream oss;
    oss << "hole_" << std::setfill('0') << std::setw(4) << feature_id_counter_++;
    feature.id = oss.str();

    feature.type = "hole";
    feature.subtype = "counterbored";
    feature.confidence = 0.95;
    feature.source = "hole_recognizer";

    // Add faces
    feature.face_ids = face_ids;

    // Find minimum radius (inner hole)
    double min_radius = 1e10;
    for (int face_id : face_ids) {
        const FaceAttributes& attrs = aag_.GetFaceAttributes(face_id);
        if (attrs.cylinder_radius < min_radius) {
            min_radius = attrs.cylinder_radius;
        }
    }

    feature.params["diameter_mm"] = 2.0 * min_radius;
    feature.params["radius_mm"] = min_radius;
    feature.params["bore_count"] = static_cast<double>(face_ids.size());

    return feature;
}

} // namespace palmetto
