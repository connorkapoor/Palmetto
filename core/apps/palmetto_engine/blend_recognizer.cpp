//-----------------------------------------------------------------------------
// Blend (Fillet/Round) Chain Recognition Implementation
//-----------------------------------------------------------------------------

#include "blend_recognizer.h"
#include <BRep_Tool.hxx>
#include <BRepAdaptor_Curve.hxx>
#include <BRepLProp_SLProps.hxx>
#include <GeomAbs_SurfaceType.hxx>
#include <Geom_CylindricalSurface.hxx>
#include <Geom_ToroidalSurface.hxx>
#include <Precision.hxx>
#include <TopExp_Explorer.hxx>
#include <TopoDS.hxx>
#include <gp_Lin.hxx>
#include <gp_Cylinder.hxx>
#include <gp_Torus.hxx>
#include <cmath>

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

namespace BlendRecognition {

BlendRecognizer::BlendRecognizer(const TopoDS_Shape& shape)
    : shape_(shape), next_chain_id_(0)
{
    // Build topology maps
    TopExp::MapShapes(shape_, TopAbs_FACE, faces_);
    TopExp::MapShapes(shape_, TopAbs_EDGE, edges_);
    TopExp::MapShapesAndAncestors(shape_, TopAbs_EDGE, TopAbs_FACE, edge_face_map_);
    TopExp::MapShapesAndAncestors(shape_, TopAbs_FACE, TopAbs_EDGE, face_edge_map_);
}

void BlendRecognizer::Perform()
{
    IdentifyCandidates();
    ClassifyEdges();
    DetermineVexity();
    BuildChains();
}

void BlendRecognizer::IdentifyCandidates()
{
    // Pass 1: Local recognition - identify cylindrical and toroidal faces
    for (int i = 1; i <= faces_.Extent(); i++) {
        const TopoDS_Face& face = TopoDS::Face(faces_(i));
        double radius = 0.0;
        
        if (IsCylindricalCandidate(face, radius) || IsToroidalCandidate(face, radius)) {
            BlendCandidate candidate;
            candidate.face_id = i;
            candidate.radius = radius;
            candidates_[i] = candidate;
        }
    }
}

bool BlendRecognizer::IsCylindricalCandidate(const TopoDS_Face& face, double& radius)
{
    try {
        BRepAdaptor_Surface surf(face);
        if (surf.GetType() == GeomAbs_Cylinder) {
            radius = surf.Cylinder().Radius();
            return true;
        }
    } catch (...) {}
    return false;
}

bool BlendRecognizer::IsToroidalCandidate(const TopoDS_Face& face, double& radius)
{
    try {
        BRepAdaptor_Surface surf(face);
        if (surf.GetType() == GeomAbs_Torus) {
            // Minor radius for torus
            radius = surf.Torus().MinorRadius();
            return true;
        }
    } catch (...) {}
    return false;
}

void BlendRecognizer::ClassifyEdges()
{
    // Pass 2: Classify edges based on tangency with adjacent faces
    for (auto& pair : candidates_) {
        int face_id = pair.first;
        BlendCandidate& candidate = pair.second;
        
        const TopoDS_Face& face = TopoDS::Face(faces_(face_id));
        
        // Get all edges of this face
        const TopTools_ListOfShape& edge_list = face_edge_map_.FindFromKey(face);
        
        for (TopTools_ListOfShape::Iterator it(edge_list); it.More(); it.Next()) {
            const TopoDS_Edge& edge = TopoDS::Edge(it.Value());
            int edge_id = edges_.FindIndex(edge);
            
            if (edge_id == 0) continue;
            
            // Get adjacent faces
            const TopTools_ListOfShape& adj_faces = edge_face_map_.FindFromKey(edge);
            
            if (adj_faces.Extent() != 2) {
                // Boundary edge - mark as terminating
                candidate.term_edges.insert(edge_id);
                continue;
            }
            
            // Get the two adjacent faces
            int face1_id = -1, face2_id = -1;
            for (TopTools_ListOfShape::Iterator fit(adj_faces); fit.More(); fit.Next()) {
                int fid = faces_.FindIndex(fit.Value());
                if (fid == face_id) continue;
                if (face1_id == -1) face1_id = fid;
                else face2_id = fid;
            }
            
            if (face1_id == -1) continue; // Only one adjacent face (shouldn't happen)
            
            int other_face_id = (face2_id == -1) ? face1_id : face2_id;
            
            // Check if the other face is also a blend candidate
            bool other_is_blend = (candidates_.find(other_face_id) != candidates_.end());
            
            if (other_is_blend && IsSmoothEdge(edge_id, face_id, other_face_id)) {
                // Smooth edge: connects two blend faces with tangent continuity
                candidate.smooth_edges.insert(edge_id);
            } else if (!other_is_blend && IsSpringEdge(edge_id, face_id, other_face_id)) {
                // Spring edge: tangent to blend, sharp to support
                candidate.spring_edges.insert(edge_id);
            } else if (!other_is_blend) {
                // Cross edge: sharp on both sides
                candidate.cross_edges.insert(edge_id);
            }
        }
    }
}

bool BlendRecognizer::IsSmoothEdge(int edge_id, int face1_id, int face2_id)
{
    // Two blend faces are smoothly connected if their normals are tangent
    try {
        const TopoDS_Face& face1 = TopoDS::Face(faces_(face1_id));
        const TopoDS_Face& face2 = TopoDS::Face(faces_(face2_id));
        const TopoDS_Edge& edge = TopoDS::Edge(edges_(edge_id));
        
        // Get mid-parameter on edge
        double first, last;
        Handle(Geom_Curve) curve = BRep_Tool::Curve(edge, first, last);
        if (curve.IsNull()) return false;
        
        double mid = (first + last) / 2.0;
        gp_Pnt pt = curve->Value(mid);
        
        // Get UV on both faces
        double u1, v1, u2, v2;
        BRepAdaptor_Surface surf1(face1);
        BRepAdaptor_Surface surf2(face2);
        
        // Simple approach: get normals at face centers (more robust than edge UV projection)
        double uMin1, uMax1, vMin1, vMax1;
        surf1.Surface().Surface()->Bounds(uMin1, uMax1, vMin1, vMax1);
        double uMid1 = (uMin1 + uMax1) / 2.0;
        double vMid1 = (vMin1 + vMax1) / 2.0;
        
        double uMin2, uMax2, vMin2, vMax2;
        surf2.Surface().Surface()->Bounds(uMin2, uMax2, vMin2, vMax2);
        double uMid2 = (uMin2 + uMax2) / 2.0;
        double vMid2 = (vMin2 + vMax2) / 2.0;
        
        gp_Pnt p1, p2;
        gp_Vec du1, dv1, du2, dv2;
        surf1.D1(uMid1, vMid1, p1, du1, dv1);
        surf2.D1(uMid2, vMid2, p2, du2, dv2);
        
        gp_Vec n1 = du1.Crossed(dv1);
        gp_Vec n2 = du2.Crossed(dv2);
        
        if (n1.Magnitude() < 1e-7 || n2.Magnitude() < 1e-7) return false;
        
        n1.Normalize();
        n2.Normalize();
        
        // Adjust for face orientation
        if (face1.Orientation() == TopAbs_REVERSED) n1.Reverse();
        if (face2.Orientation() == TopAbs_REVERSED) n2.Reverse();
        
        return AreTangent(n1, n2, 0.087); // ~5 degrees tolerance
    } catch (...) {
        return false;
    }
}

bool BlendRecognizer::IsSpringEdge(int edge_id, int blend_face_id, int support_face_id)
{
    // Spring edge is tangent to blend but sharp to support
    // For simplicity, check dihedral angle
    double angle = ComputeDihedralAngle(edge_id, blend_face_id, support_face_id);
    
    // Spring edges typically have angles between 60-120 degrees (not sharp, not tangent)
    return (fabs(angle) > 30.0 && fabs(angle) < 150.0);
}

double BlendRecognizer::ComputeDihedralAngle(int edge_id, int face1_id, int face2_id)
{
    try {
        const TopoDS_Face& face1 = TopoDS::Face(faces_(face1_id));
        const TopoDS_Face& face2 = TopoDS::Face(faces_(face2_id));
        
        BRepAdaptor_Surface surf1(face1);
        BRepAdaptor_Surface surf2(face2);
        
        // Get normals at face centers
        double uMin1, uMax1, vMin1, vMax1;
        surf1.Surface().Surface()->Bounds(uMin1, uMax1, vMin1, vMax1);
        double uMid1 = (uMin1 + uMax1) / 2.0;
        double vMid1 = (vMin1 + vMax1) / 2.0;
        
        double uMin2, uMax2, vMin2, vMax2;
        surf2.Surface().Surface()->Bounds(uMin2, uMax2, vMin2, vMax2);
        double uMid2 = (uMin2 + uMax2) / 2.0;
        double vMid2 = (vMin2 + vMax2) / 2.0;
        
        gp_Pnt p1, p2;
        gp_Vec du1, dv1, du2, dv2;
        surf1.D1(uMid1, vMid1, p1, du1, dv1);
        surf2.D1(uMid2, vMid2, p2, du2, dv2);
        
        gp_Vec n1 = du1.Crossed(dv1);
        gp_Vec n2 = du2.Crossed(dv2);
        
        if (n1.Magnitude() < 1e-7 || n2.Magnitude() < 1e-7) return 180.0;
        
        n1.Normalize();
        n2.Normalize();
        
        if (face1.Orientation() == TopAbs_REVERSED) n1.Reverse();
        if (face2.Orientation() == TopAbs_REVERSED) n2.Reverse();
        
        double dot = n1.Dot(n2);
        dot = std::max(-1.0, std::min(1.0, dot)); // Clamp to [-1, 1]
        
        return acos(dot) * 180.0 / M_PI;
    } catch (...) {
        return 180.0;
    }
}

bool BlendRecognizer::AreTangent(const gp_Vec& normal1, const gp_Vec& normal2, double tolerance)
{
    double dot = fabs(normal1.Dot(normal2));
    // Tangent if normals are nearly parallel (dot product close to 1)
    return (dot > cos(tolerance));
}

void BlendRecognizer::DetermineVexity()
{
    // Pass 3: Determine if each blend is concave or convex
    for (auto& pair : candidates_) {
        pair.second.vexity = TestVexity(pair.first);
    }
}

BlendVexity BlendRecognizer::TestVexity(int face_id)
{
    const TopoDS_Face& face = TopoDS::Face(faces_(face_id));
    const BlendCandidate& candidate = candidates_[face_id];
    
    // Use the internal cylinder test (Analysis Situs approach)
    try {
        BRepAdaptor_Surface surf(face);
        
        if (surf.GetType() == GeomAbs_Cylinder) {
            // Get point and normal at center
            double uMin, uMax, vMin, vMax;
            surf.Surface().Surface()->Bounds(uMin, uMax, vMin, vMax);
            double uMid = (uMin + uMax) / 2.0;
            double vMid = (vMin + vMax) / 2.0;
            
            gp_Pnt pnt;
            gp_Vec du, dv;
            surf.D1(uMid, vMid, pnt, du, dv);
            gp_Vec normal = du.Crossed(dv);
            
            if (normal.Magnitude() > 1e-7) {
                normal.Normalize();
                if (face.Orientation() == TopAbs_REVERSED) normal.Reverse();
                
                gp_Cylinder cyl = surf.Cylinder();
                gp_Ax1 axis = cyl.Axis();
                gp_Lin axisLine(axis);
                
                double diameter = 2.0 * candidate.radius;
                gp_Pnt probePoint = pnt.XYZ() + normal.XYZ() * diameter * 0.05;
                
                double distAtSurface = axisLine.Distance(pnt);
                double distAtProbe = axisLine.Distance(probePoint);
                
                // If probe is closer to axis, it's internal (concave)
                bool isInternal = (distAtProbe < distAtSurface);
                return isInternal ? VEXITY_CONCAVE : VEXITY_CONVEX;
            }
        } else if (surf.GetType() == GeomAbs_Torus) {
            // For torus, reversed orientation indicates concave
            bool isInternal = (face.Orientation() == TopAbs_REVERSED);
            return isInternal ? VEXITY_CONCAVE : VEXITY_CONVEX;
        }
    } catch (...) {}
    
    return VEXITY_UNCERTAIN;
}

void BlendRecognizer::BuildChains()
{
    // Pass 4: Build chains by traversing smooth edges
    for (auto& pair : candidates_) {
        if (pair.second.chain_id != -1) continue; // Already in a chain
        
        int seed_face_id = pair.first;
        BuildChainFrom(seed_face_id, next_chain_id_);
        next_chain_id_++;
    }
}

void BlendRecognizer::BuildChainFrom(int seed_face_id, int chain_id)
{
    // BFS traversal through smooth edges
    std::set<int> visited;
    std::vector<int> queue;
    queue.push_back(seed_face_id);
    visited.insert(seed_face_id);
    
    BlendChain chain;
    chain.chain_id = chain_id;
    
    while (!queue.empty()) {
        int current_id = queue.back();
        queue.pop_back();
        
        BlendCandidate& candidate = candidates_[current_id];
        candidate.chain_id = chain_id;
        chain.face_ids.push_back(current_id);
        
        // Update chain properties
        chain.max_radius = std::max(chain.max_radius, candidate.radius);
        chain.min_radius = std::min(chain.min_radius, candidate.radius);
        if (candidate.vexity != VEXITY_UNCERTAIN) {
            chain.vexity = candidate.vexity; // Assume all in chain have same vexity
        }
        
        // Traverse smooth edges to find connected blend faces
        for (int edge_id : candidate.smooth_edges) {
            const TopoDS_Edge& edge = TopoDS::Edge(edges_(edge_id));
            const TopTools_ListOfShape& adj_faces = edge_face_map_.FindFromKey(edge);
            
            for (TopTools_ListOfShape::Iterator it(adj_faces); it.More(); it.Next()) {
                int adj_face_id = faces_.FindIndex(it.Value());
                
                if (adj_face_id == current_id) continue;
                if (visited.find(adj_face_id) != visited.end()) continue;
                if (candidates_.find(adj_face_id) == candidates_.end()) continue;
                
                visited.insert(adj_face_id);
                queue.push_back(adj_face_id);
            }
        }
    }
    
    chains_.push_back(chain);
}

} // namespace BlendRecognition
