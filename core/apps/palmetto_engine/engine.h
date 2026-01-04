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
#include "sdf_generator.h"
#include "accessibility_analyzer.h"
#include "pocket_depth_analyzer.h"

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
     * Export volumetric Signed Distance Field with thickness data
     * @param sdf_path Output path for SDF JSON
     * @param resolution Number of voxels along longest axis (e.g., 100)
     * @param max_search_distance Maximum thickness search distance in mm
     * @param adaptive Use adaptive SDF with narrow-band level set (default: false)
     * @param narrow_band_width Narrow band width in mm for adaptive SDF (default: 10.0)
     * @return true if successful
     */
    bool export_sdf(const std::string& sdf_path,
                    int resolution,
                    double max_search_distance,
                    bool adaptive = false,
                    double narrow_band_width = 10.0);

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

    /**
     * DFM Geometry Analysis Methods
     */

    /**
     * Analyze thickness variance (uniformity) for all faces
     * @param max_search_distance Maximum ray casting distance in mm
     * @return true if successful
     */
    bool analyze_thickness_variance(double max_search_distance = 50.0);

    /**
     * Analyze draft angles for injection molding
     * @param draft_direction Draft direction (typically Z-axis: 0,0,1)
     * @return true if successful
     */
    bool analyze_draft_angles(const gp_Dir& draft_direction);

    /**
     * Analyze overhang angles for 3D printing
     * @return true if successful
     */
    bool analyze_overhangs();

    /**
     * Detect undercuts (negative draft angles)
     * @param draft_direction Draft direction
     * @return true if successful
     */
    bool detect_undercuts(const gp_Dir& draft_direction);

    /**
     * Compute stress concentration from SDF gradient
     * Requires SDF to be generated first via export_sdf()
     * @param sdf The generated SDF data
     * @return true if successful
     */
    bool compute_stress_concentration(const palmetto::SDF& sdf);

    /**
     * Analyze molding accessibility (true undercut detection)
     * Uses ray-based volumetric analysis to detect blocked faces
     * @param draft_direction Draft direction for molding
     * @return true if successful
     */
    bool analyze_molding_accessibility(const gp_Dir& draft_direction);

    /**
     * Analyze CNC machining accessibility
     * Tests face accessibility from 6 standard directions (+/-X, +/-Y, +/-Z)
     * @return true if successful
     */
    bool analyze_cnc_accessibility();

    /**
     * Analyze pocket depths for recognized cavities
     * Computes depth, aspect ratio, classification, and accessibility scores
     * @return true if successful
     */
    bool analyze_pocket_depths();

    /**
     * Get DFM analysis results
     */
    const std::map<int, double>& get_variance_results() const { return variance_results_; }
    const std::map<int, double>& get_stress_results() const { return stress_results_; }
    const std::map<int, double>& get_draft_results() const { return draft_results_; }
    const std::map<int, double>& get_overhang_results() const { return overhang_results_; }
    const std::map<int, bool>& get_undercut_results() const { return undercut_results_; }
    const std::map<int, AccessibilityResult>& get_molding_accessibility() const { return molding_accessibility_results_; }
    const std::map<int, AccessibilityResult>& get_cnc_accessibility() const { return cnc_accessibility_results_; }
    const std::map<int, PocketDepthResult>& get_pocket_depths() const { return pocket_depth_results_; }

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

    // DFM geometry analysis results
    std::map<int, double> variance_results_;
    std::map<int, double> stress_results_;
    std::map<int, double> draft_results_;
    std::map<int, double> overhang_results_;
    std::map<int, bool> undercut_results_;

    // Enhanced DFM analysis results
    std::map<int, AccessibilityResult> molding_accessibility_results_;
    std::map<int, AccessibilityResult> cnc_accessibility_results_;
    std::map<int, PocketDepthResult> pocket_depth_results_;

    // Feature ID counters
    int feature_id_counter_;

    // Configuration
    double thin_wall_threshold_;
};

} // namespace palmetto
