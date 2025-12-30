//-----------------------------------------------------------------------------
// Blend (Fillet/Round) Chain Recognition
// Based on Analysis Situs approach
//-----------------------------------------------------------------------------

#ifndef blend_recognizer_h
#define blend_recognizer_h

#include <TopoDS_Face.hxx>
#include <TopoDS_Edge.hxx>
#include <TopTools_IndexedMapOfShape.hxx>
#include <TopTools_IndexedDataMapOfShapeListOfShape.hxx>
#include <gp_Pnt.hxx>
#include <gp_Vec.hxx>
#include <BRepAdaptor_Surface.hxx>
#include <TopExp.hxx>
#include <map>
#include <set>
#include <vector>

namespace BlendRecognition {

enum BlendVexity {
    VEXITY_UNCERTAIN = -1,
    VEXITY_CONCAVE = 0,
    VEXITY_CONVEX = 1
};

enum EdgeType {
    EDGE_UNKNOWN = 0,
    EDGE_SMOOTH = 1,    // Connects blend faces (tangent continuity)
    EDGE_SPRING = 2,    // Connects blend to support (tangent to blend, sharp to support)
    EDGE_CROSS = 3,     // Connects blend to support across the blend
    EDGE_TERM = 4       // Sharp terminating edge
};

struct BlendCandidate {
    int face_id;
    double radius;
    BlendVexity vexity;
    std::set<int> smooth_edges;
    std::set<int> spring_edges;
    std::set<int> cross_edges;
    std::set<int> term_edges;
    int chain_id;  // -1 if not in a chain
    
    BlendCandidate() : face_id(-1), radius(0.0), vexity(VEXITY_UNCERTAIN), chain_id(-1) {}
};

struct BlendChain {
    int chain_id;
    std::vector<int> face_ids;
    BlendVexity vexity;
    double max_radius;
    double min_radius;
    double length;
    
    BlendChain() : chain_id(-1), vexity(VEXITY_UNCERTAIN), max_radius(0.0), min_radius(1e10), length(0.0) {}
};

class BlendRecognizer {
public:
    BlendRecognizer(const TopoDS_Shape& shape);
    
    // Main recognition workflow
    void Perform();
    
    // Get results
    const std::map<int, BlendCandidate>& GetCandidates() const { return candidates_; }
    const std::vector<BlendChain>& GetChains() const { return chains_; }
    
private:
    // Pass 1: Local recognition - identify candidate faces
    void IdentifyCandidates();
    
    // Pass 2: Classify edges (smooth, spring, cross, terminating)
    void ClassifyEdges();
    
    // Pass 3: Determine vexity (concave/convex)
    void DetermineVexity();
    
    // Pass 4: Build chains
    void BuildChains();
    
    // Helper methods
    bool IsCylindricalCandidate(const TopoDS_Face& face, double& radius);
    bool IsToroidalCandidate(const TopoDS_Face& face, double& radius);
    BlendVexity TestVexity(int face_id);
    bool IsSmoothEdge(int edge_id, int face1_id, int face2_id);
    bool IsSpringEdge(int edge_id, int face1_id, int face2_id);
    double ComputeDihedralAngle(int edge_id, int face1_id, int face2_id);
    bool AreTangent(const gp_Vec& normal1, const gp_Vec& normal2, double tolerance = 0.017); // ~1 degree
    void BuildChainFrom(int seed_face_id, int chain_id);
    
private:
    TopoDS_Shape shape_;
    TopTools_IndexedMapOfShape faces_;
    TopTools_IndexedMapOfShape edges_;
    TopTools_IndexedDataMapOfShapeListOfShape face_edge_map_;
    TopTools_IndexedDataMapOfShapeListOfShape edge_face_map_;
    
    std::map<int, BlendCandidate> candidates_;  // face_id -> candidate
    std::vector<BlendChain> chains_;
    int next_chain_id_;
};

} // namespace BlendRecognition

#endif
