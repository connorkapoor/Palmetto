/**
 * Thin Wall Recognizer Implementation
 */

#include "thin_wall_recognizer.h"

#include <iostream>
#include <cmath>
#include <sstream>
#include <iomanip>
#include <cfloat>
#include <algorithm>

// Define M_PI if not already defined
#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

// OpenCASCADE includes
#include <BRepAdaptor_Surface.hxx>
#include <BRepBndLib.hxx>
#include <BRepGProp.hxx>
#include <GProp_GProps.hxx>
#include <IntCurvesFace_ShapeIntersector.hxx>
#include <Precision.hxx>
#include <gp_Lin.hxx>
#include <TopExp_Explorer.hxx>
#include <TopoDS.hxx>
#include <BRep_Tool.hxx>

namespace palmetto {

int ThinWallRecognizer::feature_id_counter_ = 0;

ThinWallRecognizer::ThinWallRecognizer(const AAG& aag)
    : aag_(aag)
    , threshold_(3.0)
    , enable_ray_casting_(false)
{
}

std::vector<Feature> ThinWallRecognizer::Recognize(double threshold, bool enable_ray_casting) {
    threshold_ = threshold;
    enable_ray_casting_ = enable_ray_casting;

    std::vector<Feature> thin_walls;

    std::cout << "Thin wall recognizer: threshold=" << threshold_ << "mm\n";

    // Phase 1: Find candidate face pairs
    // Use larger search radius (10x threshold) to catch faces far apart spatially
    // (actual thickness measured by ray casting)
    std::vector<FacePair> candidates = FindOpposingFacePairs(threshold_ * 10.0);
    std::cout << "  Found " << candidates.size() << " candidate face pairs\n";

    // Phases 2-4: Measure, validate, classify
    std::set<int> processed_faces;

    for (const FacePair& pair : candidates) {
        if (processed_faces.count(pair.face1_id) || processed_faces.count(pair.face2_id)) {
            continue;  // Already part of another thin wall
        }

        // Phase 2: Measure thickness
        ThicknessMeasurement measurement = MeasureThicknessBetweenFaces(pair.face1_id, pair.face2_id);

        // Phase 3: Validate
        if (!ValidateThinWall(pair, measurement)) {
            continue;
        }

        // Phase 4: Classify subtype
        std::vector<int> face_ids = {pair.face1_id, pair.face2_id};
        std::string subtype = ClassifyThinWallSubtype(face_ids);

        // Create feature
        Feature feature = CreateThinWallFeature(face_ids, measurement, subtype);
        thin_walls.push_back(feature);

        processed_faces.insert(pair.face1_id);
        processed_faces.insert(pair.face2_id);

        std::cout << "  Thin wall " << feature.id << ": " << subtype
                  << ", thickness=" << measurement.avg_thickness << "mm\n";
    }

    std::cout << "  Recognized " << thin_walls.size() << " thin walls\n";

    return thin_walls;
}

// ========================================================================================
// Phase 1: Find Opposing Face Pairs
// ========================================================================================

std::vector<FacePair> ThinWallRecognizer::FindOpposingFacePairs(double max_distance) {
    std::vector<FacePair> pairs;

    int face_count = aag_.GetFaceCount();

    // Build bounding boxes for spatial acceleration
    std::vector<Bnd_Box> face_bboxes(face_count);
    for (int i = 0; i < face_count; i++) {
        face_bboxes[i] = ComputeFaceBoundingBox(i);
    }

    int bbox_rejects = 0, normal_rejects = 0, distance_rejects = 0;

    // Iterate all face pairs
    for (int i = 0; i < face_count; i++) {
        const FaceAttributes& attr1 = aag_.GetFaceAttributes(i);

        // Skip very small faces
        if (attr1.area < MIN_FACE_AREA) continue;

        for (int j = i + 1; j < face_count; j++) {
            const FaceAttributes& attr2 = aag_.GetFaceAttributes(j);

            // Skip very small faces
            if (attr2.area < MIN_FACE_AREA) continue;

            // Quick reject: bounding box distance test
            // Use generous bbox filtering since we'll validate thickness with ray casting
            double bbox_dist = BBoxDistance(face_bboxes[i], face_bboxes[j]);
            if (bbox_dist > max_distance) {
                bbox_rejects++;
                continue;
            }

            // Compute average normals
            gp_Vec normal1 = ComputeAverageFaceNormal(i);
            gp_Vec normal2 = ComputeAverageFaceNormal(j);

            // Check if normals are anti-parallel (opposing faces)
            double dot = normal1.Dot(normal2);

            if (dot > NORMAL_ANTIPARALLEL_THRESHOLD) {
                normal_rejects++;
                continue;  // Not anti-parallel enough
            }

            // Estimate distance between face centroids
            gp_Pnt center1 = ComputeFaceCentroid(i);
            gp_Pnt center2 = ComputeFaceCentroid(j);
            double distance = center1.Distance(center2);

            // Accept candidates within search radius (actual thickness validated later via ray casting)
            if (distance <= max_distance) {
                pairs.push_back(FacePair(i, j, distance, dot));
            } else {
                distance_rejects++;
            }
        }
    }

    std::cout << "  Candidate filtering: " << bbox_rejects << " bbox rejects, "
              << normal_rejects << " normal rejects, " << distance_rejects << " distance rejects\n";

    return pairs;
}

// ========================================================================================
// Phase 2: Thickness Measurement
// ========================================================================================

ThicknessMeasurement ThinWallRecognizer::MeasureThicknessBetweenFaces(int face1_id, int face2_id) {
    const TopoDS_Face& face1 = aag_.GetFace(face1_id);
    const TopoDS_Face& face2 = aag_.GetFace(face2_id);
    const FaceAttributes& attr1 = aag_.GetFaceAttributes(face1_id);
    const FaceAttributes& attr2 = aag_.GetFaceAttributes(face2_id);

    ThicknessMeasurement result;

    // Strategy 1: Cylindrical faces (concentric)
    if (attr1.is_cylinder && attr2.is_cylinder) {
        if (AreAxesParallel(attr1.cylinder_axis, attr2.cylinder_axis)) {
            // Concentric cylinders: radial distance
            double radial_dist = std::abs(attr1.cylinder_radius - attr2.cylinder_radius);
            result.avg_thickness = radial_dist;
            result.min_thickness = radial_dist;
            result.max_thickness = radial_dist;
            result.variance = 0.0;
            result.overlap_ratio = 1.0;  // Assume full overlap for concentric

            return result;
        }
    }

    // Strategy 2: Grid sampling with ray casting
    try {
        BRepAdaptor_Surface surf1(face1);

        double u_min = surf1.FirstUParameter();
        double u_max = surf1.LastUParameter();
        double v_min = surf1.FirstVParameter();
        double v_max = surf1.LastVParameter();

        int samples = 0;
        double sum = 0.0, sum_sq = 0.0;
        double min_dist = DBL_MAX, max_dist = 0.0;

        // 5x5 grid sampling
        const int grid_size = 5;
        for (int i = 0; i < grid_size; i++) {
            for (int j = 0; j < grid_size; j++) {
                double u = u_min + (u_max - u_min) * i / (grid_size - 1.0);
                double v = v_min + (v_max - v_min) * j / (grid_size - 1.0);

                gp_Pnt point;
                gp_Vec du, dv;
                surf1.D1(u, v, point, du, dv);

                // Compute normal (cross product)
                gp_Vec normal = du.Crossed(dv);
                if (normal.Magnitude() < Precision::Confusion()) continue;
                normal.Normalize();

                // Account for face orientation
                if (face1.Orientation() == TopAbs_REVERSED) {
                    normal.Reverse();
                }

                // Cast ray along normal
                double dist = CastRayToFace(point, gp_Dir(normal), face2);

                if (dist > 0.01 && dist < threshold_ * 2.0) {
                    result.sample_points.push_back(point);
                    result.sample_thicknesses.push_back(dist);
                    sum += dist;
                    sum_sq += dist * dist;
                    min_dist = std::min(min_dist, dist);
                    max_dist = std::max(max_dist, dist);
                    samples++;
                }
            }
        }

        if (samples > 0) {
            result.avg_thickness = sum / samples;
            result.min_thickness = min_dist;
            result.max_thickness = max_dist;
            result.variance = (sum_sq / samples) - (result.avg_thickness * result.avg_thickness);
            result.overlap_ratio = static_cast<double>(samples) / (grid_size * grid_size);
        }
    }
    catch (...) {
        // If anything fails, return empty measurement
        std::cerr << "  Error measuring thickness between faces "
                  << face1_id << " and " << face2_id << "\n";
    }

    return result;
}

double ThinWallRecognizer::CastRayToFace(const gp_Pnt& origin, const gp_Dir& direction, const TopoDS_Face& target) {
    try {
        gp_Lin ray(origin, direction);

        IntCurvesFace_ShapeIntersector intersector;
        intersector.Load(target, Precision::Confusion());
        intersector.Perform(ray, -RealLast(), RealLast());

        if (intersector.IsDone() && intersector.NbPnt() > 0) {
            double min_dist = DBL_MAX;

            for (int i = 1; i <= intersector.NbPnt(); i++) {
                gp_Pnt hit = intersector.Pnt(i);
                double dist = origin.Distance(hit);

                // Ignore self-intersection (very close hits)
                if (dist > 0.01 && dist < min_dist) {
                    min_dist = dist;
                }
            }

            return (min_dist < DBL_MAX) ? min_dist : -1.0;
        }
    }
    catch (...) {
        // Ray casting failed
    }

    return -1.0;
}

// ========================================================================================
// Phase 3: Validation
// ========================================================================================

bool ThinWallRecognizer::ValidateThinWall(const FacePair& pair, const ThicknessMeasurement& measurement) {
    // Criterion 1: Average thickness within threshold
    if (measurement.avg_thickness <= 0.0 || measurement.avg_thickness > threshold_) {
        std::cout << "    × Pair (" << pair.face1_id << "," << pair.face2_id
                  << "): thickness " << measurement.avg_thickness << "mm exceeds threshold\n";
        return false;
    }

    // Criterion 2: Uniform thickness (coefficient of variation < 30%)
    if (measurement.avg_thickness > 0.0) {
        double cv = std::sqrt(measurement.variance) / measurement.avg_thickness;
        if (cv > THICKNESS_VARIANCE_LIMIT) {
            std::cout << "    × Pair (" << pair.face1_id << "," << pair.face2_id
                      << "): thickness variance too high (CV=" << (cv*100) << "%)\n";
            return false;  // Too much variation
        }
    }

    // Criterion 3: Sufficient overlap (>20% of samples hit)
    if (measurement.overlap_ratio < OVERLAP_RATIO_MIN) {
        std::cout << "    × Pair (" << pair.face1_id << "," << pair.face2_id
                  << "): insufficient overlap (" << (measurement.overlap_ratio * 100) << "%)\n";
        return false;
    }

    // Criterion 4: Not already classified
    if (excluded_faces_.count(pair.face1_id) || excluded_faces_.count(pair.face2_id)) {
        return false;
    }

    return true;
}

// ========================================================================================
// Phase 4: Subtype Classification
// ========================================================================================

std::string ThinWallRecognizer::ClassifyThinWallSubtype(const std::vector<int>& face_ids) {
    // Gather geometric statistics
    double total_area = 0.0;
    double planar_area = 0.0;
    double cylindrical_area = 0.0;
    int cylinder_count = 0;

    std::vector<gp_Ax1> cylinder_axes;
    std::vector<double> cylinder_radii;

    Bnd_Box combined_bbox;

    for (int face_id : face_ids) {
        const FaceAttributes& attr = aag_.GetFaceAttributes(face_id);
        total_area += attr.area;

        if (attr.is_planar) {
            planar_area += attr.area;
        }

        if (attr.is_cylinder) {
            cylindrical_area += attr.area;
            cylinder_axes.push_back(attr.cylinder_axis);
            cylinder_radii.push_back(attr.cylinder_radius);
            cylinder_count++;
        }

        Bnd_Box face_bbox = ComputeFaceBoundingBox(face_id);
        combined_bbox.Add(face_bbox);
    }

    // Compute bounding box dimensions
    double xmin, ymin, zmin, xmax, ymax, zmax;
    combined_bbox.Get(xmin, ymin, zmin, xmax, ymax, zmax);

    double dx = xmax - xmin;
    double dy = ymax - ymin;
    double dz = zmax - zmin;

    double length = std::max({dx, dy, dz});
    double width = std::min({dx, dy, dz});
    double aspect_ratio = (width > 0.01) ? (length / width) : 1.0;

    // Decision tree for subtype classification

    // 1. CONCENTRIC: Cylindrical faces with parallel/coincident axes
    if (cylinder_count >= 2) {
        for (size_t i = 0; i < cylinder_axes.size(); i++) {
            for (size_t j = i + 1; j < cylinder_axes.size(); j++) {
                if (AreAxesCoincident(cylinder_axes[i], cylinder_axes[j])) {
                    double radial_diff = std::abs(cylinder_radii[i] - cylinder_radii[j]);
                    if (radial_diff < threshold_ * 2.0) {
                        return "concentric";
                    }
                }
            }
        }
    }

    // 2. SHEET: Large, flat, low aspect ratio
    double planar_ratio = (total_area > 0.0) ? (planar_area / total_area) : 0.0;
    if (planar_ratio > 0.80 && total_area > 500.0 && aspect_ratio < 5.0) {
        return "sheet";
    }

    // 3. WEB: High aspect ratio, planar ribs
    if (planar_ratio > 0.60 && aspect_ratio > 5.0) {
        return "web";
    }

    // 4. SHELL: Curved surfaces
    double curved_ratio = (total_area > 0.0) ? (cylindrical_area / total_area) : 0.0;
    if (curved_ratio > 0.50 || cylinder_count > 0) {
        return "shell";
    }

    // Default: sheet (most conservative)
    return "sheet";
}

// ========================================================================================
// Helper Methods
// ========================================================================================

Bnd_Box ThinWallRecognizer::ComputeFaceBoundingBox(int face_id) {
    const TopoDS_Face& face = aag_.GetFace(face_id);

    Bnd_Box bbox;
    BRepBndLib::Add(face, bbox);

    return bbox;
}

gp_Pnt ThinWallRecognizer::ComputeFaceCentroid(int face_id) {
    const TopoDS_Face& face = aag_.GetFace(face_id);

    GProp_GProps props;
    BRepGProp::SurfaceProperties(face, props);

    return props.CentreOfMass();
}

gp_Vec ThinWallRecognizer::ComputeAverageFaceNormal(int face_id) {
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

double ThinWallRecognizer::BBoxDistance(const Bnd_Box& box1, const Bnd_Box& box2) {
    if (box1.IsVoid() || box2.IsVoid()) {
        return DBL_MAX;
    }

    return box1.Distance(box2);
}

bool ThinWallRecognizer::AreAxesParallel(const gp_Ax1& axis1, const gp_Ax1& axis2, double tolerance) {
    gp_Dir dir1 = axis1.Direction();
    gp_Dir dir2 = axis2.Direction();

    double dot = std::abs(dir1.Dot(dir2));

    // Parallel if dot product close to 1 (angle close to 0° or 180°)
    return dot > (1.0 - tolerance);
}

bool ThinWallRecognizer::AreAxesCoincident(const gp_Ax1& axis1, const gp_Ax1& axis2) {
    // Check if axes are parallel
    if (!AreAxesParallel(axis1, axis2)) {
        return false;
    }

    // Check if axes pass through nearly the same point
    gp_Pnt p1 = axis1.Location();
    gp_Pnt p2 = axis2.Location();

    // Project p2 onto axis1
    gp_Vec v = gp_Vec(p1, p2);
    gp_Dir d1 = axis1.Direction();

    double projection = v.Dot(gp_Vec(d1));
    gp_Pnt projected = p1.Translated(gp_Vec(d1).Multiplied(projection));

    double distance = projected.Distance(p2);

    // Axes are coincident if perpendicular distance is small
    return distance < 1.0;  // 1mm tolerance
}

// ========================================================================================
// Feature Creation
// ========================================================================================

Feature ThinWallRecognizer::CreateThinWallFeature(const std::vector<int>& face_ids,
                                                  const ThicknessMeasurement& measurement,
                                                  const std::string& subtype) {
    Feature feature;

    // Generate unique ID
    std::ostringstream oss;
    oss << "thin_wall_" << std::setfill('0') << std::setw(4) << feature_id_counter_++;
    feature.id = oss.str();

    // Set metadata
    feature.type = "thin_wall";
    feature.subtype = subtype;
    feature.source = "thin_wall_recognizer";

    // Compute confidence based on measurement quality
    double confidence = 1.0;

    // Reduce for high variance
    if (measurement.avg_thickness > 0.0) {
        double cv = std::sqrt(measurement.variance) / measurement.avg_thickness;
        confidence -= cv * 0.5;
    }

    // Reduce for low overlap
    confidence -= (1.0 - measurement.overlap_ratio) * 0.2;

    // Reduce for sparse sampling
    if (measurement.sample_points.size() < 10) {
        confidence -= 0.1;
    }

    feature.confidence = std::max(0.5, std::min(1.0, confidence));

    // Add face IDs
    feature.face_ids = face_ids;

    // Geometric parameters
    feature.params["avg_thickness"] = measurement.avg_thickness;
    feature.params["min_thickness"] = measurement.min_thickness;
    feature.params["max_thickness"] = measurement.max_thickness;
    feature.params["variance"] = measurement.variance;
    feature.params["overlap_ratio"] = measurement.overlap_ratio;

    // Compute total area
    double total_area = 0.0;
    for (int face_id : face_ids) {
        total_area += aag_.GetFaceAttributes(face_id).area;
    }
    feature.params["total_area"] = total_area;

    // Compute aspect ratio from bounding box
    Bnd_Box combined_bbox;
    for (int face_id : face_ids) {
        combined_bbox.Add(ComputeFaceBoundingBox(face_id));
    }

    if (!combined_bbox.IsVoid()) {
        double xmin, ymin, zmin, xmax, ymax, zmax;
        combined_bbox.Get(xmin, ymin, zmin, xmax, ymax, zmax);

        double length = std::max({xmax - xmin, ymax - ymin, zmax - zmin});
        double width = std::min({xmax - xmin, ymax - ymin, zmax - zmin});

        feature.params["length"] = length;
        feature.params["width"] = width;

        if (width > 0.01) {
            feature.params["aspect_ratio"] = length / width;
        }
    }

    return feature;
}

} // namespace palmetto
