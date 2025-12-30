/**
 * AAG Implementation
 */

#include "aag.h"

#include <iostream>
#include <cmath>

// OpenCASCADE includes
#include <TopExp.hxx>
#include <TopExp_Explorer.hxx>
#include <TopoDS.hxx>
#include <BRep_Tool.hxx>
#include <BRepAdaptor_Surface.hxx>
#include <BRepAdaptor_Curve.hxx>
#include <BRepLProp_SLProps.hxx>
#include <GeomAbs_SurfaceType.hxx>
#include <GeomAbs_CurveType.hxx>
#include <GProp_GProps.hxx>
#include <BRepGProp.hxx>
#include <TopTools_IndexedDataMapOfShapeListOfShape.hxx>
#include <Geom_Surface.hxx>
#include <Geom_Plane.hxx>
#include <GeomAPI_ProjectPointOnSurf.hxx>
#include <GeomLProp_SLProps.hxx>
#include <TopAbs_Orientation.hxx>
#include <gp_Pln.hxx>
#include <gp_Cylinder.hxx>
#include <gp_Torus.hxx>

namespace palmetto {

AAG::AAG() {
}

AAG::~AAG() {
}

bool AAG::Build(const TopoDS_Shape& shape) {
    std::cout << "Building AAG..." << std::endl;

    // Build face index
    BuildFaceIndex(shape);
    std::cout << "  Indexed " << faces_.size() << " faces" << std::endl;

    // Compute face attributes
    ComputeFaceAttributes();
    std::cout << "  Computed face attributes" << std::endl;

    // Build adjacency
    BuildAdjacency(shape);
    std::cout << "  Built adjacency graph with " << edges_.size() << " edges" << std::endl;

    return true;
}

void AAG::BuildFaceIndex(const TopoDS_Shape& shape) {
    faces_.clear();

    for (TopExp_Explorer exp(shape, TopAbs_FACE); exp.More(); exp.Next()) {
        TopoDS_Face face = TopoDS::Face(exp.Current());
        faces_.push_back(face);
    }

    face_attrs_.resize(faces_.size());
}

void AAG::ComputeFaceAttributes() {
    for (size_t i = 0; i < faces_.size(); i++) {
        const TopoDS_Face& face = faces_[i];
        FaceAttributes& attrs = face_attrs_[i];

        // Compute area
        GProp_GProps props;
        BRepGProp::SurfaceProperties(face, props);
        attrs.area = props.Mass();

        // Analyze surface
        BRepAdaptor_Surface surface(face);

        // Get surface type
        GeomAbs_SurfaceType surf_type = surface.GetType();

        switch (surf_type) {
            case GeomAbs_Plane:
                attrs.surface_type = SurfaceType::PLANE;
                attrs.is_planar = true;
                {
                    gp_Pln plane = surface.Plane();
                    attrs.plane_location = plane.Location();
                    attrs.plane_normal = gp_Vec(plane.Axis().Direction());
                }
                break;

            case GeomAbs_Cylinder:
                attrs.surface_type = SurfaceType::CYLINDER;
                attrs.is_cylinder = true;
                {
                    gp_Cylinder cyl = surface.Cylinder();
                    attrs.cylinder_axis = cyl.Axis();
                    attrs.cylinder_radius = cyl.Radius();
                }
                break;

            case GeomAbs_Cone:
                attrs.surface_type = SurfaceType::CONE;
                break;

            case GeomAbs_Sphere:
                attrs.surface_type = SurfaceType::SPHERE;
                break;

            case GeomAbs_Torus:
                attrs.surface_type = SurfaceType::TORUS;
                attrs.is_torus = true;
                {
                    gp_Torus torus = surface.Torus();
                    attrs.torus_axis = torus.Axis();
                    attrs.torus_minor_radius = torus.MinorRadius();  // Fillet radius
                    attrs.torus_major_radius = torus.MajorRadius();  // Distance to tube center
                }
                break;

            case GeomAbs_BSplineSurface:
                attrs.surface_type = SurfaceType::BSPLINE;
                break;

            default:
                attrs.surface_type = SurfaceType::OTHER;
                break;
        }

        // Compute normal at center
        double u = (surface.FirstUParameter() + surface.LastUParameter()) / 2.0;
        double v = (surface.FirstVParameter() + surface.LastVParameter()) / 2.0;

        BRepLProp_SLProps props_normal(surface, u, v, 1, 1e-6);
        if (props_normal.IsNormalDefined()) {
            gp_Dir normal_dir = props_normal.Normal();

            // Account for face orientation
            if (face.Orientation() == TopAbs_REVERSED) {
                normal_dir.Reverse();
            }

            attrs.normal = gp_Vec(normal_dir);
        }
    }
}

void AAG::BuildAdjacency(const TopoDS_Shape& shape) {
    edges_.clear();
    edge_index_.clear();

    // Build edge-to-face map
    TopTools_IndexedDataMapOfShapeListOfShape edgeMap;
    TopExp::MapShapesAndAncestors(shape, TopAbs_EDGE, TopAbs_FACE, edgeMap);

    // For each edge, find adjacent faces
    for (int i = 1; i <= edgeMap.Extent(); i++) {
        const TopoDS_Edge& edge = TopoDS::Edge(edgeMap.FindKey(i));
        const TopTools_ListOfShape& faces = edgeMap.FindFromIndex(i);

        if (faces.Extent() == 2) {
            // This edge connects two faces
            TopTools_ListIteratorOfListOfShape it(faces);
            TopoDS_Face face1 = TopoDS::Face(it.Value());
            it.Next();
            TopoDS_Face face2 = TopoDS::Face(it.Value());

            // Find face IDs
            int face1_id = -1, face2_id = -1;
            for (size_t j = 0; j < faces_.size(); j++) {
                if (faces_[j].IsSame(face1)) face1_id = j;
                if (faces_[j].IsSame(face2)) face2_id = j;
            }

            if (face1_id >= 0 && face2_id >= 0) {
                // Compute dihedral angle
                double angle = ComputeDihedralAngle(face1_id, face2_id, edge);

                // Create edge
                AAGEdge aag_edge;
                aag_edge.face1_id = face1_id;
                aag_edge.face2_id = face2_id;
                aag_edge.edge = edge;
                aag_edge.dihedral_angle = angle;

                // Classify angle
                double abs_angle = std::abs(angle);
                if (abs_angle > 177.0) {
                    aag_edge.is_smooth = true;
                } else if (angle < 0) {
                    aag_edge.is_convex = true;
                } else {
                    aag_edge.is_concave = true;
                }

                // Store edge
                int edge_idx = edges_.size();
                edges_.push_back(aag_edge);
                edge_index_[std::make_pair(face1_id, face2_id)] = edge_idx;
                edge_index_[std::make_pair(face2_id, face1_id)] = edge_idx;
            }
        }
    }
}

double AAG::ComputeDihedralAngle(int face1_id, int face2_id, const TopoDS_Edge& edge) {
    const TopoDS_Face& face1 = faces_[face1_id];
    const TopoDS_Face& face2 = faces_[face2_id];

    try {
        // Get edge curve
        BRepAdaptor_Curve curve(edge);
        double first = curve.FirstParameter();
        double last = curve.LastParameter();
        double mid = (first + last) / 2.0;

        // Get two points along edge for reference
        double step = (last - first) * 0.01;
        gp_Pnt A = curve.Value(mid - step);
        gp_Pnt B = curve.Value(mid + step);

        // Edge direction vector
        gp_Vec Vx(A, B);
        if (Vx.Magnitude() < 1e-10) return 0.0;

        // Get normal for face1
        Handle(Geom_Surface) surf1 = BRep_Tool::Surface(face1);
        GeomAPI_ProjectPointOnSurf proj1(A, surf1);
        if (proj1.NbPoints() == 0) return 0.0;

        Standard_Real u1, v1;
        proj1.Parameters(1, u1, v1);

        GeomLProp_SLProps props1(surf1, u1, v1, 1, 1e-6);
        if (!props1.IsNormalDefined()) return 0.0;

        gp_Vec N1(props1.Normal());
        if (face1.Orientation() == TopAbs_REVERSED) N1.Reverse();

        // In-plane tangent for face1
        gp_Vec Vy1 = N1.Crossed(Vx);
        if (Vy1.Magnitude() < 1e-10) return 0.0;
        gp_Vec TF = Vy1.Normalized();

        // Reference direction
        gp_Vec Ref = Vx.Normalized();

        // Get normal for face2
        Handle(Geom_Surface) surf2 = BRep_Tool::Surface(face2);
        GeomAPI_ProjectPointOnSurf proj2(A, surf2);
        if (proj2.NbPoints() == 0) return 0.0;

        Standard_Real u2, v2;
        proj2.Parameters(1, u2, v2);

        GeomLProp_SLProps props2(surf2, u2, v2, 1, 1e-6);
        if (!props2.IsNormalDefined()) return 0.0;

        gp_Vec N2(props2.Normal());
        if (face2.Orientation() == TopAbs_REVERSED) N2.Reverse();

        // In-plane tangent for face2
        gp_Vec Vy2 = N2.Crossed(Vx);
        if (Vy2.Magnitude() < 1e-10) return 0.0;
        gp_Vec TG = Vy2.Normalized();

        // Compute signed angle
        double angle_rad = TF.AngleWithRef(TG, Ref);
        double angle_deg = angle_rad * 180.0 / M_PI;

        return angle_deg;

    } catch (...) {
        return 0.0;
    }
}

std::vector<int> AAG::GetNeighbors(int face_id) const {
    std::vector<int> neighbors;

    for (const auto& edge : edges_) {
        if (edge.face1_id == face_id) {
            neighbors.push_back(edge.face2_id);
        } else if (edge.face2_id == face_id) {
            neighbors.push_back(edge.face1_id);
        }
    }

    return neighbors;
}

const AAGEdge* AAG::GetEdge(int face1_id, int face2_id) const {
    auto it = edge_index_.find(std::make_pair(face1_id, face2_id));
    if (it != edge_index_.end()) {
        return &edges_[it->second];
    }
    return nullptr;
}

double AAG::GetDihedralAngle(int face1_id, int face2_id) const {
    const AAGEdge* edge = GetEdge(face1_id, face2_id);
    return edge ? edge->dihedral_angle : 0.0;
}

std::vector<int> AAG::GetCylindricalFaces() const {
    std::vector<int> result;

    for (size_t i = 0; i < faces_.size(); i++) {
        if (face_attrs_[i].is_cylinder) {
            result.push_back(i);
        }
    }

    return result;
}

std::vector<int> AAG::GetToroidalFaces() const {
    std::vector<int> result;

    for (size_t i = 0; i < faces_.size(); i++) {
        if (face_attrs_[i].is_torus) {
            result.push_back(i);
        }
    }

    return result;
}

} // namespace palmetto
