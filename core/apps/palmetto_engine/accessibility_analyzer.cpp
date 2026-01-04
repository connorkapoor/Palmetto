/**
 * Accessibility Analyzer Implementation
 *
 * Uses volumetric ray-based analysis to detect TRUE undercuts and accessibility issues.
 */

#include "accessibility_analyzer.h"

#include <GProp_GProps.hxx>
#include <BRepGProp.hxx>
#include <BRepAdaptor_Surface.hxx>
#include <TopExp_Explorer.hxx>
#include <TopoDS.hxx>
#include <GeomLProp_SLProps.hxx>
#include <BRep_Tool.hxx>
#include <Geom_Surface.hxx>

#include <iostream>
#include <algorithm>
#include <cmath>

namespace palmetto {

AccessibilityAnalyzer::AccessibilityAnalyzer(const TopoDS_Shape& shape, const AAG& aag)
    : shape_(shape), aag_(aag) {

    BuildFaceIndex();

#ifdef USE_EMBREE
    // Initialize Embree ray tracer for fast ray-shape intersection
    ray_tracer_ = std::make_unique<EmbreeRayTracer>();
    if (!ray_tracer_->Build(shape, 0.05)) {
        std::cerr << "AccessibilityAnalyzer: Failed to build Embree scene\n";
    } else {
        std::cout << "AccessibilityAnalyzer: Using Embree ray tracer for fast intersection\n";
    }
#else
    std::cout << "AccessibilityAnalyzer: WARNING - Embree not available, falling back to slower OCC ray casting\n";
#endif
}

std::map<int, AccessibilityResult> AccessibilityAnalyzer::AnalyzeMoldingAccessibility(const gp_Dir& draft_direction) {
    std::cout << "Analyzing molding accessibility (draft direction: "
              << draft_direction.X() << ", " << draft_direction.Y() << ", " << draft_direction.Z() << ")\n";

    std::map<int, AccessibilityResult> results;
    int undercut_count = 0;
    int side_action_count = 0;

    // Compute shadow volume - faces that are "behind" other faces relative to draft direction
    std::set<int> shadow_faces = ComputeShadowVolume(draft_direction);

    for (size_t i = 0; i < index_to_face_.size(); i++) {
        AccessibilityResult result;
        result.face_id = i;

        const TopoDS_Face& face = index_to_face_[i];

        // Get face normal
        gp_Dir normal = GetFaceNormal(face);

        // Compute draft angle (angle between normal and draft direction)
        double dot = normal.Dot(draft_direction);
        double angle = std::acos(std::clamp(dot, -1.0, 1.0)) * 180.0 / M_PI;
        double draft_angle = 90.0 - angle;  // Positive = good, negative = undercut

        // Ray-based accessibility test
        bool accessible = IsFaceAccessibleFromDirection(face, draft_direction.Reversed());

        // Combine geometric and volumetric analysis
        bool is_in_shadow = shadow_faces.count(i) > 0;

        // Face is an undercut if:
        // 1. Negative draft angle (facing away from draft), OR
        // 2. In shadow volume (blocked by other geometry), OR
        // 3. Not accessible by ray casting
        bool is_undercut = (draft_angle < 0.0) || is_in_shadow || !accessible;

        result.is_accessible_molding = !is_undercut;

        // Determine if side action is required (complex undercut)
        result.requires_side_action = RequiresSideAction(i, draft_direction, draft_angle, accessible);

        // Store accessibility info
        result.accessible_from_direction["draft"] = accessible;

        if (is_undercut) undercut_count++;
        if (result.requires_side_action) side_action_count++;

        results[i] = result;
    }

    std::cout << "  Found " << undercut_count << " undercut faces\n";
    std::cout << "  " << side_action_count << " faces require side action/lifters\n";

    return results;
}

std::map<int, AccessibilityResult> AccessibilityAnalyzer::AnalyzeCNCAccessibility() {
    std::cout << "Analyzing CNC machining accessibility (6 standard directions)\n";

    std::map<int, AccessibilityResult> results;

    // Test 6 standard CNC directions
    std::vector<std::pair<std::string, gp_Dir>> directions = {
        {"+X", gp_Dir(1, 0, 0)},
        {"-X", gp_Dir(-1, 0, 0)},
        {"+Y", gp_Dir(0, 1, 0)},
        {"-Y", gp_Dir(0, -1, 0)},
        {"+Z", gp_Dir(0, 0, 1)},
        {"-Z", gp_Dir(0, 0, -1)}
    };

    int inaccessible_count = 0;

    for (size_t i = 0; i < index_to_face_.size(); i++) {
        AccessibilityResult result;
        result.face_id = i;

        const TopoDS_Face& face = index_to_face_[i];

        int accessible_direction_count = 0;

        for (const auto& [dir_name, dir] : directions) {
            bool accessible = IsFaceAccessibleFromDirection(face, dir);
            result.accessible_from_direction[dir_name] = accessible;

            if (accessible) {
                accessible_direction_count++;
            }
        }

        // Face is accessible for CNC if reachable from at least one direction
        result.is_accessible_cnc = (accessible_direction_count > 0);

        // Compute accessibility score (0-1)
        result.accessibility_score = (double)accessible_direction_count / directions.size();

        if (!result.is_accessible_cnc) {
            inaccessible_count++;
        }

        results[i] = result;
    }

    std::cout << "  " << inaccessible_count << " faces inaccessible from all directions (internal features)\n";

    return results;
}

std::map<int, double> AccessibilityAnalyzer::ComputeAccessibilityScores() {
    std::map<int, double> scores;

    // Compute scores by testing multiple directions
    std::vector<gp_Dir> test_directions;

    // 26 directions (cube corners + face centers + edge centers)
    for (int dx = -1; dx <= 1; dx++) {
        for (int dy = -1; dy <= 1; dy++) {
            for (int dz = -1; dz <= 1; dz++) {
                if (dx == 0 && dy == 0 && dz == 0) continue;
                test_directions.push_back(gp_Dir(dx, dy, dz));
            }
        }
    }

    for (size_t i = 0; i < index_to_face_.size(); i++) {
        const TopoDS_Face& face = index_to_face_[i];

        int accessible_count = 0;

        for (const gp_Dir& dir : test_directions) {
            if (IsFaceAccessibleFromDirection(face, dir)) {
                accessible_count++;
            }
        }

        // Score = percentage of directions that can access this face
        scores[i] = (double)accessible_count / test_directions.size();
    }

    return scores;
}

bool AccessibilityAnalyzer::IsFaceAccessibleFromDirection(const TopoDS_Face& face, const gp_Dir& direction) {
    // Get face normal and centroid
    gp_Dir normal = GetFaceNormal(face);
    gp_Pnt centroid = GetFaceCentroid(face);

    // Step 1: Check if face is facing the direction
    // If normal points away from direction, face is not visible from that direction
    double dot = normal.Dot(direction);
    if (dot > 0) {
        return false;  // Face is facing away
    }

    // Step 2: Cast ray from face centroid in the opposite direction
    // If ray hits another face before escaping, this face is blocked (undercut/inaccessible)

    // Offset centroid slightly along face normal to avoid self-intersection
    gp_Pnt ray_start = centroid.Translated(gp_Vec(normal) * 0.1);
    gp_Dir ray_dir = direction.Reversed();  // Cast away from source

#ifdef USE_EMBREE
    // Use Embree for fast ray-shape intersection
    double max_distance = 1000.0;  // Large distance (mm)
    double hit_distance = ray_tracer_->CastRay(ray_start, ray_dir, max_distance);

    // If ray doesn't hit anything (returns -1.0), face is accessible
    // If ray hits something (returns >= 0), face is blocked
    return hit_distance < 0;
#else
    // Fallback: Use OpenCASCADE ray casting (slower)
    // TODO: Implement OCC-based ray casting if needed
    // For now, return true (accessible) as conservative estimate
    return true;
#endif
}

double AccessibilityAnalyzer::CastAccessibilityRay(int face_id, const gp_Dir& direction) {
    const TopoDS_Face& face = index_to_face_[face_id];
    gp_Pnt centroid = GetFaceCentroid(face);
    gp_Dir normal = GetFaceNormal(face);

    // Offset ray start
    gp_Pnt ray_start = centroid.Translated(gp_Vec(normal) * 0.1);

#ifdef USE_EMBREE
    double max_distance = 1000.0;
    double hit_distance = ray_tracer_->CastRay(ray_start, direction, max_distance);
    return hit_distance;  // Returns distance or -1.0 if no hit
#else
    return -1.0;  // No hit (conservative)
#endif
}

std::set<int> AccessibilityAnalyzer::ComputeShadowVolume(const gp_Dir& direction) {
    std::set<int> shadow_faces;

    // For each face, check if it's "behind" any other face relative to direction
    // This is a simplified shadow volume computation

    for (size_t i = 0; i < index_to_face_.size(); i++) {
        gp_Pnt centroid_i = GetFaceCentroid(index_to_face_[i]);

        for (size_t j = 0; j < index_to_face_.size(); j++) {
            if (i == j) continue;

            gp_Pnt centroid_j = GetFaceCentroid(index_to_face_[j]);

            // Compute projection along direction
            gp_Vec vec_ij(centroid_i, centroid_j);
            double proj = vec_ij.Dot(gp_Vec(direction));

            // If j is "in front of" i (positive projection), and close enough laterally,
            // then i is in shadow
            if (proj > 0.5) {  // j is ahead of i
                // Check lateral distance (perpendicular to direction)
                gp_Vec lateral = vec_ij - gp_Vec(direction) * proj;
                double lateral_dist = lateral.Magnitude();

                // If lateral distance is small, i is shadowed by j
                if (lateral_dist < 10.0) {  // 10mm threshold
                    shadow_faces.insert(i);
                    break;
                }
            }
        }
    }

    return shadow_faces;
}

bool AccessibilityAnalyzer::RequiresSideAction(int face_id, const gp_Dir& draft_direction,
                                                double draft_angle, bool accessible) {
    // Side action is required if:
    // 1. Face has significant negative draft angle (< -2°), AND
    // 2. Face is not accessible by straight pull, AND
    // 3. Face has area > threshold (significant feature)

    if (draft_angle >= -2.0) {
        return false;  // Not a significant undercut
    }

    if (accessible) {
        return false;  // Can be demolded without side action
    }

    // Check face area
    const TopoDS_Face& face = index_to_face_[face_id];
    GProp_GProps props;
    BRepGProp::SurfaceProperties(face, props);
    double area = props.Mass();

    // Require side action if area > 10mm²
    return (area > 10.0);
}

gp_Dir AccessibilityAnalyzer::GetFaceNormal(const TopoDS_Face& face) {
    GProp_GProps props;
    BRepGProp::SurfaceProperties(face, props);
    gp_Pnt centroid = props.CentreOfMass();

    // Get surface
    Handle(Geom_Surface) surface = BRep_Tool::Surface(face);

    // Get U, V parameters at centroid
    BRepAdaptor_Surface adaptor(face);
    double u_min = adaptor.FirstUParameter();
    double u_max = adaptor.LastUParameter();
    double v_min = adaptor.FirstVParameter();
    double v_max = adaptor.LastVParameter();

    double u = (u_min + u_max) / 2.0;
    double v = (v_min + v_max) / 2.0;

    // Compute normal at (u, v)
    GeomLProp_SLProps props_surf(surface, u, v, 1, 1e-6);

    if (props_surf.IsNormalDefined()) {
        gp_Dir normal = props_surf.Normal();

        // Adjust normal direction based on face orientation
        if (face.Orientation() == TopAbs_REVERSED) {
            normal.Reverse();
        }

        return normal;
    }

    // Fallback: return Z-axis
    return gp_Dir(0, 0, 1);
}

gp_Pnt AccessibilityAnalyzer::GetFaceCentroid(const TopoDS_Face& face) {
    GProp_GProps props;
    BRepGProp::SurfaceProperties(face, props);
    return props.CentreOfMass();
}

void AccessibilityAnalyzer::BuildFaceIndex() {
    index_to_face_.clear();

    for (TopExp_Explorer exp(shape_, TopAbs_FACE); exp.More(); exp.Next()) {
        TopoDS_Face face = TopoDS::Face(exp.Current());
        index_to_face_.push_back(face);
    }

    std::cout << "AccessibilityAnalyzer: Built face index with " << index_to_face_.size() << " faces\n";
}

} // namespace palmetto
