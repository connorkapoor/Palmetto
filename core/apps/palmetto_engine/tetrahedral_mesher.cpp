/**
 * Tetrahedral Mesh Generation using TetGen
 */

#include "tetrahedral_mesher.h"

// TetGen library
#define TETLIBRARY
#include "tetgen.h"

// OpenCASCADE for geometry processing
#include <TopoDS.hxx>
#include <TopoDS_Face.hxx>
#include <TopExp_Explorer.hxx>
#include <BRepMesh_IncrementalMesh.hxx>
#include <Poly_Triangulation.hxx>
#include <TopLoc_Location.hxx>
#include <BRep_Tool.hxx>
#include <gp_Pnt.hxx>

// Standard library
#include <iostream>
#include <fstream>
#include <sstream>
#include <algorithm>
#include <map>
#include <iomanip>
#include <cmath>
#include <limits>

namespace palmetto {

TetrahedralMesher::TetrahedralMesher() {
}

TetrahedralMesher::~TetrahedralMesher() {
}

void TetrahedralMesher::OCCTToTetGenInput(
    const TopoDS_Shape& shape,
    double quality,
    tetgenio& input
) {
    std::cout << "  Converting OCCT surface mesh to TetGen format..." << std::endl;

    // Tessellate the shape
    BRepMesh_IncrementalMesh mesher(shape, quality, Standard_False, 0.5, Standard_True);

    // Collect all triangles and vertices from all faces
    std::vector<gp_Pnt> vertices;
    std::vector<std::array<int, 3>> triangles;
    std::map<std::array<double, 3>, int> vertex_map;  // Deduplicate vertices

    int vertex_count = 0;

    for (TopExp_Explorer exp(shape, TopAbs_FACE); exp.More(); exp.Next()) {
        TopoDS_Face face = TopoDS::Face(exp.Current());
        TopLoc_Location loc;
        Handle(Poly_Triangulation) tri = BRep_Tool::Triangulation(face, loc);

        if (tri.IsNull()) {
            std::cerr << "WARNING: Face has no triangulation" << std::endl;
            continue;
        }

        // Get transformation
        gp_Trsf trsf = loc.Transformation();

        // Process vertices
        for (int i = 1; i <= tri->NbNodes(); i++) {
            gp_Pnt pnt = tri->Node(i).Transformed(trsf);

            // Deduplicate vertices (merge vertices within 1e-6 tolerance)
            std::array<double, 3> key = {
                std::round(pnt.X() * 1e6) / 1e6,
                std::round(pnt.Y() * 1e6) / 1e6,
                std::round(pnt.Z() * 1e6) / 1e6
            };

            if (vertex_map.find(key) == vertex_map.end()) {
                vertex_map[key] = vertex_count++;
                vertices.push_back(pnt);
            }
        }

        // Process triangles
        for (int i = 1; i <= tri->NbTriangles(); i++) {
            const Poly_Triangle& triangle = tri->Triangle(i);
            int n1, n2, n3;
            triangle.Get(n1, n2, n3);

            // Get actual vertex positions and map to global indices
            gp_Pnt p1 = tri->Node(n1).Transformed(trsf);
            gp_Pnt p2 = tri->Node(n2).Transformed(trsf);
            gp_Pnt p3 = tri->Node(n3).Transformed(trsf);

            auto round_pt = [](const gp_Pnt& p) -> std::array<double, 3> {
                return {
                    std::round(p.X() * 1e6) / 1e6,
                    std::round(p.Y() * 1e6) / 1e6,
                    std::round(p.Z() * 1e6) / 1e6
                };
            };

            int idx1 = vertex_map[round_pt(p1)];
            int idx2 = vertex_map[round_pt(p2)];
            int idx3 = vertex_map[round_pt(p3)];

            // Check for orientation (TetGen expects consistent winding)
            if (face.Orientation() == TopAbs_REVERSED) {
                std::swap(idx2, idx3);
            }

            triangles.push_back({idx1, idx2, idx3});
        }
    }

    std::cout << "    Collected " << vertices.size() << " unique vertices, "
              << triangles.size() << " triangles" << std::endl;

    // Populate TetGen input structure
    input.firstnumber = 0;  // Use 0-based indexing
    input.numberofpoints = vertices.size();
    input.pointlist = new REAL[input.numberofpoints * 3];

    for (size_t i = 0; i < vertices.size(); i++) {
        input.pointlist[i * 3 + 0] = vertices[i].X();
        input.pointlist[i * 3 + 1] = vertices[i].Y();
        input.pointlist[i * 3 + 2] = vertices[i].Z();
    }

    // Set up facets (triangles)
    input.numberoffacets = triangles.size();
    input.facetlist = new tetgenio::facet[input.numberoffacets];
    input.facetmarkerlist = new int[input.numberoffacets];

    for (size_t i = 0; i < triangles.size(); i++) {
        tetgenio::facet* f = &input.facetlist[i];
        f->numberofpolygons = 1;
        f->polygonlist = new tetgenio::polygon[1];
        f->numberofholes = 0;
        f->holelist = nullptr;

        tetgenio::polygon* p = &f->polygonlist[0];
        p->numberofvertices = 3;
        p->vertexlist = new int[3];
        p->vertexlist[0] = triangles[i][0];
        p->vertexlist[1] = triangles[i][1];
        p->vertexlist[2] = triangles[i][2];

        input.facetmarkerlist[i] = 1;  // Mark as boundary
    }

    std::cout << "    TetGen input prepared successfully" << std::endl;
}

TetMesh TetrahedralMesher::TetGenOutputToTetMesh(const tetgenio& output) {
    TetMesh mesh;

    // Extract nodes
    mesh.nodes.reserve(output.numberofpoints);
    for (int i = 0; i < output.numberofpoints; i++) {
        TetNode node;
        node.id = i;
        node.x = output.pointlist[i * 3 + 0];
        node.y = output.pointlist[i * 3 + 1];
        node.z = output.pointlist[i * 3 + 2];
        node.thickness = -1.0;  // Will be computed later
        node.is_boundary = false;  // Will be determined from facets

        mesh.nodes.push_back(node);
    }

    // Mark boundary nodes (nodes that appear in boundary facets)
    if (output.trifacelist != nullptr && output.numberoftrifaces > 0) {
        for (int i = 0; i < output.numberoftrifaces; i++) {
            int n1 = output.trifacelist[i * 3 + 0];
            int n2 = output.trifacelist[i * 3 + 1];
            int n3 = output.trifacelist[i * 3 + 2];

            if (n1 >= 0 && n1 < (int)mesh.nodes.size()) mesh.nodes[n1].is_boundary = true;
            if (n2 >= 0 && n2 < (int)mesh.nodes.size()) mesh.nodes[n2].is_boundary = true;
            if (n3 >= 0 && n3 < (int)mesh.nodes.size()) mesh.nodes[n3].is_boundary = true;
        }
    }

    // Count boundary vs interior nodes
    mesh.boundary_node_count = 0;
    mesh.interior_node_count = 0;
    for (const auto& node : mesh.nodes) {
        if (node.is_boundary) {
            mesh.boundary_node_count++;
        } else {
            mesh.interior_node_count++;
        }
    }

    // Extract tetrahedra
    mesh.elements.reserve(output.numberoftetrahedra);
    for (int i = 0; i < output.numberoftetrahedra; i++) {
        TetElement elem;
        elem.id = i;
        elem.node_ids[0] = output.tetrahedronlist[i * 4 + 0];
        elem.node_ids[1] = output.tetrahedronlist[i * 4 + 1];
        elem.node_ids[2] = output.tetrahedronlist[i * 4 + 2];
        elem.node_ids[3] = output.tetrahedronlist[i * 4 + 3];

        mesh.elements.push_back(elem);
    }

    // Compute bounding box
    mesh.min_x = mesh.min_y = mesh.min_z = std::numeric_limits<double>::max();
    mesh.max_x = mesh.max_y = mesh.max_z = std::numeric_limits<double>::lowest();

    for (const auto& node : mesh.nodes) {
        mesh.min_x = std::min(mesh.min_x, node.x);
        mesh.max_x = std::max(mesh.max_x, node.x);
        mesh.min_y = std::min(mesh.min_y, node.y);
        mesh.max_y = std::max(mesh.max_y, node.y);
        mesh.min_z = std::min(mesh.min_z, node.z);
        mesh.max_z = std::max(mesh.max_z, node.z);
    }

    std::cout << "    Extracted " << mesh.nodes.size() << " nodes ("
              << mesh.boundary_node_count << " boundary, "
              << mesh.interior_node_count << " interior), "
              << mesh.elements.size() << " tetrahedra" << std::endl;

    return mesh;
}

TetMesh TetrahedralMesher::GenerateTetMesh(
    const TopoDS_Shape& shape,
    double surface_mesh_quality,
    double tet_quality_ratio
) {
    std::cout << "Generating tetrahedral mesh (quality=" << tet_quality_ratio << ")..." << std::endl;

    // Prepare input
    tetgenio input, output;
    OCCTToTetGenInput(shape, surface_mesh_quality, input);

    // Build TetGen command string
    // p = tetrahedralize PSLG
    // q = quality constraint (radius-to-edge ratio)
    // a = maximum tetrahedron volume (optional, we omit for adaptive sizing)
    std::ostringstream cmd;
    cmd << "pq" << std::fixed << std::setprecision(1) << tet_quality_ratio;

    std::cout << "  Running TetGen with switches: " << cmd.str() << std::endl;

    try {
        // Call TetGen
        tetrahedralize(const_cast<char*>(cmd.str().c_str()), &input, &output);

        std::cout << "  ✓ TetGen completed successfully" << std::endl;

    } catch (const std::exception& e) {
        std::cerr << "ERROR: TetGen failed: " << e.what() << std::endl;
        return TetMesh();  // Return empty mesh
    } catch (...) {
        std::cerr << "ERROR: TetGen failed with unknown exception" << std::endl;
        return TetMesh();
    }

    // Extract mesh
    return TetGenOutputToTetMesh(output);
}

bool TetrahedralMesher::ExportToJSON(const TetMesh& mesh, const std::string& output_path) {
    std::cout << "  Exporting tet mesh to JSON..." << std::endl;

    std::ofstream out(output_path);
    if (!out.is_open()) {
        std::cerr << "ERROR: Could not open " << output_path << " for writing" << std::endl;
        return false;
    }

    // Compute thickness range
    double min_thickness = std::numeric_limits<double>::max();
    double max_thickness = std::numeric_limits<double>::lowest();

    for (const auto& node : mesh.nodes) {
        if (node.thickness > 0) {
            min_thickness = std::min(min_thickness, node.thickness);
            max_thickness = std::max(max_thickness, node.thickness);
        }
    }

    if (min_thickness > max_thickness) {
        min_thickness = 0.0;
        max_thickness = 0.0;
    }

    // Write JSON
    out << "{\n";
    out << "  \"version\": \"1.0\",\n";
    out << "  \"type\": \"tetrahedral_mesh\",\n";
    out << "  \"metadata\": {\n";
    out << "    \"node_count\": " << mesh.nodes.size() << ",\n";
    out << "    \"element_count\": " << mesh.elements.size() << ",\n";
    out << "    \"boundary_nodes\": " << mesh.boundary_node_count << ",\n";
    out << "    \"interior_nodes\": " << mesh.interior_node_count << ",\n";
    out << "    \"thickness_range\": [" << min_thickness << ", " << max_thickness << "],\n";
    out << "    \"bbox\": {\n";
    out << "      \"min\": [" << mesh.min_x << ", " << mesh.min_y << ", " << mesh.min_z << "],\n";
    out << "      \"max\": [" << mesh.max_x << ", " << mesh.max_y << ", " << mesh.max_z << "]\n";
    out << "    }\n";
    out << "  },\n";

    // Write nodes
    out << "  \"nodes\": [\n";
    for (size_t i = 0; i < mesh.nodes.size(); i++) {
        const auto& node = mesh.nodes[i];
        out << "    {\"id\": " << node.id << ", ";
        out << "\"pos\": [" << node.x << ", " << node.y << ", " << node.z << "], ";
        out << "\"thickness\": " << node.thickness << ", ";
        out << "\"boundary\": " << (node.is_boundary ? "true" : "false") << "}";

        if (i < mesh.nodes.size() - 1) {
            out << ",";
        }
        out << "\n";
    }
    out << "  ],\n";

    // Write elements
    out << "  \"elements\": [\n";
    for (size_t i = 0; i < mesh.elements.size(); i++) {
        const auto& elem = mesh.elements[i];
        out << "    {\"id\": " << elem.id << ", ";
        out << "\"nodes\": [" << elem.node_ids[0] << ", "
            << elem.node_ids[1] << ", "
            << elem.node_ids[2] << ", "
            << elem.node_ids[3] << "]}";

        if (i < mesh.elements.size() - 1) {
            out << ",";
        }
        out << "\n";
    }
    out << "  ]\n";
    out << "}\n";

    out.close();

    std::cout << "    ✓ Exported to " << output_path << std::endl;
    return true;
}

} // namespace palmetto
