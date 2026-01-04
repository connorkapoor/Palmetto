/**
 * Palmetto Engine - Core feature recognition engine using Analysis Situs
 */

#pragma once

#include <string>
#include <vector>
#include <memory>
#include <map>

// OpenCASCADE includes
#include <TopoDS_Shape.hxx>
#include <TopoDS_Face.hxx>

// Palmetto includes
#include "aag.h"
#include "thickness_analyzer.h"

namespace palmetto {

/**
 * Recognized feature structure
 */
struct Feature {
    std::string id;
    std::string type;       // "hole", "shaft", "fillet", "cavity", etc.
    std::string subtype;    // "simple", "countersunk", "counterbored", etc.
    std::vector<int> face_ids;
    std::vector<int> edge_ids;
    std::map<std::string, double> params;  // diameter, depth, radius, etc.
    std::string source;     // which recognizer found it
    double confidence;

    Feature() : confidence(1.0) {}
};

/**
 * Triangle to face mapping structure
 */
struct TriFaceMapping {
    std::vector<uint32_t> face_ids;  // face_id per triangle
    uint32_t triangle_count;

    TriFaceMapping() : triangle_count(0) {}
};

/**
 * Main recognition engine
 */
class Engine {
public:
    Engine();
    ~Engine();

    /**
     * Load STEP file
     * @param filepath Path to STEP file
     * @return true if successful
     */
    bool load_step(const std::string& filepath);

    /**
     * Build Attributed Adjacency Graph using Analysis Situs
     * @return true if successful
     */
    bool build_aag();

    /**
     * Run feature recognizers
     * @param modules Comma-separated list or "all"
     * @return true if successful
     */
    bool recognize_features(const std::string& modules);

    /**
     * Export mesh with triangle→face mapping
     * @param mesh_path Output glTF file path
     * @param mapping_path Output binary mapping file path
     * @param quality Mesh quality 0.0-1.0
     * @return true if successful
     */
    bool export_mesh(const std::string& mesh_path,
                     const std::string& mapping_path,
                     double quality);

    /**
     * Export dense analysis mesh with thickness heatmap as vertex colors
     * @param mesh_path Output glTF file path (mesh_analysis.glb)
     * @param quality Mesh quality 0.0-1.0 (recommend 0.01-0.05 for dense FEA-style mesh)
     * @param max_search_distance Maximum thickness search distance in mm
     * @return true if successful
     */
    bool export_analysis_mesh(const std::string& mesh_path,
                              double quality,
                              double max_search_distance);

    /**
     * Get recognized features
     */
    const std::vector<Feature>& get_features() const { return features_; }

    /**
     * Get AAG instance
     */
    AAG* get_aag() const { return aag_.get(); }

    /**
     * Get loaded shape
     */
    const TopoDS_Shape& get_shape() const { return shape_; }

    /**
     * Get triangle→face mapping
     */
    const TriFaceMapping& get_tri_face_mapping() const { return tri_face_mapping_; }

    /**
     * Statistics
     */
    size_t get_feature_count() const { return features_.size(); }
    size_t get_triangle_count() const { return tri_face_mapping_.triangle_count; }
    size_t get_face_count() const;
    size_t get_edge_count() const;

    /**
     * Set thin wall threshold
     */
    void set_thin_wall_threshold(double threshold) { thin_wall_threshold_ = threshold; }

    /**
     * Analyze thickness for all faces
     * @param max_search_distance Maximum ray casting distance in mm
     * @return true if successful
     */
    bool analyze_thickness(double max_search_distance = 50.0);

    /**
     * Get thickness analysis results
     */
    const std::map<int, ThicknessResult>& get_thickness_results() const { return thickness_results_; }

private:
    // Internal implementation
    bool run_hole_recognizer(const std::set<int>& excluded_faces = {});
    bool run_shaft_recognizer();
    bool run_fillet_recognizer();
    bool run_chamfer_recognizer();
    bool run_cavity_recognizer();
    bool run_thin_wall_recognizer(double threshold);

    // Build face index map (deterministic face IDs)
    void build_face_index();

    // Data members
    TopoDS_Shape shape_;
    std::unique_ptr<AAG> aag_;
    std::vector<Feature> features_;
    TriFaceMapping tri_face_mapping_;
    std::vector<TopoDS_Face> index_to_face_;
    std::string input_filepath_;

    // Thickness analysis results
    std::map<int, ThicknessResult> thickness_results_;

    // Feature ID counters
    int feature_id_counter_;

    // Configuration
    double thin_wall_threshold_;
};

} // namespace palmetto
