/**
 * Chamfer Recognizer Implementation
 */

#include "chamfer_recognizer.h"

#include <iostream>
#include <cmath>
#include <sstream>
#include <iomanip>
#include <algorithm>

// Define M_PI if not already defined
#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

// OpenCASCADE includes for geometry analysis
#include <BRepAdaptor_Curve.hxx>
#include <BRepBndLib.hxx>
#include <Bnd_Box.hxx>
#include <gp_Dir.hxx>
#include <gp_Pnt.hxx>
#include <gp_Vec.hxx>
#include <GeomAbs_CurveType.hxx>
#include <TopExp_Explorer.hxx>
#include <TopoDS.hxx>

namespace palmetto {

int ChamferRecognizer::feature_id_counter_ = 0;

ChamferRecognizer::ChamferRecognizer(const AAG& aag)
    : aag_(aag)
{
}

std::vector<Feature> ChamferRecognizer::Recognize(double max_width) {
    std::vector<Feature> chamfers;

    std::cout << "Chamfer recognizer: Checking faces for chamfers\n";

    // Iterate through all faces
    int face_count = aag_.GetFaceCount();

    int planar_count = 0;
    for (int i = 0; i < face_count; i++) {
        const FaceAttributes& attrs = aag_.GetFaceAttributes(i);

        if (!attrs.is_planar) continue;
        planar_count++;

        if (IsChamferCandidate(i, max_width)) {
            double width = GetChamferWidth(i);
            Feature chamfer = CreateChamfer(i, width);
            chamfers.push_back(chamfer);
        }
    }

    std::cout << "  Found " << planar_count << " planar faces\n";
    std::cout << "Chamfer recognizer: Recognized " << chamfers.size() << " chamfers\n";

    return chamfers;
}

bool ChamferRecognizer::IsChamferCandidate(int face_id, double max_width) {
    const FaceAttributes& attrs = aag_.GetFaceAttributes(face_id);

    // Must be planar
    if (!attrs.is_planar) {
        return false;
    }

    // CRITICAL: Chamfers are beveled edges, not primary surfaces
    // Their normals should NOT be aligned with coordinate axes (X, Y, or Z)
    // Real chamfers have normals at standard angles (typically 30°, 45°, or 60°)
    const gp_Vec& normal = attrs.plane_normal;
    double nx = std::abs(normal.X());
    double ny = std::abs(normal.Y());
    double nz = std::abs(normal.Z());

    // Check if normal is aligned with any principal axis (within tolerance)
    const double axis_alignment_tolerance = 0.1;  // ~6 degrees
    bool aligned_with_x = (nx > 0.99 && ny < axis_alignment_tolerance && nz < axis_alignment_tolerance);
    bool aligned_with_y = (ny > 0.99 && nx < axis_alignment_tolerance && nz < axis_alignment_tolerance);
    bool aligned_with_z = (nz > 0.99 && nx < axis_alignment_tolerance && ny < axis_alignment_tolerance);

    if (aligned_with_x || aligned_with_y || aligned_with_z) {
        // This is a primary surface (top, side, etc.), not a chamfer
        return false;
    }

    // Additional check: Chamfer angles should be reasonable (20-70°)
    // This filters out shallow draft angles (<20°) and steep walls (>70°)
    // For a planar face at angle θ from horizontal, one normal component ≈ sin(θ)
    // Find the minimum component (closest to horizontal plane)
    double min_component = std::min({nx, ny, nz});
    double max_component = std::max({nx, ny, nz});

    // sin(20°) ≈ 0.342, sin(70°) ≈ 0.940
    // If the smallest component is > 0.342, the face is too steep (>70° from that axis)
    // If the largest component is > 0.940, the face is too shallow (<20° from that axis)
    if (max_component > 0.94) {
        // Too shallow - likely a draft angle or shallow slope, not a chamfer
        return false;
    }

    // Must have small area (chamfers are small beveled edges)
    // Approximate width check based on area
    if (attrs.area > max_width * max_width * 10) {
        return false;
    }

    // Must have linear edges (not circular arcs)
    if (!HasLinearEdges(face_id)) {
        return false;
    }

    // Must have sharp edges (not smooth/tangent connections)
    if (!HasSharpEdges(face_id)) {
        return false;
    }

    return true;
}

bool ChamferRecognizer::HasLinearEdges(int face_id) {
    const TopoDS_Face& face = aag_.GetFace(face_id);

    int line_edge_count = 0;
    int total_edges = 0;

    // Check edge types
    for (TopExp_Explorer exp(face, TopAbs_EDGE); exp.More(); exp.Next()) {
        TopoDS_Edge edge = TopoDS::Edge(exp.Current());
        total_edges++;

        try {
            BRepAdaptor_Curve curve(edge);

            // Check if it's a line
            if (curve.GetType() == GeomAbs_Line) {
                line_edge_count++;
            }
        } catch (...) {
            continue;
        }
    }

    // Chamfers typically have mostly linear edges (at least 2-3)
    // Allow some circular edges for corner connections
    return (line_edge_count >= 2);
}

bool ChamferRecognizer::HasSharpEdges(int face_id) {
    // Get neighbors
    std::vector<int> neighbors = aag_.GetNeighbors(face_id);

    int sharp_edge_count = 0;

    for (int neighbor_id : neighbors) {
        double dihedral = aag_.GetDihedralAngle(face_id, neighbor_id);

        // Sharp edge: dihedral angle significantly different from 180°
        // 180° would be a smooth/tangent connection (like fillets)
        double deviation_from_180 = std::abs(dihedral - 180.0);

        bool is_sharp = (deviation_from_180 > SHARP_ANGLE_THRESHOLD);

        if (is_sharp) {
            sharp_edge_count++;
        }
    }

    // Chamfers typically have at least 2 sharp edges
    // (connecting at angles to support faces)
    return sharp_edge_count >= 2;
}

double ChamferRecognizer::GetChamferWidth(int face_id) {
    const TopoDS_Face& face = aag_.GetFace(face_id);

    // Compute bounding box to estimate width
    Bnd_Box bbox;
    BRepBndLib::Add(face, bbox);

    if (bbox.IsVoid()) {
        return 0.0;
    }

    double xmin, ymin, zmin, xmax, ymax, zmax;
    bbox.Get(xmin, ymin, zmin, xmax, ymax, zmax);

    // Use maximum dimension as width estimate
    double dx = xmax - xmin;
    double dy = ymax - ymin;
    double dz = zmax - zmin;

    return std::max({dx, dy, dz});
}

Feature ChamferRecognizer::CreateChamfer(int face_id, double width) {
    const FaceAttributes& attrs = aag_.GetFaceAttributes(face_id);

    Feature feature;

    // Generate ID
    std::ostringstream oss;
    oss << "chamfer_" << std::setfill('0') << std::setw(4) << feature_id_counter_++;
    feature.id = oss.str();

    feature.type = "chamfer";
    feature.subtype = "bevel";
    feature.source = "chamfer_recognizer";
    feature.confidence = 0.80;

    // Face IDs
    feature.face_ids.push_back(face_id);

    // Parameters
    feature.params["width_mm"] = width;
    feature.params["area_mm2"] = attrs.area;

    // Add normal direction
    feature.params["normal_x"] = attrs.plane_normal.X();
    feature.params["normal_y"] = attrs.plane_normal.Y();
    feature.params["normal_z"] = attrs.plane_normal.Z();

    return feature;
}

} // namespace palmetto
