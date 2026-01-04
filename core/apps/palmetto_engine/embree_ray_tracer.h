#ifndef EMBREE_RAY_TRACER_H
#define EMBREE_RAY_TRACER_H

#include <embree4/rtcore.h>
#include <TopoDS_Shape.hxx>
#include <gp_Pnt.hxx>
#include <gp_Dir.hxx>
#include <vector>
#include <map>

/**
 * Wrapper for Embree-accelerated ray-shape intersection.
 *
 * Converts OpenCASCADE B-Rep shapes to triangle meshes and uses
 * Intel Embree's BVH acceleration for fast ray tracing.
 *
 * Performance: 5-10x faster than CPU-only IntCurvesFace_ShapeIntersector
 */
class EmbreeRayTracer {
public:
    EmbreeRayTracer();
    ~EmbreeRayTracer();

    /**
     * Build Embree scene from BREP shape (via tessellation).
     *
     * @param shape OpenCASCADE shape to tessellate
     * @param mesh_quality Tessellation quality (smaller = finer mesh, default 0.05)
     * @return true if successful, false on error
     */
    bool Build(const TopoDS_Shape& shape, double mesh_quality = 0.05);

    /**
     * Cast a single ray and return closest intersection distance.
     *
     * @param origin Ray origin point
     * @param direction Ray direction (unit vector)
     * @param max_distance Maximum search distance
     * @return Distance to closest intersection, or -1.0 if no intersection
     */
    double CastRay(const gp_Pnt& origin, const gp_Dir& direction, double max_distance = 1e6) const;

    /**
     * Batch ray casting (for SDF generation).
     * Casts multiple rays in parallel.
     *
     * @param origins Vector of ray origin points
     * @param directions Vector of ray directions (must match origins size)
     * @param distances Output vector of intersection distances
     * @param max_distance Maximum search distance
     */
    void CastRays(const std::vector<gp_Pnt>& origins,
                  const std::vector<gp_Dir>& directions,
                  std::vector<double>& distances,
                  double max_distance = 1e6) const;

    /**
     * Check if Embree scene is valid and ready for ray casting.
     */
    bool IsValid() const { return scene_ != nullptr; }

    /**
     * Get statistics about the mesh.
     */
    void GetStats(int& vertex_count, int& triangle_count) const {
        vertex_count = vertex_buffer_.size() / 3;
        triangle_count = index_buffer_.size() / 3;
    }

    /**
     * Check if point is inside solid using ray casting (odd-even test).
     * Much faster than BRepClass3d_SolidClassifier.
     *
     * @param point Point to test
     * @return true if inside, false if outside
     */
    bool IsInside(const gp_Pnt& point) const;

private:
    RTCDevice device_;           // Embree device handle
    RTCScene scene_;             // Embree scene (BVH structure)
    std::vector<float> vertex_buffer_;    // Flattened vertex coordinates [x,y,z,x,y,z,...]
    std::vector<unsigned int> index_buffer_;  // Triangle indices [i0,i1,i2,...]

    // Helper for comparing gp_Pnt (needed for std::map)
    struct PntComparator {
        bool operator()(const gp_Pnt& a, const gp_Pnt& b) const {
            if (a.X() != b.X()) return a.X() < b.X();
            if (a.Y() != b.Y()) return a.Y() < b.Y();
            return a.Z() < b.Z();
        }
    };
};

#endif // EMBREE_RAY_TRACER_H
