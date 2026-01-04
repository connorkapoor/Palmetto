/**
 * Palmetto Engine Implementation
 */

#include "engine.h"

#include <iostream>
#include <sstream>
#include <fstream>

// OpenCASCADE includes
#include <STEPControl_Reader.hxx>
#include <TopoDS.hxx>
#include <TopExp_Explorer.hxx>
#include <BRepMesh_IncrementalMesh.hxx>
#include <BRep_Tool.hxx>
#include <Poly_Triangulation.hxx>
#include <BRepLProp_SLProps.hxx>
#include <BRepAdaptor_Surface.hxx>
#include <IntCurvesFace_ShapeIntersector.hxx>
#include <Precision.hxx>

// Palmetto recognizer includes
#include "hole_recognizer.h"
#include "fillet_recognizer.h"
#include "chamfer_recognizer.h"
#include "cavity_recognizer.h"
#include "thin_wall_recognizer.h"
#include "thin_wall_recognizer_v2.h"

// glTF export
#define TINYGLTF_IMPLEMENTATION
#define STB_IMAGE_IMPLEMENTATION
#define STB_IMAGE_WRITE_IMPLEMENTATION
#include <tinygltf.h>

namespace palmetto {

Engine::Engine()
    : aag_(nullptr), feature_id_counter_(0), thin_wall_threshold_(3.0)
{
}

Engine::~Engine() {
}

bool Engine::load_step(const std::string& filepath) {
    input_filepath_ = filepath;

    STEPControl_Reader reader;
    IFSelect_ReturnStatus status = reader.ReadFile(filepath.c_str());

    if (status != IFSelect_RetDone) {
        std::cerr << "ERROR: Failed to read STEP file: " << filepath << "\n";
        return false;
    }

    // Transfer all roots
    reader.TransferRoots();

    // Get shape
    shape_ = reader.OneShape();

    if (shape_.IsNull()) {
        std::cerr << "ERROR: Loaded shape is null\n";
        return false;
    }

    std::cout << "  ✓ STEP file loaded successfully\n";

    // Build face index
    build_face_index();

    std::cout << "  ✓ Indexed " << index_to_face_.size() << " faces\n";

    return true;
}

void Engine::build_face_index() {
    index_to_face_.clear();

    for (TopExp_Explorer exp(shape_, TopAbs_FACE); exp.More(); exp.Next()) {
        TopoDS_Face face = TopoDS::Face(exp.Current());
        index_to_face_.push_back(face);
    }
}

bool Engine::build_aag() {
    if (shape_.IsNull()) {
        std::cerr << "ERROR: No shape loaded\n";
        return false;
    }

    // Create AAG instance
    aag_ = std::make_unique<AAG>();

    // Build AAG from shape
    if (!aag_->Build(shape_)) {
        std::cerr << "ERROR: Failed to build AAG\n";
        return false;
    }

    std::cout << "  ✓ AAG built successfully\n";

    return true;
}

bool Engine::recognize_features(const std::string& modules) {
    if (aag_ == nullptr) {
        std::cerr << "ERROR: AAG not built\n";
        return false;
    }

    features_.clear();

    // Parse module list
    bool run_all = (modules == "all");
    bool run_holes = run_all || (modules.find("recognize_holes") != std::string::npos);
    bool run_shafts = run_all || (modules.find("recognize_shafts") != std::string::npos);
    bool run_fillets = run_all || (modules.find("recognize_fillets") != std::string::npos);
    bool run_chamfers = run_all || (modules.find("recognize_chamfers") != std::string::npos);
    bool run_cavities = run_all || (modules.find("recognize_cavities") != std::string::npos);
    bool run_thin_walls = run_all || (modules.find("recognize_thin_walls") != std::string::npos);

    // Track face IDs that have already been classified
    std::set<int> fillet_faces;

    // IMPORTANT: Run fillet recognition FIRST
    // This allows holes to exclude fillet faces from consideration
    if (run_fillets) {
        std::cout << "  - Running fillet recognizer...\n";
        size_t before = features_.size();
        if (!run_fillet_recognizer()) {
            std::cerr << "    WARNING: Fillet recognizer failed\n";
        } else {
            // Collect fillet face IDs
            for (size_t i = before; i < features_.size(); i++) {
                for (int face_id : features_[i].face_ids) {
                    fillet_faces.insert(face_id);
                }
            }
        }
    }

    if (run_chamfers) {
        std::cout << "  - Running chamfer recognizer...\n";
        if (!run_chamfer_recognizer()) {
            std::cerr << "    WARNING: Chamfer recognizer failed\n";
        }
    }

    if (run_thin_walls) {
        std::cout << "  - Running thin wall recognizer...\n";
        if (!run_thin_wall_recognizer(thin_wall_threshold_)) {
            std::cerr << "    WARNING: Thin wall recognizer failed\n";
        }
    }

    if (run_holes) {
        std::cout << "  - Running hole recognizer...\n";
        if (!run_hole_recognizer(fillet_faces)) {
            std::cerr << "    WARNING: Hole recognizer failed\n";
        }
    }

    if (run_shafts) {
        std::cout << "  - Running shaft recognizer...\n";
        if (!run_shaft_recognizer()) {
            std::cerr << "    WARNING: Shaft recognizer failed\n";
        }
    }

    if (run_cavities) {
        std::cout << "  - Running cavity recognizer...\n";
        if (!run_cavity_recognizer()) {
            std::cerr << "    WARNING: Cavity recognizer failed\n";
        }
    }

    std::cout << "  ✓ Recognized " << features_.size() << " features\n";

    return true;
}

bool Engine::run_hole_recognizer(const std::set<int>& excluded_faces) {
    // Create hole recognizer
    HoleRecognizer recognizer(*aag_);

    // Run recognition with excluded faces
    std::vector<Feature> holes = recognizer.Recognize(excluded_faces);

    // Add to features list
    features_.insert(features_.end(), holes.begin(), holes.end());

    std::cout << "    Found " << holes.size() << " holes\n";

    return true;
}

bool Engine::run_shaft_recognizer() {
    // Simplified shaft recognizer using our AAG
    // Find external cylinders (opposite of holes - convex edges)
    std::vector<int> cyl_faces = aag_->GetCylindricalFaces();

    std::cout << "    Found " << cyl_faces.size() << " cylindrical faces (potential shafts)\n";

    // TODO: Implement shaft detection logic similar to holes but checking for convex edges
    // For now, return success but with no features (to avoid false positives)

    return true;
}

bool Engine::run_fillet_recognizer() {
    // Create fillet recognizer
    FilletRecognizer recognizer(*aag_);

    // Run recognition (fillets typically < 10mm radius)
    std::vector<Feature> fillets = recognizer.Recognize(10.0);

    // Add to features list
    features_.insert(features_.end(), fillets.begin(), fillets.end());

    std::cout << "    Found " << fillets.size() << " fillets\n";

    return true;
}

bool Engine::run_chamfer_recognizer() {
    // Create chamfer recognizer
    ChamferRecognizer recognizer(*aag_);

    // Run recognition (chamfers typically < 5mm width)
    std::vector<Feature> chamfers = recognizer.Recognize(5.0);

    // Add to features list
    features_.insert(features_.end(), chamfers.begin(), chamfers.end());

    std::cout << "    Found " << chamfers.size() << " chamfers\n";

    return true;
}

bool Engine::run_cavity_recognizer() {
    // Create cavity recognizer
    CavityRecognizer recognizer(*aag_);

    // Run recognition with infinite volume threshold (no size limit)
    std::vector<Feature> cavities = recognizer.Recognize(1e9);

    // Add to features list
    features_.insert(features_.end(), cavities.begin(), cavities.end());

    std::cout << "    Found " << cavities.size() << " cavities\n";

    return true;
}

bool Engine::run_thin_wall_recognizer(double threshold) {
    // Create graph-aware thin wall recognizer (v2)
    ThinWallRecognizerV2 recognizer(*aag_, shape_);

    // Run recognition with specified threshold and Analysis Situs validation
    std::vector<Feature> thin_walls = recognizer.Recognize(threshold, true);

    // Add to features list
    features_.insert(features_.end(), thin_walls.begin(), thin_walls.end());

    std::cout << "    Found " << thin_walls.size() << " thin walls\n";

    return true;
}

bool Engine::analyze_thickness(double max_search_distance) {
    if (!aag_) {
        std::cerr << "ERROR: AAG not built\n";
        return false;
    }

    if (shape_.IsNull()) {
        std::cerr << "ERROR: No shape loaded\n";
        return false;
    }

    std::cout << "  Running thickness analyzer...\n";

    // Create thickness analyzer
    ThicknessAnalyzer analyzer(*aag_, shape_);

    // Analyze all faces
    thickness_results_ = analyzer.AnalyzeAllFaces(max_search_distance);

    // Print statistics
    std::string stats = ThicknessAnalyzer::GenerateStatistics(thickness_results_);
    std::cout << stats;

    return true;
}

bool Engine::export_mesh(const std::string& mesh_path,
                         const std::string& mapping_path,
                         double quality)
{
    if (shape_.IsNull()) {
        std::cerr << "ERROR: No shape to mesh\n";
        return false;
    }

    // Tessellate shape
    double linear_deflection = quality;
    double angular_deflection = 0.5;

    BRepMesh_IncrementalMesh mesher(shape_, linear_deflection, Standard_False,
                                    angular_deflection, Standard_True);

    if (!mesher.IsDone()) {
        std::cerr << "ERROR: Mesh generation failed\n";
        return false;
    }

    // Build combined mesh and tri→face mapping
    tri_face_mapping_.face_ids.clear();
    tri_face_mapping_.triangle_count = 0;

    std::vector<float> vertices;
    std::vector<float> normals;
    std::vector<uint32_t> indices;
    uint32_t vertex_offset = 0;

    for (size_t face_idx = 0; face_idx < index_to_face_.size(); face_idx++) {
        const TopoDS_Face& face = index_to_face_[face_idx];

        TopLoc_Location loc;
        Handle(Poly_Triangulation) tri = BRep_Tool::Triangulation(face, loc);

        if (tri.IsNull()) {
            continue;
        }

        // Compute face normal for this face
        BRepAdaptor_Surface surface(face);
        double u_mid = (surface.FirstUParameter() + surface.LastUParameter()) / 2.0;
        double v_mid = (surface.FirstVParameter() + surface.LastVParameter()) / 2.0;

        gp_Dir face_normal(0, 0, 1);  // Default
        try {
            BRepLProp_SLProps props(surface, u_mid, v_mid, 1, 1e-6);
            if (props.IsNormalDefined()) {
                face_normal = props.Normal();
                if (face.Orientation() == TopAbs_REVERSED) {
                    face_normal.Reverse();
                }
            }
        } catch (...) {
            // Use default
        }

        // Get vertices and normals
        for (int i = 1; i <= tri->NbNodes(); i++) {
            gp_Pnt pnt = tri->Node(i).Transformed(loc);
            vertices.push_back(static_cast<float>(pnt.X()));
            vertices.push_back(static_cast<float>(pnt.Y()));
            vertices.push_back(static_cast<float>(pnt.Z()));

            // Use face normal for all vertices on this face
            normals.push_back(static_cast<float>(face_normal.X()));
            normals.push_back(static_cast<float>(face_normal.Y()));
            normals.push_back(static_cast<float>(face_normal.Z()));
        }

        // Get triangles
        for (int i = 1; i <= tri->NbTriangles(); i++) {
            const Poly_Triangle& triangle = tri->Triangle(i);
            int n1, n2, n3;
            triangle.Get(n1, n2, n3);

            indices.push_back(vertex_offset + n1 - 1);
            indices.push_back(vertex_offset + n2 - 1);
            indices.push_back(vertex_offset + n3 - 1);

            // Record face ID for this triangle
            tri_face_mapping_.face_ids.push_back(static_cast<uint32_t>(face_idx));
            tri_face_mapping_.triangle_count++;
        }

        vertex_offset += tri->NbNodes();
    }

    std::cout << "  ✓ Generated mesh: " << tri_face_mapping_.triangle_count
              << " triangles, " << vertices.size() / 3 << " vertices\n";

    // Export to glTF
    tinygltf::Model model;
    tinygltf::Scene scene;
    tinygltf::Mesh gltf_mesh;
    tinygltf::Primitive primitive;
    tinygltf::Buffer buffer;
    tinygltf::BufferView vertices_view;
    tinygltf::BufferView normals_view;
    tinygltf::BufferView indices_view;
    tinygltf::Accessor vertices_accessor;
    tinygltf::Accessor normals_accessor;
    tinygltf::Accessor indices_accessor;

    // Compute bounds for vertices
    float min_x = vertices[0], max_x = vertices[0];
    float min_y = vertices[1], max_y = vertices[1];
    float min_z = vertices[2], max_z = vertices[2];
    for (size_t i = 0; i < vertices.size(); i += 3) {
        min_x = std::min(min_x, vertices[i]);
        max_x = std::max(max_x, vertices[i]);
        min_y = std::min(min_y, vertices[i+1]);
        max_y = std::max(max_y, vertices[i+1]);
        min_z = std::min(min_z, vertices[i+2]);
        max_z = std::max(max_z, vertices[i+2]);
    }

    // Pack data into buffer
    size_t vertices_size = vertices.size() * sizeof(float);
    size_t normals_size = normals.size() * sizeof(float);
    size_t indices_size = indices.size() * sizeof(uint32_t);

    buffer.data.resize(vertices_size + normals_size + indices_size);
    memcpy(&buffer.data[0], vertices.data(), vertices_size);
    memcpy(&buffer.data[vertices_size], normals.data(), normals_size);
    memcpy(&buffer.data[vertices_size + normals_size], indices.data(), indices_size);

    // Vertices buffer view
    vertices_view.buffer = 0;
    vertices_view.byteOffset = 0;
    vertices_view.byteLength = vertices_size;
    vertices_view.target = TINYGLTF_TARGET_ARRAY_BUFFER;

    // Normals buffer view
    normals_view.buffer = 0;
    normals_view.byteOffset = vertices_size;
    normals_view.byteLength = normals_size;
    normals_view.target = TINYGLTF_TARGET_ARRAY_BUFFER;

    // Indices buffer view
    indices_view.buffer = 0;
    indices_view.byteOffset = vertices_size + normals_size;
    indices_view.byteLength = indices_size;
    indices_view.target = TINYGLTF_TARGET_ELEMENT_ARRAY_BUFFER;

    // Vertices accessor
    vertices_accessor.bufferView = 0;
    vertices_accessor.byteOffset = 0;
    vertices_accessor.componentType = TINYGLTF_COMPONENT_TYPE_FLOAT;
    vertices_accessor.count = vertices.size() / 3;
    vertices_accessor.type = TINYGLTF_TYPE_VEC3;
    vertices_accessor.minValues = {min_x, min_y, min_z};
    vertices_accessor.maxValues = {max_x, max_y, max_z};

    // Normals accessor
    normals_accessor.bufferView = 1;
    normals_accessor.byteOffset = 0;
    normals_accessor.componentType = TINYGLTF_COMPONENT_TYPE_FLOAT;
    normals_accessor.count = normals.size() / 3;
    normals_accessor.type = TINYGLTF_TYPE_VEC3;

    // Indices accessor
    indices_accessor.bufferView = 2;
    indices_accessor.byteOffset = 0;
    indices_accessor.componentType = TINYGLTF_COMPONENT_TYPE_UNSIGNED_INT;
    indices_accessor.count = indices.size();
    indices_accessor.type = TINYGLTF_TYPE_SCALAR;

    // Build primitive
    primitive.attributes["POSITION"] = 0;
    primitive.attributes["NORMAL"] = 1;
    primitive.indices = 2;
    primitive.mode = TINYGLTF_MODE_TRIANGLES;

    gltf_mesh.primitives.push_back(primitive);
    gltf_mesh.name = "palmetto_mesh";

    // Assemble model
    model.buffers.push_back(buffer);
    model.bufferViews.push_back(vertices_view);
    model.bufferViews.push_back(normals_view);
    model.bufferViews.push_back(indices_view);
    model.accessors.push_back(vertices_accessor);
    model.accessors.push_back(normals_accessor);
    model.accessors.push_back(indices_accessor);
    model.meshes.push_back(gltf_mesh);

    tinygltf::Node node;
    node.mesh = 0;
    model.nodes.push_back(node);

    scene.nodes.push_back(0);
    model.scenes.push_back(scene);
    model.defaultScene = 0;

    tinygltf::Asset asset;
    asset.version = "2.0";
    asset.generator = "Palmetto Engine";
    model.asset = asset;

    // Write glTF binary
    tinygltf::TinyGLTF gltf;
    if (!gltf.WriteGltfSceneToFile(&model, mesh_path, false, true, true, true)) {
        std::cerr << "ERROR: Failed to write glTF file\n";
        return false;
    }

    // Write tri_face_map.bin
    std::ofstream mapping_file(mapping_path, std::ios::binary);
    if (!mapping_file) {
        std::cerr << "ERROR: Failed to open mapping file for writing\n";
        return false;
    }
    mapping_file.write(reinterpret_cast<const char*>(tri_face_mapping_.face_ids.data()),
                       tri_face_mapping_.face_ids.size() * sizeof(uint32_t));
    mapping_file.close();

    return true;
}

bool Engine::export_analysis_mesh(const std::string& mesh_path,
                                   double quality,
                                   double max_search_distance)
{
    if (shape_.IsNull()) {
        std::cerr << "ERROR: No shape to mesh\n";
        return false;
    }

    std::cout << "  Generating dense FEA-style analysis mesh (quality=" << quality << ")...\n";

    // Tessellate shape with dense mesh for analysis
    double linear_deflection = quality;
    double angular_deflection = 0.3;  // Tighter angular tolerance for FEA-style mesh

    BRepMesh_IncrementalMesh mesher(shape_, linear_deflection, Standard_False,
                                    angular_deflection, Standard_True);

    if (!mesher.IsDone()) {
        std::cerr << "ERROR: Analysis mesh generation failed\n";
        return false;
    }

    std::cout << "  Computing thickness at mesh vertices...\n";

    // Build mesh and compute thickness at each vertex
    std::vector<float> vertices;
    std::vector<float> normals;
    std::vector<float> colors;  // RGB colors for thickness heatmap
    std::vector<uint32_t> indices;
    uint32_t vertex_offset = 0;

    // Track thickness statistics for color scaling
    double min_thickness = DBL_MAX;
    double max_thickness = 0.0;
    std::vector<double> vertex_thicknesses;  // Store for normalization

    // First pass: collect vertices and compute thickness
    for (size_t face_idx = 0; face_idx < index_to_face_.size(); face_idx++) {
        const TopoDS_Face& face = index_to_face_[face_idx];

        TopLoc_Location loc;
        Handle(Poly_Triangulation) tri = BRep_Tool::Triangulation(face, loc);

        if (tri.IsNull()) {
            continue;
        }

        // Get face normal for ray casting direction
        BRepAdaptor_Surface surface(face);
        double u_mid = (surface.FirstUParameter() + surface.LastUParameter()) / 2.0;
        double v_mid = (surface.FirstVParameter() + surface.LastVParameter()) / 2.0;

        gp_Dir face_normal(0, 0, 1);
        try {
            BRepLProp_SLProps props(surface, u_mid, v_mid, 1, 1e-6);
            if (props.IsNormalDefined()) {
                face_normal = props.Normal();
                if (face.Orientation() == TopAbs_REVERSED) {
                    face_normal.Reverse();
                }
            }
        } catch (...) {}

        // Process vertices
        for (int i = 1; i <= tri->NbNodes(); i++) {
            gp_Pnt pnt = tri->Node(i).Transformed(loc);

            // Compute thickness at this vertex using ray casting
            double thickness = -1.0;
            try {
                // Cast ray forward
                gp_Lin ray_forward(pnt, face_normal);
                IntCurvesFace_ShapeIntersector intersector;
                intersector.Load(shape_, Precision::Confusion());
                intersector.Perform(ray_forward, 0, max_search_distance);

                double min_dist_forward = DBL_MAX;
                if (intersector.IsDone() && intersector.NbPnt() > 0) {
                    for (int j = 1; j <= intersector.NbPnt(); j++) {
                        gp_Pnt hit = intersector.Pnt(j);
                        double dist = pnt.Distance(hit);
                        if (dist > 0.1 && dist < min_dist_forward) {
                            min_dist_forward = dist;
                        }
                    }
                }

                // Cast ray backward
                gp_Lin ray_backward(pnt, face_normal.Reversed());
                intersector.Perform(ray_backward, 0, max_search_distance);

                double min_dist_backward = DBL_MAX;
                if (intersector.IsDone() && intersector.NbPnt() > 0) {
                    for (int j = 1; j <= intersector.NbPnt(); j++) {
                        gp_Pnt hit = intersector.Pnt(j);
                        double dist = pnt.Distance(hit);
                        if (dist > 0.1 && dist < min_dist_backward) {
                            min_dist_backward = dist;
                        }
                    }
                }

                // Use minimum of forward/backward
                if (min_dist_forward < DBL_MAX && min_dist_backward < DBL_MAX) {
                    thickness = std::min(min_dist_forward, min_dist_backward);
                } else if (min_dist_forward < DBL_MAX) {
                    thickness = min_dist_forward;
                } else if (min_dist_backward < DBL_MAX) {
                    thickness = min_dist_backward;
                }

                // Update statistics
                if (thickness > 0) {
                    min_thickness = std::min(min_thickness, thickness);
                    max_thickness = std::max(max_thickness, thickness);
                }
            } catch (...) {}

            // Store vertex data
            vertices.push_back(static_cast<float>(pnt.X()));
            vertices.push_back(static_cast<float>(pnt.Y()));
            vertices.push_back(static_cast<float>(pnt.Z()));

            normals.push_back(static_cast<float>(face_normal.X()));
            normals.push_back(static_cast<float>(face_normal.Y()));
            normals.push_back(static_cast<float>(face_normal.Z()));

            vertex_thicknesses.push_back(thickness);
        }

        // Get triangles
        for (int i = 1; i <= tri->NbTriangles(); i++) {
            const Poly_Triangle& triangle = tri->Triangle(i);
            int n1, n2, n3;
            triangle.Get(n1, n2, n3);

            indices.push_back(vertex_offset + n1 - 1);
            indices.push_back(vertex_offset + n2 - 1);
            indices.push_back(vertex_offset + n3 - 1);
        }

        vertex_offset += tri->NbNodes();
    }

    std::cout << "  Generated analysis mesh: " << indices.size() / 3
              << " triangles, " << vertices.size() / 3 << " vertices\n";
    std::cout << "  Thickness range: " << min_thickness << "mm to " << max_thickness << "mm\n";

    // Second pass: convert thickness to colors using heatmap
    for (double thickness : vertex_thicknesses) {
        float r, g, b;

        if (thickness < 0) {
            // No measurement - gray
            r = g = b = 0.5f;
        } else {
            // Normalize thickness to [0, 1]
            float normalized = (max_thickness > min_thickness) ?
                static_cast<float>((thickness - min_thickness) / (max_thickness - min_thickness)) : 0.5f;

            // Heatmap: Blue (thick) → Green → Yellow → Red (thin)
            // Invert so thin = red
            normalized = 1.0f - normalized;

            if (normalized < 0.25f) {
                // Blue to Cyan
                r = 0.0f;
                g = normalized * 4.0f;
                b = 1.0f;
            } else if (normalized < 0.5f) {
                // Cyan to Green
                r = 0.0f;
                g = 1.0f;
                b = 1.0f - (normalized - 0.25f) * 4.0f;
            } else if (normalized < 0.75f) {
                // Green to Yellow
                r = (normalized - 0.5f) * 4.0f;
                g = 1.0f;
                b = 0.0f;
            } else {
                // Yellow to Red
                r = 1.0f;
                g = 1.0f - (normalized - 0.75f) * 4.0f;
                b = 0.0f;
            }
        }

        colors.push_back(r);
        colors.push_back(g);
        colors.push_back(b);
    }

    // Export to glTF with vertex colors
    tinygltf::Model model;
    tinygltf::Scene scene;
    tinygltf::Mesh gltf_mesh;
    tinygltf::Primitive primitive;
    tinygltf::Buffer buffer;

    // Compute bounds
    float min_x = vertices[0], max_x = vertices[0];
    float min_y = vertices[1], max_y = vertices[1];
    float min_z = vertices[2], max_z = vertices[2];
    for (size_t i = 0; i < vertices.size(); i += 3) {
        min_x = std::min(min_x, vertices[i]);
        max_x = std::max(max_x, vertices[i]);
        min_y = std::min(min_y, vertices[i+1]);
        max_y = std::max(max_y, vertices[i+1]);
        min_z = std::min(min_z, vertices[i+2]);
        max_z = std::max(max_z, vertices[i+2]);
    }

    // Pack data into buffer
    size_t vertices_size = vertices.size() * sizeof(float);
    size_t normals_size = normals.size() * sizeof(float);
    size_t colors_size = colors.size() * sizeof(float);
    size_t indices_size = indices.size() * sizeof(uint32_t);

    buffer.data.resize(vertices_size + normals_size + colors_size + indices_size);
    memcpy(&buffer.data[0], vertices.data(), vertices_size);
    memcpy(&buffer.data[vertices_size], normals.data(), normals_size);
    memcpy(&buffer.data[vertices_size + normals_size], colors.data(), colors_size);
    memcpy(&buffer.data[vertices_size + normals_size + colors_size], indices.data(), indices_size);

    model.buffers.push_back(buffer);

    // Buffer views
    tinygltf::BufferView vertices_view, normals_view, colors_view, indices_view;

    vertices_view.buffer = 0;
    vertices_view.byteOffset = 0;
    vertices_view.byteLength = vertices_size;
    vertices_view.target = TINYGLTF_TARGET_ARRAY_BUFFER;
    model.bufferViews.push_back(vertices_view);

    normals_view.buffer = 0;
    normals_view.byteOffset = vertices_size;
    normals_view.byteLength = normals_size;
    normals_view.target = TINYGLTF_TARGET_ARRAY_BUFFER;
    model.bufferViews.push_back(normals_view);

    colors_view.buffer = 0;
    colors_view.byteOffset = vertices_size + normals_size;
    colors_view.byteLength = colors_size;
    colors_view.target = TINYGLTF_TARGET_ARRAY_BUFFER;
    model.bufferViews.push_back(colors_view);

    indices_view.buffer = 0;
    indices_view.byteOffset = vertices_size + normals_size + colors_size;
    indices_view.byteLength = indices_size;
    indices_view.target = TINYGLTF_TARGET_ELEMENT_ARRAY_BUFFER;
    model.bufferViews.push_back(indices_view);

    // Accessors
    tinygltf::Accessor vertices_accessor, normals_accessor, colors_accessor, indices_accessor;

    vertices_accessor.bufferView = 0;
    vertices_accessor.byteOffset = 0;
    vertices_accessor.componentType = TINYGLTF_COMPONENT_TYPE_FLOAT;
    vertices_accessor.count = vertices.size() / 3;
    vertices_accessor.type = TINYGLTF_TYPE_VEC3;
    vertices_accessor.minValues = {min_x, min_y, min_z};
    vertices_accessor.maxValues = {max_x, max_y, max_z};
    model.accessors.push_back(vertices_accessor);

    normals_accessor.bufferView = 1;
    normals_accessor.byteOffset = 0;
    normals_accessor.componentType = TINYGLTF_COMPONENT_TYPE_FLOAT;
    normals_accessor.count = normals.size() / 3;
    normals_accessor.type = TINYGLTF_TYPE_VEC3;
    model.accessors.push_back(normals_accessor);

    colors_accessor.bufferView = 2;
    colors_accessor.byteOffset = 0;
    colors_accessor.componentType = TINYGLTF_COMPONENT_TYPE_FLOAT;
    colors_accessor.count = colors.size() / 3;
    colors_accessor.type = TINYGLTF_TYPE_VEC3;
    model.accessors.push_back(colors_accessor);

    indices_accessor.bufferView = 3;
    indices_accessor.byteOffset = 0;
    indices_accessor.componentType = TINYGLTF_COMPONENT_TYPE_UNSIGNED_INT;
    indices_accessor.count = indices.size();
    indices_accessor.type = TINYGLTF_TYPE_SCALAR;
    model.accessors.push_back(indices_accessor);

    // Primitive
    primitive.attributes["POSITION"] = 0;
    primitive.attributes["NORMAL"] = 1;
    primitive.attributes["COLOR_0"] = 2;
    primitive.indices = 3;
    primitive.mode = TINYGLTF_MODE_TRIANGLES;

    // Material with vertex colors
    tinygltf::Material material;
    material.name = "ThicknessHeatmap";
    material.pbrMetallicRoughness.baseColorFactor = {1.0, 1.0, 1.0, 1.0};
    material.pbrMetallicRoughness.metallicFactor = 0.0;
    material.pbrMetallicRoughness.roughnessFactor = 1.0;
    material.doubleSided = true;
    model.materials.push_back(material);
    primitive.material = 0;

    gltf_mesh.primitives.push_back(primitive);
    model.meshes.push_back(gltf_mesh);

    tinygltf::Node node;
    node.mesh = 0;
    model.nodes.push_back(node);

    scene.nodes.push_back(0);
    model.scenes.push_back(scene);
    model.defaultScene = 0;

    tinygltf::Asset asset;
    asset.version = "2.0";
    asset.generator = "Palmetto Engine - Thickness Analyzer";
    model.asset = asset;

    // Write glTF binary
    tinygltf::TinyGLTF gltf;
    if (!gltf.WriteGltfSceneToFile(&model, mesh_path, false, true, true, true)) {
        std::cerr << "ERROR: Failed to write analysis mesh glTF file\n";
        return false;
    }

    std::cout << "  ✓ Exported thickness heatmap mesh to " << mesh_path << "\n";

    return true;
}

size_t Engine::get_face_count() const {
    return index_to_face_.size();
}

size_t Engine::get_edge_count() const {
    size_t count = 0;
    for (TopExp_Explorer exp(shape_, TopAbs_EDGE); exp.More(); exp.Next()) {
        count++;
    }
    return count;
}

} // namespace palmetto
