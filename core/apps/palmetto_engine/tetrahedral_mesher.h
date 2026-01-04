/**
 * Tetrahedral Mesh Generation using TetGen
 *
 * Generates volumetric tetrahedral meshes from CAD geometry for
 * dense thickness analysis and finite element applications.
 */

#pragma once

#include <TopoDS_Shape.hxx>
#include <vector>
#include <string>

// Forward declaration from TetGen library
class tetgenio;

namespace palmetto {

/**
 * Tetrahedral mesh node with thickness value
 */
struct TetNode {
    int id;
    double x, y, z;
    double thickness;      // Computed thickness at this node (-1 if unmeasured)
    bool is_boundary;      // True if node is on surface boundary
};

/**
 * Tetrahedral element (4 nodes)
 */
struct TetElement {
    int id;
    int node_ids[4];       // Indices into node array
};

/**
 * Complete tetrahedral mesh
 */
struct TetMesh {
    std::vector<TetNode> nodes;
    std::vector<TetElement> elements;
    int boundary_node_count;
    int interior_node_count;

    // Bounding box for slicing
    double min_x, max_x;
    double min_y, max_y;
    double min_z, max_z;
};

/**
 * Tetrahedral mesher using TetGen
 */
class TetrahedralMesher {
public:
    TetrahedralMesher();
    ~TetrahedralMesher();

    /**
     * Generate tetrahedral mesh from OCCT shape
     * @param shape Input CAD shape
     * @param surface_mesh_quality Quality parameter for surface mesh (0.01-1.0)
     * @param tet_quality_ratio Max radius-to-edge ratio (1.2-2.0, lower = better quality)
     * @return TetMesh structure
     */
    TetMesh GenerateTetMesh(
        const TopoDS_Shape& shape,
        double surface_mesh_quality = 0.05,
        double tet_quality_ratio = 1.4
    );

    /**
     * Export tet mesh to custom JSON format for web rendering
     * @param mesh Tetrahedral mesh
     * @param output_path Output .json file path
     * @return true if successful
     */
    bool ExportToJSON(const TetMesh& mesh, const std::string& output_path);

private:
    /**
     * Convert OCCT surface triangulation to TetGen input
     */
    void OCCTToTetGenInput(const TopoDS_Shape& shape, double quality, tetgenio& input);

    /**
     * Extract tet mesh from TetGen output
     */
    TetMesh TetGenOutputToTetMesh(const tetgenio& output);
};

} // namespace palmetto
