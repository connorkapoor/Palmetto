/**
 * Simplified Attributed Adjacency Graph (AAG) implementation
 * Based on Analysis Situs asiAlgo_AAG
 */

#pragma once

#include <map>
#include <set>
#include <vector>
#include <memory>

// OpenCASCADE includes
#include <TopoDS_Shape.hxx>
#include <TopoDS_Face.hxx>
#include <TopoDS_Edge.hxx>
#include <gp_Pnt.hxx>
#include <gp_Vec.hxx>
#include <gp_Ax1.hxx>

namespace palmetto {

/**
 * Surface types for face classification
 */
enum class SurfaceType {
    PLANE,
    CYLINDER,
    CONE,
    SPHERE,
    TORUS,
    BSPLINE,
    OTHER
};

/**
 * Face attributes in the AAG
 */
struct FaceAttributes {
    SurfaceType surface_type;
    double area;
    gp_Vec normal;

    // For cylindrical faces
    bool is_cylinder;
    gp_Ax1 cylinder_axis;
    double cylinder_radius;

    // For toroidal faces
    bool is_torus;
    gp_Ax1 torus_axis;
    double torus_minor_radius;  // Fillet radius
    double torus_major_radius;  // Distance from axis to center of tube

    // For planar faces
    bool is_planar;
    gp_Pnt plane_location;
    gp_Vec plane_normal;

    FaceAttributes()
        : surface_type(SurfaceType::OTHER)
        , area(0.0)
        , is_cylinder(false)
        , cylinder_radius(0.0)
        , is_torus(false)
        , torus_minor_radius(0.0)
        , torus_major_radius(0.0)
        , is_planar(false)
    {}
};

/**
 * Edge between two faces with dihedral angle
 */
struct AAGEdge {
    int face1_id;
    int face2_id;
    TopoDS_Edge edge;
    double dihedral_angle;  // Signed angle in degrees [-180, 180]
    bool is_convex;         // angle < 0
    bool is_concave;        // angle > 0
    bool is_smooth;         // |angle| ≈ 180°

    AAGEdge()
        : face1_id(-1)
        , face2_id(-1)
        , dihedral_angle(0.0)
        , is_convex(false)
        , is_concave(false)
        , is_smooth(false)
    {}
};

/**
 * Attributed Adjacency Graph
 *
 * Simplified implementation of Analysis Situs AAG for feature recognition
 */
class AAG {
public:
    AAG();
    ~AAG();

    /**
     * Build AAG from shape
     */
    bool Build(const TopoDS_Shape& shape);

    /**
     * Get face count
     */
    int GetFaceCount() const { return static_cast<int>(faces_.size()); }

    /**
     * Get face by ID
     */
    const TopoDS_Face& GetFace(int id) const { return faces_[id]; }

    /**
     * Get face attributes
     */
    const FaceAttributes& GetFaceAttributes(int id) const { return face_attrs_[id]; }

    /**
     * Get neighbors of a face
     */
    std::vector<int> GetNeighbors(int face_id) const;

    /**
     * Get edge between two faces
     */
    const AAGEdge* GetEdge(int face1_id, int face2_id) const;

    /**
     * Get dihedral angle between two faces
     */
    double GetDihedralAngle(int face1_id, int face2_id) const;

    /**
     * Get all cylindrical faces
     */
    std::vector<int> GetCylindricalFaces() const;

    /**
     * Get all toroidal faces
     */
    std::vector<int> GetToroidalFaces() const;

    /**
     * Get all edges in the AAG
     */
    const std::vector<AAGEdge>& GetEdges() const { return edges_; }

    /**
     * Get edge count
     */
    int GetEdgeCount() const { return static_cast<int>(edges_.size()); }

private:
    // Build face index
    void BuildFaceIndex(const TopoDS_Shape& shape);

    // Compute face attributes
    void ComputeFaceAttributes();

    // Build adjacency graph
    void BuildAdjacency(const TopoDS_Shape& shape);

    // Compute dihedral angle between two faces
    double ComputeDihedralAngle(int face1_id, int face2_id, const TopoDS_Edge& edge);

    // Check if face is cylindrical
    bool IsCylindrical(int face_id, gp_Ax1& axis, double& radius);

    // Data members
    std::vector<TopoDS_Face> faces_;
    std::vector<FaceAttributes> face_attrs_;
    std::vector<AAGEdge> edges_;
    std::map<std::pair<int, int>, int> edge_index_;  // (face1, face2) -> edge index
};

} // namespace palmetto
