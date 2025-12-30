/**
 * JSON Exporter - Exports features, AAG, and metadata to JSON
 */

#pragma once

#include <string>
#include "engine.h"

namespace palmetto {

/**
 * Exports engine results to JSON files
 */
class JsonExporter {
public:
    explicit JsonExporter(const Engine& engine);

    /**
     * Export recognized features to JSON
     * Schema: {model_id, units, features: [{id, type, subtype, faces, edges, params, source, confidence}]}
     */
    bool export_features(const std::string& filepath);

    /**
     * Export AAG to JSON
     * Schema: {nodes: [{id, type, attributes}], arcs: [{u, v, attributes}]}
     */
    bool export_aag(const std::string& filepath);

    /**
     * Export metadata to JSON
     * Schema: {counts, timings, warnings, units, bbox}
     */
    bool export_metadata(const std::string& filepath, long processing_time_ms);

    /**
     * Export topology geometry (vertices and edges) to JSON for 3D visualization
     * Schema: {vertices: [{id, position: [x,y,z]}], edges: [{id, vertices: [v1,v2]}]}
     */
    bool export_topology_geometry(const std::string& filepath);

private:
    const Engine& engine_;
};

} // namespace palmetto
