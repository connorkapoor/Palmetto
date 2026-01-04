/**
 * JSON Exporter Implementation
 */

#include "json_exporter.h"
#include "blend_recognizer.h"

#include <fstream>
#include <sstream>
#include <iomanip>
#include <iostream>
#include <cmath>

// Define M_PI if not already defined
#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

// For UUID generation (simplified)
#include <random>

// OpenCASCADE topology exploration
#include <TopExp_Explorer.hxx>
#include <TopoDS.hxx>
#include <TopoDS_Vertex.hxx>
#include <TopoDS_Edge.hxx>
#include <TopoDS_Shell.hxx>
#include <TopExp.hxx>
#include <TopTools_IndexedMapOfShape.hxx>
#include <BRep_Tool.hxx>
#include <gp_Pnt.hxx>

// For curve discretization and surface analysis
#include <BRepAdaptor_Curve.hxx>
#include <BRepAdaptor_Surface.hxx>
#include <GCPnts_UniformAbscissa.hxx>
#include <GeomAdaptor_Curve.hxx>
#include <BRepGProp.hxx>
#include <GProp_GProps.hxx>
#include <Geom_Surface.hxx>
#include <gp_Circ.hxx>
#include <gp_Vec.hxx>
#include <gp_Cylinder.hxx>
#include <gp_Lin.hxx>

namespace palmetto {

JsonExporter::JsonExporter(const Engine& engine)
    : engine_(engine)
{
}

// Simple JSON escaping
std::string escape_json(const std::string& str) {
    std::ostringstream oss;
    for (char c : str) {
        switch (c) {
            case '"':  oss << "\\\""; break;
            case '\\': oss << "\\\\"; break;
            case '\n': oss << "\\n"; break;
            case '\r': oss << "\\r"; break;
            case '\t': oss << "\\t"; break;
            default: oss << c; break;
        }
    }
    return oss.str();
}

// Generate simple UUID
std::string generate_uuid() {
    std::random_device rd;
    std::mt19937 gen(rd());
    std::uniform_int_distribution<> dis(0, 15);
    std::uniform_int_distribution<> dis2(8, 11);

    std::ostringstream oss;
    oss << std::hex;
    for (int i = 0; i < 8; i++) oss << dis(gen);
    oss << "-";
    for (int i = 0; i < 4; i++) oss << dis(gen);
    oss << "-4";
    for (int i = 0; i < 3; i++) oss << dis(gen);
    oss << "-";
    oss << dis2(gen);
    for (int i = 0; i < 3; i++) oss << dis(gen);
    oss << "-";
    for (int i = 0; i < 12; i++) oss << dis(gen);

    return oss.str();
}

bool JsonExporter::export_features(const std::string& filepath) {
    std::ofstream out(filepath);
    if (!out.is_open()) {
        std::cerr << "ERROR: Failed to open " << filepath << "\n";
        return false;
    }

    out << "{\n";
    out << "  \"model_id\": \"" << generate_uuid() << "\",\n";
    out << "  \"units\": \"mm\",\n";
    out << "  \"features\": [\n";

    const auto& features = engine_.get_features();

    for (size_t i = 0; i < features.size(); ++i) {
        const Feature& feat = features[i];

        out << "    {\n";
        out << "      \"id\": \"" << escape_json(feat.id) << "\",\n";
        out << "      \"type\": \"" << escape_json(feat.type) << "\",\n";
        out << "      \"subtype\": \"" << escape_json(feat.subtype) << "\",\n";

        // Face IDs
        out << "      \"faces\": [";
        for (size_t j = 0; j < feat.face_ids.size(); ++j) {
            out << feat.face_ids[j];
            if (j < feat.face_ids.size() - 1) out << ", ";
        }
        out << "],\n";

        // Edge IDs
        out << "      \"edges\": [";
        for (size_t j = 0; j < feat.edge_ids.size(); ++j) {
            out << feat.edge_ids[j];
            if (j < feat.edge_ids.size() - 1) out << ", ";
        }
        out << "],\n";

        // Parameters
        out << "      \"params\": {";
        size_t param_idx = 0;
        for (const auto& [key, value] : feat.params) {
            out << "\"" << escape_json(key) << "\": " << value;
            if (param_idx < feat.params.size() - 1) out << ", ";
            param_idx++;
        }
        out << "},\n";

        out << "      \"source\": \"" << escape_json(feat.source) << "\",\n";
        out << "      \"confidence\": " << feat.confidence << "\n";
        out << "    }";

        if (i < features.size() - 1) out << ",";
        out << "\n";
    }

    out << "  ]\n";
    out << "}\n";

    out.close();

    std::cout << "  ✓ Exported " << features.size() << " features to " << filepath << "\n";

    return true;
}

bool JsonExporter::export_aag(const std::string& filepath) {
    std::ofstream out(filepath);
    if (!out.is_open()) {
        std::cerr << "ERROR: Failed to open " << filepath << "\n";
        return false;
    }

    AAG* aag = engine_.get_aag();
    if (!aag) {
        std::cerr << "ERROR: AAG not available\n";
        return false;
    }

    const TopoDS_Shape& shape = engine_.get_shape();

    // Build indexed maps for all topology types
    TopTools_IndexedMapOfShape vertexMap, edgeMap, faceMap, shellMap;
    TopExp::MapShapes(shape, TopAbs_VERTEX, vertexMap);
    TopExp::MapShapes(shape, TopAbs_EDGE, edgeMap);
    TopExp::MapShapes(shape, TopAbs_FACE, faceMap);
    TopExp::MapShapes(shape, TopAbs_SHELL, shellMap);

    // Perform blend chain recognition
    BlendRecognition::BlendRecognizer blendRecognizer(shape);
    blendRecognizer.Perform();
    const std::map<int, BlendRecognition::BlendCandidate>& blendCandidates = blendRecognizer.GetCandidates();
    const std::vector<BlendRecognition::BlendChain>& blendChains = blendRecognizer.GetChains();

    // Build set of cavity face IDs from recognized features
    std::set<int> cavityFaceIds;
    std::set<int> thinWallFaceIds;
    const auto& features = engine_.get_features();
    for (const Feature& feat : features) {
        if (feat.type == "cavity") {
            for (int face_id : feat.face_ids) {
                cavityFaceIds.insert(face_id);
            }
        }
        if (feat.type == "thin_wall") {
            for (int face_id : feat.face_ids) {
                thinWallFaceIds.insert(face_id);
            }
        }
    }

    // Get thickness analysis results
    const auto& thickness_results = engine_.get_thickness_results();

    out << "{\n";
    out << "  \"nodes\": [\n";

    bool first_node = true;

    // Export vertex nodes
    for (int i = 1; i <= vertexMap.Extent(); i++) {
        const TopoDS_Vertex& vertex = TopoDS::Vertex(vertexMap(i));
        gp_Pnt pnt = BRep_Tool::Pnt(vertex);

        if (!first_node) out << ",\n";
        first_node = false;

        out << "    {\n";
        out << "      \"id\": \"vertex_" << i << "\",\n";
        out << "      \"name\": \"V" << i << "\",\n";
        out << "      \"group\": \"vertex\",\n";
        out << "      \"color\": \"#4a90e2\",\n";
        out << "      \"val\": 3,\n";
        out << "      \"attributes\": {\n";
        out << "        \"x\": " << std::fixed << std::setprecision(2) << pnt.X() << ",\n";
        out << "        \"y\": " << pnt.Y() << ",\n";
        out << "        \"z\": " << pnt.Z() << "\n";
        out << "      }\n";
        out << "    }";
    }

    // Export edge nodes with curve type
    for (int i = 1; i <= edgeMap.Extent(); i++) {
        const TopoDS_Edge& edge = TopoDS::Edge(edgeMap(i));

        if (!first_node) out << ",\n";
        first_node = false;

        out << "    {\n";
        out << "      \"id\": \"edge_" << i << "\",\n";
        out << "      \"name\": \"E" << i << "\",\n";
        out << "      \"group\": \"edge\",\n";
        out << "      \"color\": \"#50c878\",\n";
        out << "      \"val\": 4,\n";
        out << "      \"attributes\": {\n";

        // Determine curve type
        try {
            BRepAdaptor_Curve curve(edge);
            GeomAbs_CurveType curveType = curve.GetType();

            GProp_GProps props;
            BRepGProp::LinearProperties(edge, props);
            double length = props.Mass();

            out << "        \"curve_type\": \"";
            switch (curveType) {
                case GeomAbs_Line:      out << "line"; break;
                case GeomAbs_Circle:    out << "circle"; break;
                case GeomAbs_Ellipse:   out << "ellipse"; break;
                case GeomAbs_Hyperbola: out << "hyperbola"; break;
                case GeomAbs_Parabola:  out << "parabola"; break;
                case GeomAbs_BezierCurve: out << "bezier"; break;
                case GeomAbs_BSplineCurve: out << "bspline"; break;
                default:                out << "other"; break;
            }
            out << "\",\n";
            out << "        \"length\": " << std::fixed << std::setprecision(2) << length;

            // For circles, distinguish between full circles and arcs
            if (curveType == GeomAbs_Circle) {
                gp_Circ circle = curve.Circle();
                double radius = circle.Radius();

                // Get parameter range
                double first_param = curve.FirstParameter();
                double last_param = curve.LastParameter();
                double param_range = last_param - first_param;

                // Calculate arc angle in degrees
                double arc_angle = param_range * 180.0 / M_PI;

                // Full circle has ~360 degrees (2*PI radians)
                bool is_full_circle = (fabs(param_range - 2.0 * M_PI) < 1e-6);
                bool is_arc = !is_full_circle;
                bool is_semicircle = (fabs(arc_angle - 180.0) < 1.0);
                bool is_quarter_circle = (fabs(arc_angle - 90.0) < 1.0);
                bool is_three_quarter_circle = (fabs(arc_angle - 270.0) < 1.0);

                out << ",\n        \"radius\": " << radius;
                out << ",\n        \"is_full_circle\": " << (is_full_circle ? "true" : "false");
                out << ",\n        \"is_arc\": " << (is_arc ? "true" : "false");

                if (is_arc) {
                    out << ",\n        \"arc_angle\": " << std::setprecision(1) << arc_angle;
                    out << ",\n        \"is_semicircle\": " << (is_semicircle ? "true" : "false");
                    out << ",\n        \"is_quarter_circle\": " << (is_quarter_circle ? "true" : "false");
                    out << ",\n        \"is_three_quarter_circle\": " << (is_three_quarter_circle ? "true" : "false");
                }

                // Get center point
                gp_Pnt center = circle.Location();
                out << ",\n        \"center\": ["
                    << std::setprecision(2) << center.X() << ", "
                    << center.Y() << ", " << center.Z() << "]";
            }

            // Get edge endpoints for all edge types
            try {
                TopoDS_Vertex V1, V2;
                TopExp::Vertices(edge, V1, V2);

                if (!V1.IsNull()) {
                    gp_Pnt p1 = BRep_Tool::Pnt(V1);
                    out << ",\n        \"start_point\": ["
                        << std::setprecision(2) << p1.X() << ", "
                        << p1.Y() << ", " << p1.Z() << "]";
                }

                if (!V2.IsNull()) {
                    gp_Pnt p2 = BRep_Tool::Pnt(V2);
                    out << ",\n        \"end_point\": ["
                        << std::setprecision(2) << p2.X() << ", "
                        << p2.Y() << ", " << p2.Z() << "]";
                }
            } catch (...) {
                // Endpoints extraction failed, skip
            }
        } catch (...) {
            out << "        \"curve_type\": \"unknown\"";
        }

        out << "\n";
        out << "      }\n";
        out << "    }";
    }

    // Export face nodes with normals
    int face_count = aag->GetFaceCount();
    for (int i = 0; i < face_count; i++) {
        const FaceAttributes& attrs = aag->GetFaceAttributes(i);
        const TopoDS_Face& face = TopoDS::Face(faceMap(i + 1));

        if (!first_node) out << ",\n";
        first_node = false;

        out << "    {\n";
        out << "      \"id\": \"face_" << i << "\",\n";
        out << "      \"name\": \"F" << i << "\",\n";
        out << "      \"group\": \"face\",\n";
        out << "      \"color\": \"#f5a623\",\n";
        out << "      \"val\": 5,\n";
        out << "      \"attributes\": {\n";
        out << "        \"area\": " << attrs.area << ",\n";
        out << "        \"surface_type\": \"";
        switch (attrs.surface_type) {
            case SurfaceType::PLANE:    out << "plane"; break;
            case SurfaceType::CYLINDER: out << "cylinder"; break;
            case SurfaceType::CONE:     out << "cone"; break;
            case SurfaceType::SPHERE:   out << "sphere"; break;
            case SurfaceType::TORUS:    out << "torus"; break;
            case SurfaceType::BSPLINE:  out << "bspline"; break;
            default:                    out << "other"; break;
        }
        out << "\"";

        // For cylinders, determine if internal (hole) or external (fillet/boss)
        // Uses Analysis Situs technique: move along normal and check distance to axis
        bool is_internal_cylinder = false;
        if (attrs.is_cylinder) {
            out << ",\n        \"radius\": " << attrs.cylinder_radius;

            try {
                BRepAdaptor_Surface surfAdaptor(face);

                // Get parameter range and midpoint
                Standard_Real uMin = surfAdaptor.FirstUParameter();
                Standard_Real uMax = surfAdaptor.LastUParameter();
                Standard_Real vMin = surfAdaptor.FirstVParameter();
                Standard_Real vMax = surfAdaptor.LastVParameter();
                Standard_Real uMid = (uMin + uMax) / 2.0;
                Standard_Real vMid = (vMin + vMax) / 2.0;

                // Get point and normal at center
                gp_Pnt pnt;
                gp_Vec du, dv;
                surfAdaptor.D1(uMid, vMid, pnt, du, dv);
                gp_Vec normal = du.Crossed(dv);

                if (normal.Magnitude() > 1e-7) {
                    normal.Normalize();

                    // Adjust for face orientation
                    if (face.Orientation() == TopAbs_REVERSED) {
                        normal.Reverse();
                    }

                    // Get cylinder axis
                    gp_Cylinder cyl = surfAdaptor.Cylinder();
                    gp_Ax1 axis = cyl.Axis();
                    gp_Lin axisLine(axis);

                    // Take probe point along normal (5% of diameter)
                    double diameter = 2.0 * attrs.cylinder_radius;
                    gp_Pnt probePoint = pnt.XYZ() + normal.XYZ() * diameter * 0.05;

                    // Compute distances to axis
                    double distAtSurface = axisLine.Distance(pnt);
                    double distAtProbe = axisLine.Distance(probePoint);

                    // If probe is closer to axis, it's internal (hole)
                    // If probe is farther from axis, it's external (fillet/boss)
                    is_internal_cylinder = (distAtProbe < distAtSurface);

                    out << ",\n        \"is_internal_cylinder\": " << (is_internal_cylinder ? "true" : "false");
                }
            } catch (...) {
                // If we can't determine, skip
            }
        }

        // Add face normal
        try {
            BRepAdaptor_Surface surfAdaptor(face);

            // Get parameter range
            Standard_Real uMin = surfAdaptor.FirstUParameter();
            Standard_Real uMax = surfAdaptor.LastUParameter();
            Standard_Real vMin = surfAdaptor.FirstVParameter();
            Standard_Real vMax = surfAdaptor.LastVParameter();
            Standard_Real uMid = (uMin + uMax) / 2.0;
            Standard_Real vMid = (vMin + vMax) / 2.0;

            // Get normal at center
            gp_Pnt pnt;
            gp_Vec du, dv;
            surfAdaptor.D1(uMid, vMid, pnt, du, dv);
            gp_Vec normal = du.Crossed(dv);

            if (normal.Magnitude() > 1e-7) {
                normal.Normalize();

                // Adjust for face orientation
                if (face.Orientation() == TopAbs_REVERSED) {
                    normal.Reverse();
                }

                out << ",\n        \"normal\": ["
                    << std::fixed << std::setprecision(4)
                    << normal.X() << ", " << normal.Y() << ", " << normal.Z() << "]";
            }
        } catch (...) {
            // Normal calculation failed, skip it
        }

        // Analyze edges of this face to help distinguish fillets from holes
        try {
            int edge_count = 0;
            int arc_edge_count = 0;
            int full_circle_edge_count = 0;
            int quarter_circle_count = 0;
            int semicircle_count = 0;

            // Iterate through edges of this face
            TopExp_Explorer edgeExp(face, TopAbs_EDGE);
            for (; edgeExp.More(); edgeExp.Next()) {
                const TopoDS_Edge& faceEdge = TopoDS::Edge(edgeExp.Current());
                edge_count++;

                try {
                    BRepAdaptor_Curve edgeCurve(faceEdge);
                    if (edgeCurve.GetType() == GeomAbs_Circle) {
                        double first_param = edgeCurve.FirstParameter();
                        double last_param = edgeCurve.LastParameter();
                        double param_range = last_param - first_param;
                        double arc_angle = param_range * 180.0 / M_PI;

                        bool is_full = (fabs(param_range - 2.0 * M_PI) < 1e-6);

                        if (is_full) {
                            full_circle_edge_count++;
                        } else {
                            arc_edge_count++;
                            if (fabs(arc_angle - 90.0) < 1.0) {
                                quarter_circle_count++;
                            } else if (fabs(arc_angle - 180.0) < 1.0) {
                                semicircle_count++;
                            }
                        }
                    }
                } catch (...) {
                    // Skip edges that can't be analyzed
                }
            }

            // Add edge statistics to help distinguish feature types
            out << ",\n        \"edge_count\": " << edge_count;
            out << ",\n        \"has_full_circle_edges\": " << (full_circle_edge_count > 0 ? "true" : "false");
            out << ",\n        \"has_arc_edges\": " << (arc_edge_count > 0 ? "true" : "false");

            if (arc_edge_count > 0) {
                out << ",\n        \"arc_edge_count\": " << arc_edge_count;
            }
            if (quarter_circle_count > 0) {
                out << ",\n        \"quarter_circle_edge_count\": " << quarter_circle_count;
            }
            if (semicircle_count > 0) {
                out << ",\n        \"semicircle_edge_count\": " << semicircle_count;
            }
        } catch (...) {
            // Edge analysis failed, skip
        }

        // Add cavity information if this face is part of a cavity
        if (cavityFaceIds.count(i) > 0) {
            out << ",\n        \"is_cavity_face\": true";
        }

        // Add thin wall information if this face is part of a thin wall
        if (thinWallFaceIds.count(i) > 0) {
            out << ",\n        \"is_thin_wall_face\": true";

            // Find feature details
            for (const Feature& feature : features) {
                if (feature.type == "thin_wall") {
                    auto it = std::find(feature.face_ids.begin(), feature.face_ids.end(), i);
                    if (it != feature.face_ids.end()) {
                        out << ",\n        \"thin_wall_id\": \"" << feature.id << "\"";
                        out << ",\n        \"thin_wall_subtype\": \"" << feature.subtype << "\"";
                        if (feature.params.count("avg_thickness") > 0) {
                            out << ",\n        \"wall_thickness\": " << feature.params.at("avg_thickness");
                        }
                        break;
                    }
                }
            }
        }

        // Add blend chain information if this face is a blend candidate
        int face_id_1based = i + 1;  // faceMap uses 1-based indexing
        auto blend_it = blendCandidates.find(face_id_1based);
        if (blend_it != blendCandidates.end()) {
            const BlendRecognition::BlendCandidate& candidate = blend_it->second;

            out << ",\n        \"is_blend_candidate\": true";
            out << ",\n        \"blend_chain_id\": " << candidate.chain_id;

            // Add vexity
            out << ",\n        \"blend_vexity\": \"";
            if (candidate.vexity == BlendRecognition::VEXITY_CONCAVE) {
                out << "concave";
            } else if (candidate.vexity == BlendRecognition::VEXITY_CONVEX) {
                out << "convex";
            } else {
                out << "uncertain";
            }
            out << "\"";

            // Add edge counts
            if (!candidate.smooth_edges.empty()) {
                out << ",\n        \"smooth_edge_count\": " << candidate.smooth_edges.size();
            }
            if (!candidate.spring_edges.empty()) {
                out << ",\n        \"spring_edge_count\": " << candidate.spring_edges.size();
            }
            if (!candidate.cross_edges.empty()) {
                out << ",\n        \"cross_edge_count\": " << candidate.cross_edges.size();
            }
            if (!candidate.term_edges.empty()) {
                out << ",\n        \"term_edge_count\": " << candidate.term_edges.size();
            }
        }

        // Add thickness data if available
        // Note: faceMap is 1-indexed, but thickness_results uses 0-indexed face IDs
        int face_id_0based = i;  // i already iterates from 0 to face_count-1
        auto thickness_it = thickness_results.find(face_id_0based);
        if (thickness_it != thickness_results.end()) {
            const ThicknessResult& result = thickness_it->second;
            if (result.has_measurement) {
                out << ",\n        \"local_thickness\": " << std::fixed << std::setprecision(3) << result.thickness;
            }
        }

        out << "\n";
        out << "      }\n";
        out << "    }";
    }

    // Export shell nodes
    for (int i = 1; i <= shellMap.Extent(); i++) {
        if (!first_node) out << ",\n";
        first_node = false;

        out << "    {\n";
        out << "      \"id\": \"shell_" << i << "\",\n";
        out << "      \"name\": \"S" << i << "\",\n";
        out << "      \"group\": \"shell\",\n";
        out << "      \"color\": \"#bd10e0\",\n";
        out << "      \"val\": 6,\n";
        out << "      \"attributes\": {\n";
        out << "        \"type\": \"shell\"\n";
        out << "      }\n";
        out << "    }";
    }

    out << "\n  ],\n";

    // Export topology links
    out << "  \"links\": [\n";

    bool first_link = true;

    // Build vertex-to-edge relationships
    TopTools_IndexedDataMapOfShapeListOfShape vertexEdgeMap;
    TopExp::MapShapesAndAncestors(shape, TopAbs_VERTEX, TopAbs_EDGE, vertexEdgeMap);

    // Vertex -> Edge links
    for (int vIdx = 1; vIdx <= vertexEdgeMap.Extent(); vIdx++) {
        const TopTools_ListOfShape& edges = vertexEdgeMap(vIdx);
        for (TopTools_ListIteratorOfListOfShape it(edges); it.More(); it.Next()) {
            int edgeIdx = edgeMap.FindIndex(it.Value());
            if (edgeIdx > 0) {
                if (!first_link) out << ",\n";
                first_link = false;

                out << "    {\n";
                out << "      \"source\": \"vertex_" << vIdx << "\",\n";
                out << "      \"target\": \"edge_" << edgeIdx << "\",\n";
                out << "      \"type\": \"vertex_edge\"\n";
                out << "    }";
            }
        }
    }

    // Build edge-to-face relationships
    TopTools_IndexedDataMapOfShapeListOfShape edgeFaceMap;
    TopExp::MapShapesAndAncestors(shape, TopAbs_EDGE, TopAbs_FACE, edgeFaceMap);

    // Edge -> Face links
    for (int eIdx = 1; eIdx <= edgeFaceMap.Extent(); eIdx++) {
        const TopTools_ListOfShape& faces = edgeFaceMap(eIdx);
        for (TopTools_ListIteratorOfListOfShape it(faces); it.More(); it.Next()) {
            int faceIdx = faceMap.FindIndex(it.Value());
            if (faceIdx > 0) {
                if (!first_link) out << ",\n";
                first_link = false;

                out << "    {\n";
                out << "      \"source\": \"edge_" << eIdx << "\",\n";
                out << "      \"target\": \"face_" << (faceIdx - 1) << "\",\n";  // AAG uses 0-based
                out << "      \"type\": \"edge_face\"\n";
                out << "    }";
            }
        }
    }

    // Face -> Face adjacency (original AAG edges)
    const auto& aag_edges = aag->GetEdges();
    for (size_t i = 0; i < aag_edges.size(); i++) {
        const AAGEdge& edge = aag_edges[i];

        if (!first_link) out << ",\n";
        first_link = false;

        out << "    {\n";
        out << "      \"source\": \"face_" << edge.face1_id << "\",\n";
        out << "      \"target\": \"face_" << edge.face2_id << "\",\n";
        out << "      \"type\": \"face_adjacency\",\n";
        out << "      \"dihedral_angle\": " << edge.dihedral_angle << ",\n";
        out << "      \"convex\": " << (edge.is_convex ? "true" : "false") << ",\n";
        out << "      \"concave\": " << (edge.is_concave ? "true" : "false") << ",\n";
        out << "      \"smooth\": " << (edge.is_smooth ? "true" : "false") << "\n";
        out << "    }";
    }

    // Build face-to-shell relationships
    TopTools_IndexedDataMapOfShapeListOfShape faceShellMap;
    TopExp::MapShapesAndAncestors(shape, TopAbs_FACE, TopAbs_SHELL, faceShellMap);

    // Face -> Shell links
    for (int fIdx = 1; fIdx <= faceShellMap.Extent(); fIdx++) {
        const TopTools_ListOfShape& shells = faceShellMap(fIdx);
        for (TopTools_ListIteratorOfListOfShape it(shells); it.More(); it.Next()) {
            int shellIdx = shellMap.FindIndex(it.Value());
            if (shellIdx > 0) {
                if (!first_link) out << ",\n";
                first_link = false;

                out << "    {\n";
                out << "      \"source\": \"face_" << (fIdx - 1) << "\",\n";  // AAG uses 0-based
                out << "      \"target\": \"shell_" << shellIdx << "\",\n";
                out << "      \"type\": \"face_shell\"\n";
                out << "    }";
            }
        }
    }

    out << "\n  ],\n";

    // Export blend chains
    out << "  \"blend_chains\": [\n";
    bool first_chain = true;
    for (const BlendRecognition::BlendChain& chain : blendChains) {
        if (!first_chain) out << ",\n";
        first_chain = false;

        out << "    {\n";
        out << "      \"chain_id\": " << chain.chain_id << ",\n";
        out << "      \"vexity\": \"";
        if (chain.vexity == BlendRecognition::VEXITY_CONCAVE) {
            out << "concave";
        } else if (chain.vexity == BlendRecognition::VEXITY_CONVEX) {
            out << "convex";
        } else {
            out << "uncertain";
        }
        out << "\",\n";
        out << "      \"face_count\": " << chain.face_ids.size() << ",\n";
        out << "      \"max_radius\": " << chain.max_radius << ",\n";
        out << "      \"min_radius\": " << chain.min_radius << ",\n";
        out << "      \"face_ids\": [";
        for (size_t j = 0; j < chain.face_ids.size(); j++) {
            if (j > 0) out << ", ";
            out << "\"face_" << (chain.face_ids[j] - 1) << "\"";  // Convert to 0-based
        }
        out << "]\n";
        out << "    }";
    }
    out << "\n  ],\n";

    out << "  \"stats\": {\n";
    out << "    \"vertex\": " << vertexMap.Extent() << ",\n";
    out << "    \"edge\": " << edgeMap.Extent() << ",\n";
    out << "    \"face\": " << face_count << ",\n";
    out << "    \"shell\": " << shellMap.Extent() << ",\n";
    out << "    \"blend_chains\": " << blendChains.size() << "\n";
    out << "  }\n";
    out << "}\n";

    out.close();

    int total_nodes = vertexMap.Extent() + edgeMap.Extent() + face_count + shellMap.Extent();
    std::cout << "  ✓ Exported AAG to " << filepath << " (" << total_nodes << " nodes)\n";

    return true;
}

bool JsonExporter::export_topology_geometry(const std::string& filepath) {
    std::ofstream out(filepath);
    if (!out.is_open()) {
        std::cerr << "ERROR: Failed to open " << filepath << "\n";
        return false;
    }

    const TopoDS_Shape& shape = engine_.get_shape();

    // Build indexed maps
    TopTools_IndexedMapOfShape vertexMap, edgeMap;
    TopExp::MapShapes(shape, TopAbs_VERTEX, vertexMap);
    TopExp::MapShapes(shape, TopAbs_EDGE, edgeMap);

    out << "{\n";
    out << "  \"vertices\": [\n";

    // Export vertices with positions
    for (int i = 1; i <= vertexMap.Extent(); i++) {
        const TopoDS_Vertex& vertex = TopoDS::Vertex(vertexMap(i));
        gp_Pnt pnt = BRep_Tool::Pnt(vertex);

        out << "    {\n";
        out << "      \"id\": " << i << ",\n";
        out << "      \"position\": ["
            << std::fixed << std::setprecision(4)
            << pnt.X() << ", " << pnt.Y() << ", " << pnt.Z()
            << "]\n";
        out << "    }";

        if (i < vertexMap.Extent()) out << ",";
        out << "\n";
    }

    out << "  ],\n";
    out << "  \"edges\": [\n";

    // Export edges with discretized curve points
    for (int i = 1; i <= edgeMap.Extent(); i++) {
        const TopoDS_Edge& edge = TopoDS::Edge(edgeMap(i));

        // Get vertices of this edge
        TopoDS_Vertex v1, v2;
        TopExp::Vertices(edge, v1, v2);

        int v1_idx = vertexMap.FindIndex(v1);
        int v2_idx = vertexMap.FindIndex(v2);

        out << "    {\n";
        out << "      \"id\": " << i << ",\n";
        out << "      \"vertices\": [" << v1_idx << ", " << v2_idx << "],\n";

        // Discretize the edge curve into points
        out << "      \"points\": [";

        try {
            BRepAdaptor_Curve curve(edge);

            // Get edge length using GProp
            GProp_GProps props;
            BRepGProp::LinearProperties(edge, props);
            double length = props.Mass();

            // Sample points along the curve (approximately every 1mm or at least 10 points)
            int num_points = std::max(10, static_cast<int>(length / 1.0));
            num_points = std::min(num_points, 100); // Cap at 100 points per edge

            GCPnts_UniformAbscissa discretizer(curve, num_points);

            if (discretizer.IsDone()) {
                for (int j = 1; j <= discretizer.NbPoints(); j++) {
                    double param = discretizer.Parameter(j);
                    gp_Pnt pnt = curve.Value(param);

                    out << std::fixed << std::setprecision(4)
                        << "[" << pnt.X() << ", " << pnt.Y() << ", " << pnt.Z() << "]";

                    if (j < discretizer.NbPoints()) out << ", ";
                }
            } else {
                // Fallback: just use the two endpoint vertices
                gp_Pnt p1 = BRep_Tool::Pnt(v1);
                gp_Pnt p2 = BRep_Tool::Pnt(v2);

                out << std::fixed << std::setprecision(4)
                    << "[" << p1.X() << ", " << p1.Y() << ", " << p1.Z() << "], "
                    << "[" << p2.X() << ", " << p2.Y() << ", " << p2.Z() << "]";
            }
        } catch (...) {
            // Fallback: just use the two endpoint vertices
            gp_Pnt p1 = BRep_Tool::Pnt(v1);
            gp_Pnt p2 = BRep_Tool::Pnt(v2);

            out << std::fixed << std::setprecision(4)
                << "[" << p1.X() << ", " << p1.Y() << ", " << p1.Z() << "], "
                << "[" << p2.X() << ", " << p2.Y() << ", " << p2.Z() << "]";
        }

        out << "]\n";
        out << "    }";

        if (i < edgeMap.Extent()) out << ",";
        out << "\n";
    }

    out << "  ]\n";
    out << "}\n";

    out.close();

    std::cout << "  ✓ Exported topology geometry: "
              << vertexMap.Extent() << " vertices, "
              << edgeMap.Extent() << " edges\n";

    return true;
}

bool JsonExporter::export_metadata(const std::string& filepath, long processing_time_ms) {
    std::ofstream out(filepath);
    if (!out.is_open()) {
        std::cerr << "ERROR: Failed to open " << filepath << "\n";
        return false;
    }

    out << "{\n";
    out << "  \"counts\": {\n";
    out << "    \"faces\": " << engine_.get_face_count() << ",\n";
    out << "    \"edges\": " << engine_.get_edge_count() << ",\n";
    out << "    \"triangles\": " << engine_.get_triangle_count() << ",\n";
    out << "    \"features\": " << engine_.get_feature_count() << "\n";
    out << "  },\n";
    out << "  \"timings\": {\n";
    out << "    \"total_ms\": " << processing_time_ms << "\n";
    out << "  },\n";
    out << "  \"warnings\": [],\n";
    out << "  \"units\": \"mm\",\n";
    out << "  \"bbox\": {\n";
    out << "    \"min\": [0, 0, 0],\n";
    out << "    \"max\": [0, 0, 0]\n";
    out << "  }\n";
    out << "}\n";

    out.close();

    std::cout << "  ✓ Exported metadata to " << filepath << "\n";

    return true;
}

} // namespace palmetto
