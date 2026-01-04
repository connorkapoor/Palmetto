#include "draft_angle_analyzer.h"
#include <BRepAdaptor_Surface.hxx>
#include <GProp_GProps.hxx>
#include <BRepGProp.hxx>
#include <TopExp_Explorer.hxx>
#include <TopoDS.hxx>
#include <gp_Pnt.hxx>
#include <gp_Vec.hxx>
#include <Precision.hxx>
#include <cmath>
#include <iostream>

DraftAngleAnalyzer::DraftAngleAnalyzer(const TopoDS_Shape& shape, const gp_Dir& draft_direction)
    : shape_(shape), draft_direction_(draft_direction) {
}

std::map<int, double> DraftAngleAnalyzer::AnalyzeDraftAngles() {
    std::map<int, double> draft_map;

    int face_id = 0;
    for (TopExp_Explorer exp(shape_, TopAbs_FACE); exp.More(); exp.Next(), face_id++) {
        TopoDS_Face face = TopoDS::Face(exp.Current());
        double draft_angle = ComputeDraftAngle(face);
        draft_map[face_id] = draft_angle;
    }

    std::cout << "Draft angle analysis: " << draft_map.size() << " faces analyzed\n";
    return draft_map;
}

std::map<int, double> DraftAngleAnalyzer::AnalyzeOverhangs() {
    std::map<int, double> overhang_map;

    int face_id = 0;
    for (TopExp_Explorer exp(shape_, TopAbs_FACE); exp.More(); exp.Next(), face_id++) {
        TopoDS_Face face = TopoDS::Face(exp.Current());
        double overhang_angle = ComputeOverhangAngle(face);
        overhang_map[face_id] = overhang_angle;
    }

    std::cout << "Overhang analysis: " << overhang_map.size() << " faces analyzed\n";
    return overhang_map;
}

std::map<int, bool> DraftAngleAnalyzer::DetectUndercuts() {
    std::map<int, bool> undercut_map;

    int face_id = 0;
    for (TopExp_Explorer exp(shape_, TopAbs_FACE); exp.More(); exp.Next(), face_id++) {
        TopoDS_Face face = TopoDS::Face(exp.Current());
        double draft_angle = ComputeDraftAngle(face);

        // Negative draft angle = undercut
        undercut_map[face_id] = (draft_angle < 0.0);
    }

    int undercut_count = 0;
    for (const auto& pair : undercut_map) {
        if (pair.second) undercut_count++;
    }

    std::cout << "Undercut detection: " << undercut_count << " undercuts found\n";
    return undercut_map;
}

double DraftAngleAnalyzer::ComputeDraftAngle(const TopoDS_Face& face) {
    try {
        // Get face normal
        gp_Dir normal = GetFaceNormal(face);

        // Compute angle between normal and draft direction
        // angle = acos(normal · draft_direction)
        double dot_product = normal.Dot(draft_direction_);

        // Clamp to [-1, 1] to avoid numerical errors
        dot_product = std::max(-1.0, std::min(1.0, dot_product));

        double angle_from_vertical = std::acos(dot_product) * 180.0 / M_PI;

        // Draft angle = 90° - angle_from_vertical
        // Positive = face can be demolded
        // Negative = undercut
        double draft_angle = 90.0 - angle_from_vertical;

        return draft_angle;

    } catch (const Standard_Failure& e) {
        return 0.0;  // Return neutral angle on error
    }
}

double DraftAngleAnalyzer::ComputeOverhangAngle(const TopoDS_Face& face) {
    try {
        // Get face normal
        gp_Dir normal = GetFaceNormal(face);

        // For 3D printing, build direction is typically Z-axis (0, 0, 1)
        gp_Dir build_direction(0, 0, 1);

        // Compute angle between normal and build direction
        double dot_product = normal.Dot(build_direction);

        // Clamp to [-1, 1]
        dot_product = std::max(-1.0, std::min(1.0, dot_product));

        double angle_from_vertical = std::acos(dot_product) * 180.0 / M_PI;

        // Overhang angle = angle from horizontal
        // 0° = horizontal (worst overhang)
        // 90° = vertical (no overhang)
        double overhang_angle = angle_from_vertical;

        return overhang_angle;

    } catch (const Standard_Failure& e) {
        return 90.0;  // Return vertical angle on error (no overhang)
    }
}

gp_Dir DraftAngleAnalyzer::GetFaceNormal(const TopoDS_Face& face) {
    try {
        // Compute face centroid
        GProp_GProps props;
        BRepGProp::SurfaceProperties(face, props);
        gp_Pnt centroid = props.CentreOfMass();

        // Get surface adapter
        BRepAdaptor_Surface surface(face);

        // Find UV parameters at centroid (approximate)
        double u_mid = (surface.FirstUParameter() + surface.LastUParameter()) / 2.0;
        double v_mid = (surface.FirstVParameter() + surface.LastVParameter()) / 2.0;

        // Compute normal at mid-point
        gp_Pnt point;
        gp_Vec du, dv;
        surface.D1(u_mid, v_mid, point, du, dv);

        gp_Vec normal = du.Crossed(dv);

        if (normal.Magnitude() < Precision::Confusion()) {
            // Degenerate normal, return Z-axis as fallback
            return gp_Dir(0, 0, 1);
        }

        normal.Normalize();

        // Ensure normal points outward for FORWARD orientation
        if (face.Orientation() == TopAbs_REVERSED) {
            normal.Reverse();
        }

        return gp_Dir(normal);

    } catch (const Standard_Failure& e) {
        // Return Z-axis as fallback
        return gp_Dir(0, 0, 1);
    }
}
