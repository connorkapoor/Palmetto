/**
 * Palmetto Feature Recognition Engine
 *
 * Headless C++ engine using Analysis Situs for CAD feature recognition.
 * Invoked by FastAPI backend to process STEP files.
 */

#include <iostream>
#include <string>
#include <filesystem>
#include <chrono>

#include <gp_Dir.hxx>

#include "engine.h"
#include "json_exporter.h"
#include "version.h"
#include "sdf_generator.h"

namespace fs = std::filesystem;

void print_usage(const char* prog_name) {
    std::cout << "Palmetto Feature Recognition Engine v" << PALMETTO_VERSION << "\n"
              << "Usage: " << prog_name << " [options]\n\n"
              << "Options:\n"
              << "  --input <file>              Input STEP file (required)\n"
              << "  --outdir <dir>              Output directory (required)\n"
              << "  --modules <list>            Comma-separated module list or 'all' (default: all)\n"
              << "  --mesh-quality <val>        Mesh quality 0.0-1.0 (default: 0.35)\n"
              << "  --units <unit>              Output units: mm, cm, in (default: mm)\n"
              << "  --thin-wall-threshold <mm>  Thin wall thickness threshold (default: 5.0)\n"
              << "  --analyze-thickness <mm>    Analyze thickness for all faces (max search distance, default: off)\n"
              << "  --enable-thickness-heatmap  Generate dense mesh with thickness heatmap (mesh_analysis.glb)\n"
              << "  --heatmap-quality <val>     Analysis mesh quality 0.0-1.0 (default: 0.05, denser = smaller value)\n"
              << "  --enable-sdf                Generate volumetric Signed Distance Field (thickness_sdf.json)\n"
              << "  --sdf-resolution <val>      SDF grid resolution along longest axis (default: 100)\n"
              << "  --adaptive-sdf              Use adaptive SDF (narrow-band, faster with better resolution)\n"
              << "  --narrow-band-width <mm>    Narrow band width for adaptive SDF (default: 10mm)\n"
              << "  --analyze-dfm-geometry      Enable DFM geometry analysis (variance, draft, overhang, undercut)\n"
              << "  --draft-direction <x,y,z>   Draft direction vector for molding (default: 0,0,1)\n"
              << "  --list-modules              List available recognition modules\n"
              << "  --version                   Print version and exit\n"
              << "  --help                      Show this help\n\n"
              << "Example:\n"
              << "  " << prog_name << " --input part.step --outdir out/ --modules all --analyze-thickness 50\n\n"
              << "Outputs:\n"
              << "  mesh.glb              - 3D mesh in glTF binary format\n"
              << "  tri_face_map.bin      - Triangle to face ID mapping\n"
              << "  features.json         - Recognized features\n"
              << "  aag.json              - Attributed Adjacency Graph (includes local_thickness if --analyze-thickness used)\n"
              << "  meta.json             - Metadata (timings, counts, warnings)\n";
}

void list_modules() {
    std::cout << R"JSON({
  "modules": [
    {"name": "aag_dump", "type": "graph", "description": "Build and export Attributed Adjacency Graph"},
    {"name": "recognize_holes", "type": "recognizer", "description": "Detect drilled holes (simple, countersunk, counterbored)"},
    {"name": "recognize_shafts", "type": "recognizer", "description": "Detect cylindrical shafts and bosses"},
    {"name": "recognize_fillets", "type": "recognizer", "description": "Detect edge-based fillets and rounds"},
    {"name": "recognize_cavities", "type": "recognizer", "description": "Detect pockets, slots, and blind/through cavities"},
    {"name": "recognize_thin_walls", "type": "recognizer", "description": "Detect thin-walled features (sheets, webs, shells, concentric)"}
  ]
})JSON" << std::endl;
}

int main(int argc, char** argv) {
    // Parse command line arguments
    std::string input_file;
    std::string output_dir;
    std::string modules = "all";
    double mesh_quality = 0.35;
    std::string units = "mm";
    double thin_wall_threshold = 5.0;
    bool analyze_thickness = false;
    double thickness_max_distance = 50.0;
    bool enable_thickness_heatmap = false;
    double heatmap_quality = 0.05;  // Dense mesh for FEA-style analysis
    bool enable_sdf = false;
    int sdf_resolution = 100;
    bool adaptive_sdf = false;
    double narrow_band_width = 10.0;
    bool analyze_dfm_geometry = false;
    double draft_direction_x = 0.0;
    double draft_direction_y = 0.0;
    double draft_direction_z = 1.0;

    for (int i = 1; i < argc; ++i) {
        std::string arg = argv[i];

        if (arg == "--help" || arg == "-h") {
            print_usage(argv[0]);
            return 0;
        }
        else if (arg == "--version") {
            std::cout << "Palmetto v" << PALMETTO_VERSION << "\n"
                      << "Analysis Situs integration\n"
                      << "Built on " << __DATE__ << "\n";
            return 0;
        }
        else if (arg == "--list-modules") {
            list_modules();
            return 0;
        }
        else if (arg == "--input" && i + 1 < argc) {
            input_file = argv[++i];
        }
        else if (arg == "--outdir" && i + 1 < argc) {
            output_dir = argv[++i];
        }
        else if (arg == "--modules" && i + 1 < argc) {
            modules = argv[++i];
        }
        else if (arg == "--mesh-quality" && i + 1 < argc) {
            mesh_quality = std::stod(argv[++i]);
        }
        else if (arg == "--units" && i + 1 < argc) {
            units = argv[++i];
        }
        else if (arg == "--thin-wall-threshold" && i + 1 < argc) {
            thin_wall_threshold = std::stod(argv[++i]);
        }
        else if (arg == "--analyze-thickness" && i + 1 < argc) {
            analyze_thickness = true;
            thickness_max_distance = std::stod(argv[++i]);
        }
        else if (arg == "--enable-thickness-heatmap") {
            enable_thickness_heatmap = true;
        }
        else if (arg == "--heatmap-quality" && i + 1 < argc) {
            heatmap_quality = std::stod(argv[++i]);
        }
        else if (arg == "--enable-sdf") {
            enable_sdf = true;
        }
        else if (arg == "--sdf-resolution" && i + 1 < argc) {
            sdf_resolution = std::stoi(argv[++i]);
        }
        else if (arg == "--adaptive-sdf") {
            adaptive_sdf = true;
        }
        else if (arg == "--narrow-band-width" && i + 1 < argc) {
            narrow_band_width = std::stod(argv[++i]);
        }
        else if (arg == "--analyze-dfm-geometry") {
            analyze_dfm_geometry = true;
        }
        else if (arg == "--draft-direction" && i + 1 < argc) {
            std::string dir_str = argv[++i];
            // Parse "x,y,z" format
            size_t pos1 = dir_str.find(',');
            size_t pos2 = dir_str.rfind(',');
            if (pos1 != std::string::npos && pos2 != std::string::npos && pos1 != pos2) {
                draft_direction_x = std::stod(dir_str.substr(0, pos1));
                draft_direction_y = std::stod(dir_str.substr(pos1 + 1, pos2 - pos1 - 1));
                draft_direction_z = std::stod(dir_str.substr(pos2 + 1));
            } else {
                std::cerr << "ERROR: Invalid draft-direction format (expected: x,y,z)\n";
                return 1;
            }
        }
        else {
            std::cerr << "Unknown option: " << arg << "\n";
            print_usage(argv[0]);
            return 1;
        }
    }

    // Validate required arguments
    if (input_file.empty() || output_dir.empty()) {
        std::cerr << "ERROR: --input and --outdir are required\n";
        print_usage(argv[0]);
        return 1;
    }

    if (!fs::exists(input_file)) {
        std::cerr << "ERROR: Input file not found: " << input_file << "\n";
        return 1;
    }

    // Create output directory
    fs::create_directories(output_dir);

    std::cout << "Palmetto Feature Recognition Engine v" << PALMETTO_VERSION << "\n";
    std::cout << "Input:  " << input_file << "\n";
    std::cout << "Output: " << output_dir << "\n";
    std::cout << "Modules: " << modules << "\n\n";

    auto start_time = std::chrono::high_resolution_clock::now();

    try {
        // Create engine instance
        palmetto::Engine engine;

        // Configure engine
        engine.set_thin_wall_threshold(thin_wall_threshold);

        // Load STEP file
        std::cout << "[1/5] Loading STEP file...\n";
        if (!engine.load_step(input_file)) {
            std::cerr << "ERROR: Failed to load STEP file\n";
            return 1;
        }

        // Build AAG
        std::cout << "[2/5] Building Attributed Adjacency Graph...\n";
        if (!engine.build_aag()) {
            std::cerr << "ERROR: Failed to build AAG\n";
            return 1;
        }

        // Run recognizers
        std::cout << "[3/5] Running feature recognizers...\n";
        if (!engine.recognize_features(modules)) {
            std::cerr << "ERROR: Feature recognition failed\n";
            return 1;
        }

        // Analyze thickness (optional)
        if (analyze_thickness) {
            std::cout << "[3.5/5] Analyzing thickness...\n";
            if (!engine.analyze_thickness(thickness_max_distance)) {
                std::cerr << "WARNING: Thickness analysis failed (continuing)\n";
            }
        }

        // DFM Geometry Analysis (optional)
        if (analyze_dfm_geometry) {
            std::cout << "[3.6/5] Running DFM geometry analysis...\n";

            // Thickness variance analysis
            if (!engine.analyze_thickness_variance(thickness_max_distance)) {
                std::cerr << "WARNING: Thickness variance analysis failed (continuing)\n";
            }

            // Draft angle and undercut detection for molding
            gp_Dir draft_direction(draft_direction_x, draft_direction_y, draft_direction_z);
            if (!engine.analyze_draft_angles(draft_direction)) {
                std::cerr << "WARNING: Draft angle analysis failed (continuing)\n";
            }
            if (!engine.detect_undercuts(draft_direction)) {
                std::cerr << "WARNING: Undercut detection failed (continuing)\n";
            }

            // Overhang analysis for 3D printing
            if (!engine.analyze_overhangs()) {
                std::cerr << "WARNING: Overhang analysis failed (continuing)\n";
            }

            // Enhanced undercut detection (volumetric ray-based)
            if (!engine.analyze_molding_accessibility(draft_direction)) {
                std::cerr << "WARNING: Molding accessibility analysis failed (continuing)\n";
            }

            // CNC tool accessibility analysis
            if (!engine.analyze_cnc_accessibility()) {
                std::cerr << "WARNING: CNC accessibility analysis failed (continuing)\n";
            }

            // Pocket depth and classification analysis
            if (!engine.analyze_pocket_depths()) {
                std::cerr << "WARNING: Pocket depth analysis failed (continuing)\n";
            }

            std::cout << "  ✓ Enhanced DFM geometry analysis complete\n";
        }

        // Generate mesh with tri→face mapping
        std::cout << "[4/5] Generating mesh with face mapping...\n";
        if (!engine.export_mesh(output_dir + "/mesh.glb",
                                output_dir + "/tri_face_map.bin",
                                mesh_quality)) {
            std::cerr << "ERROR: Mesh export failed\n";
            return 1;
        }

        // Generate thickness heatmap analysis mesh (optional)
        if (enable_thickness_heatmap) {
            std::cout << "[4.5/5] Generating thickness heatmap analysis mesh...\n";
            if (!engine.export_analysis_mesh(output_dir + "/mesh_analysis.glb",
                                            heatmap_quality,
                                            thickness_max_distance)) {
                std::cerr << "WARNING: Analysis mesh export failed (continuing)\n";
            }
        }

        // Generate Signed Distance Field (optional)
        palmetto::SDF* sdf_ptr = nullptr;
        if (enable_sdf) {
            std::cout << "[4.75/5] Generating volumetric SDF...\n";
            if (!engine.export_sdf(output_dir + "/thickness_sdf.json",
                                   sdf_resolution,
                                   thickness_max_distance,
                                   adaptive_sdf,
                                   narrow_band_width)) {
                std::cerr << "WARNING: SDF export failed (continuing)\n";
            }

            // Compute stress concentration from SDF gradients (if DFM analysis requested)
            if (analyze_dfm_geometry) {
                std::cout << "[4.76/5] Computing stress concentration from SDF...\n";
                // Note: We need to load the generated SDF to compute stress concentration
                // For now, we'll skip this as it requires refactoring export_sdf to return the SDF
                std::cerr << "WARNING: Stress concentration analysis requires SDF in memory (feature coming soon)\n";
            }
        }

        // Export results
        std::cout << "[5/5] Exporting results...\n";
        palmetto::JsonExporter exporter(engine);

        if (!exporter.export_features(output_dir + "/features.json")) {
            std::cerr << "ERROR: Failed to export features.json\n";
            return 1;
        }

        if (!exporter.export_aag(output_dir + "/aag.json")) {
            std::cerr << "ERROR: Failed to export aag.json\n";
            return 1;
        }

        if (!exporter.export_topology_geometry(output_dir + "/topology.json")) {
            std::cerr << "ERROR: Failed to export topology.json\n";
            return 1;
        }

        auto end_time = std::chrono::high_resolution_clock::now();
        auto duration = std::chrono::duration_cast<std::chrono::milliseconds>(end_time - start_time);

        if (!exporter.export_metadata(output_dir + "/meta.json", duration.count())) {
            std::cerr << "ERROR: Failed to export meta.json\n";
            return 1;
        }

        std::cout << "\n✓ Processing complete in " << duration.count() << "ms\n";
        std::cout << "  Features recognized: " << engine.get_feature_count() << "\n";
        std::cout << "  Triangles generated: " << engine.get_triangle_count() << "\n";
        std::cout << "  Output files:\n";
        std::cout << "    - mesh.glb\n";
        std::cout << "    - tri_face_map.bin\n";
        std::cout << "    - features.json\n";
        std::cout << "    - aag.json\n";
        std::cout << "    - meta.json\n";
        if (enable_thickness_heatmap) {
            std::cout << "    - mesh_analysis.glb (thickness heatmap)\n";
        }

        return 0;
    }
    catch (const std::exception& e) {
        std::cerr << "ERROR: " << e.what() << "\n";
        return 1;
    }
}
