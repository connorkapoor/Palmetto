/**
 * Pocket Depth Analyzer Implementation
 */

#include "pocket_depth_analyzer.h"

#include <GProp_GProps.hxx>
#include <BRepGProp.hxx>
#include <BRepAdaptor_Surface.hxx>
#include <TopExp_Explorer.hxx>
#include <TopoDS.hxx>
#include <BRepBndLib.hxx>
#include <BRep_Tool.hxx>
#include <Geom_Surface.hxx>
#include <Geom_Plane.hxx>
#include <GeomAPI_ProjectPointOnSurf.hxx>
#include <GeomLProp_SLProps.hxx>

#include <iostream>
#include <algorithm>
#include <cmath>

namespace palmetto {

PocketDepthAnalyzer::PocketDepthAnalyzer(const TopoDS_Shape& shape, const AAG& aag)
    : shape_(shape), aag_(aag) {
    BuildFaceIndex();
}

std::map<int, PocketDepthResult> PocketDepthAnalyzer::AnalyzePockets(
    const std::vector<std::set<int>>& cavity_face_sets) {

    std::cout << "PocketDepthAnalyzer: Analyzing " << cavity_face_sets.size() << " pockets\n";

    std::map<int, PocketDepthResult> results;

    for (size_t i = 0; i < cavity_face_sets.size(); i++) {
        PocketDepthResult result = AnalyzeSinglePocket(cavity_face_sets[i]);
        result.pocket_id = i;
        results[i] = result;

        std::cout << "  Pocket " << i << ": "
                  << "depth=" << result.depth << "mm, "
                  << "opening=" << result.opening_diameter << "mm, "
                  << "type=" << static_cast<int>(result.type) << ", "
                  << "through=" << (result.is_through_hole ? "yes" : "no") << "\n";
    }

    return results;
}

PocketDepthResult PocketDepthAnalyzer::AnalyzeSinglePocket(const std::set<int>& face_ids) {
    PocketDepthResult result;
    result.face_ids = face_ids;

    if (face_ids.empty()) {
        return result;
    }

    // Step 1: Find opening faces (boundary faces with most external connections)
    result.opening_faces = FindOpeningFaces(face_ids);

    if (result.opening_faces.empty()) {
        std::cout << "  WARNING: No opening faces found for pocket\n";
        return result;
    }

    // Step 2: Compute opening plane
    gp_Pln opening_plane = ComputeOpeningPlane(result.opening_faces);
    result.opening_normal = opening_plane.Axis().Direction();

    // Compute opening centroid
    gp_Pnt sum(0, 0, 0);
    for (int face_id : result.opening_faces) {
        gp_Pnt centroid = GetFaceCentroid(index_to_face_[face_id]);
        sum.SetX(sum.X() + centroid.X());
        sum.SetY(sum.Y() + centroid.Y());
        sum.SetZ(sum.Z() + centroid.Z());
    }
    result.opening_centroid = gp_Pnt(
        sum.X() / result.opening_faces.size(),
        sum.Y() / result.opening_faces.size(),
        sum.Z() / result.opening_faces.size()
    );

    // Step 3: Compute depth (maximum distance from opening plane)
    result.depth = ComputeMaxDepth(face_ids, opening_plane);

    // Step 4: Estimate opening diameter
    result.opening_diameter = EstimateOpeningDiameter(result.opening_faces);

    // Step 5: Check if through-hole
    result.is_through_hole = IsThroughHole(face_ids);

    // Step 6: Classify pocket type
    result.type = ClassifyPocket(result.depth, result.opening_diameter, result.is_through_hole);

    // Step 7: Compute metrics
    result.aspect_ratio = (result.opening_diameter > 0.1)
        ? (result.depth / result.opening_diameter)
        : 0.0;
    result.is_deep = (result.aspect_ratio > 2.0);
    result.is_narrow = (result.opening_diameter < 5.0);

    // Step 8: Compute accessibility score
    result.accessibility_score = ComputeAccessibilityScore(result.depth, result.opening_diameter);

    // Step 9: Estimate volume
    result.volume = EstimateVolume(face_ids);

    return result;
}

std::set<int> PocketDepthAnalyzer::FindOpeningFaces(const std::set<int>& cavity_faces) {
    // Opening faces are boundary faces with highest ratio of external to internal adjacencies

    std::map<int, int> external_adjacency_count;
    std::map<int, int> total_adjacency_count;

    for (int face_id : cavity_faces) {
        std::vector<int> neighbors = aag_.GetNeighbors(face_id);

        int external_count = 0;
        int total_count = neighbors.size();

        for (int neighbor_id : neighbors) {
            if (cavity_faces.find(neighbor_id) == cavity_faces.end()) {
                // Neighbor is external to cavity
                external_count++;
            }
        }

        external_adjacency_count[face_id] = external_count;
        total_adjacency_count[face_id] = total_count;
    }

    // Find faces with maximum external adjacency ratio
    double max_ratio = 0;
    for (int face_id : cavity_faces) {
        if (total_adjacency_count[face_id] == 0) continue;

        double ratio = (double)external_adjacency_count[face_id] / total_adjacency_count[face_id];
        max_ratio = std::max(max_ratio, ratio);
    }

    // Collect all faces with ratio >= 80% of max (consider as opening)
    std::set<int> opening_faces;
    double threshold = max_ratio * 0.8;

    for (int face_id : cavity_faces) {
        if (total_adjacency_count[face_id] == 0) continue;

        double ratio = (double)external_adjacency_count[face_id] / total_adjacency_count[face_id];
        if (ratio >= threshold) {
            opening_faces.insert(face_id);
        }
    }

    return opening_faces;
}

gp_Pln PocketDepthAnalyzer::ComputeOpeningPlane(const std::set<int>& opening_faces) {
    // Compute best-fit plane through opening face centroids

    // Step 1: Compute centroid of all opening faces
    gp_XYZ sum(0, 0, 0);
    for (int face_id : opening_faces) {
        gp_Pnt centroid = GetFaceCentroid(index_to_face_[face_id]);
        sum += centroid.XYZ();
    }
    gp_Pnt center(sum / opening_faces.size());

    // Step 2: Average normal of opening faces
    gp_XYZ normal_sum(0, 0, 0);
    for (int face_id : opening_faces) {
        gp_Dir normal = GetFaceNormal(index_to_face_[face_id]);
        normal_sum += normal.XYZ();
    }

    // Normalize and check for zero-length vector
    gp_XYZ avg_vec = normal_sum / opening_faces.size();
    double length = avg_vec.Modulus();

    gp_Dir avg_normal;
    if (length < 1e-6) {
        // Normals cancelled out - use fallback (Z-axis)
        avg_normal = gp_Dir(0, 0, 1);
        std::cout << "  WARNING: Opening normals cancelled out, using Z-axis as fallback\n";
    } else {
        // Normalize to unit vector
        avg_normal = gp_Dir(avg_vec.X() / length, avg_vec.Y() / length, avg_vec.Z() / length);
    }

    // Create plane
    return gp_Pln(center, avg_normal);
}

double PocketDepthAnalyzer::ComputeMaxDepth(const std::set<int>& cavity_faces, const gp_Pln& opening_plane) {
    double max_depth = 0.0;

    for (int face_id : cavity_faces) {
        gp_Pnt centroid = GetFaceCentroid(index_to_face_[face_id]);
        double distance = opening_plane.Distance(centroid);
        max_depth = std::max(max_depth, distance);
    }

    return max_depth;
}

double PocketDepthAnalyzer::EstimateOpeningDiameter(const std::set<int>& opening_faces) {
    if (opening_faces.empty()) return 0.0;

    // Compute bounding box of opening faces
    Bnd_Box bbox;
    for (int face_id : opening_faces) {
        BRepBndLib::Add(index_to_face_[face_id], bbox);
    }

    double xmin, ymin, zmin, xmax, ymax, zmax;
    bbox.Get(xmin, ymin, zmin, xmax, ymax, zmax);

    // Estimate diameter as average of bbox dimensions
    double dx = xmax - xmin;
    double dy = ymax - ymin;
    double dz = zmax - zmin;

    // Use 2D extent (ignore smallest dimension)
    double dims[3] = {dx, dy, dz};
    std::sort(dims, dims + 3);

    // Average of two largest dimensions
    return (dims[1] + dims[2]) / 2.0;
}

bool PocketDepthAnalyzer::IsThroughHole(const std::set<int>& cavity_faces) {
    // A through-hole has opening faces at both "ends"
    // Heuristic: Check if cavity spans significant portion of part bounding box

    Bnd_Box cavity_bbox = GetBoundingBox(cavity_faces);
    Bnd_Box part_bbox;
    BRepBndLib::Add(shape_, part_bbox);

    double cx_min, cy_min, cz_min, cx_max, cy_max, cz_max;
    double px_min, py_min, pz_min, px_max, py_max, pz_max;

    cavity_bbox.Get(cx_min, cy_min, cz_min, cx_max, cy_max, cz_max);
    part_bbox.Get(px_min, py_min, pz_min, px_max, py_max, pz_max);

    // Check if cavity spans > 80% of part extent in any direction
    double cx_span = (cx_max - cx_min) / (px_max - px_min);
    double cy_span = (cy_max - cy_min) / (py_max - py_min);
    double cz_span = (cz_max - cz_min) / (pz_max - pz_min);

    return (cx_span > 0.8 || cy_span > 0.8 || cz_span > 0.8);
}

PocketType PocketDepthAnalyzer::ClassifyPocket(double depth, double opening_diameter, bool is_through) {
    if (is_through) {
        return PocketType::THROUGH_HOLE;
    }

    double aspect_ratio = (opening_diameter > 0.1) ? (depth / opening_diameter) : 0.0;

    if (aspect_ratio < 0.5) {
        return PocketType::SHALLOW_RECESS;
    } else if (aspect_ratio < 2.0) {
        return PocketType::BLIND_POCKET;
    } else {
        return PocketType::DEEP_CAVITY;
    }
}

double PocketDepthAnalyzer::ComputeAccessibilityScore(double depth, double opening_diameter) {
    // Accessibility score based on aspect ratio and opening size
    // 1.0 = easy to machine (wide, shallow)
    // 0.0 = hard to machine (narrow, deep)

    double aspect_ratio = (opening_diameter > 0.1) ? (depth / opening_diameter) : 10.0;

    // Penalty for high aspect ratio
    double aspect_score = 1.0 / (1.0 + aspect_ratio / 2.0);  // 0.5 for AR=2, 0.33 for AR=4

    // Penalty for narrow opening
    double opening_score = std::min(1.0, opening_diameter / 10.0);  // Full score at 10mm+

    // Combined score
    return (aspect_score + opening_score) / 2.0;
}

double PocketDepthAnalyzer::EstimateVolume(const std::set<int>& cavity_faces) {
    // Approximate volume = sum of face areas * average depth
    // (Rough estimate, exact volume would require 3D reconstruction)

    double total_area = 0.0;

    for (int face_id : cavity_faces) {
        const TopoDS_Face& face = index_to_face_[face_id];
        GProp_GProps props;
        BRepGProp::SurfaceProperties(face, props);
        total_area += props.Mass();
    }

    // Estimate depth from bounding box
    Bnd_Box bbox = GetBoundingBox(cavity_faces);
    double xmin, ymin, zmin, xmax, ymax, zmax;
    bbox.Get(xmin, ymin, zmin, xmax, ymax, zmax);

    double dx = xmax - xmin;
    double dy = ymax - ymin;
    double dz = zmax - zmin;

    // Use smallest dimension as depth estimate
    double depth_estimate = std::min({dx, dy, dz});

    return total_area * depth_estimate * 0.5;  // Factor of 0.5 for approximate cavity shape
}

Bnd_Box PocketDepthAnalyzer::GetBoundingBox(const std::set<int>& face_ids) {
    Bnd_Box bbox;
    for (int face_id : face_ids) {
        BRepBndLib::Add(index_to_face_[face_id], bbox);
    }
    return bbox;
}

gp_Pnt PocketDepthAnalyzer::GetFaceCentroid(const TopoDS_Face& face) {
    GProp_GProps props;
    BRepGProp::SurfaceProperties(face, props);
    return props.CentreOfMass();
}

gp_Dir PocketDepthAnalyzer::GetFaceNormal(const TopoDS_Face& face) {
    GProp_GProps props;
    BRepGProp::SurfaceProperties(face, props);
    gp_Pnt centroid = props.CentreOfMass();

    Handle(Geom_Surface) surface = BRep_Tool::Surface(face);
    BRepAdaptor_Surface adaptor(face);

    double u = (adaptor.FirstUParameter() + adaptor.LastUParameter()) / 2.0;
    double v = (adaptor.FirstVParameter() + adaptor.LastVParameter()) / 2.0;

    GeomLProp_SLProps props_surf(surface, u, v, 1, 1e-6);

    if (props_surf.IsNormalDefined()) {
        gp_Dir normal = props_surf.Normal();
        if (face.Orientation() == TopAbs_REVERSED) {
            normal.Reverse();
        }
        return normal;
    }

    return gp_Dir(0, 0, 1);
}

void PocketDepthAnalyzer::BuildFaceIndex() {
    index_to_face_.clear();

    for (TopExp_Explorer exp(shape_, TopAbs_FACE); exp.More(); exp.Next()) {
        TopoDS_Face face = TopoDS::Face(exp.Current());
        index_to_face_.push_back(face);
    }
}

} // namespace palmetto
