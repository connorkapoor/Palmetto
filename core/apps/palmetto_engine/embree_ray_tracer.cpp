#include "embree_ray_tracer.h"
#include <BRepMesh_IncrementalMesh.hxx>
#include <BRep_Tool.hxx>
#include <TopExp_Explorer.hxx>
#include <TopoDS.hxx>
#include <TopoDS_Face.hxx>
#include <Poly_Triangulation.hxx>
#include <TopLoc_Location.hxx>
#include <iostream>
#include <cstring>

EmbreeRayTracer::EmbreeRayTracer() : device_(nullptr), scene_(nullptr) {
    // Create Embree device
    device_ = rtcNewDevice(nullptr);
    if (!device_) {
        std::cerr << "ERROR: Failed to create Embree device\n";
        RTCError error = rtcGetDeviceError(nullptr);
        if (error != RTC_ERROR_NONE) {
            std::cerr << "Embree error code: " << error << "\n";
        }
    }
}

EmbreeRayTracer::~EmbreeRayTracer() {
    // Clean up Embree resources
    if (scene_) {
        rtcReleaseScene(scene_);
        scene_ = nullptr;
    }
    if (device_) {
        rtcReleaseDevice(device_);
        device_ = nullptr;
    }
}

bool EmbreeRayTracer::Build(const TopoDS_Shape& shape, double mesh_quality) {
    if (!device_) {
        std::cerr << "ERROR: No Embree device available\n";
        return false;
    }

    // Step 1: Tessellate BREP to triangles
    std::cout << "  [Embree] Tessellating shape (quality=" << mesh_quality << ")...\n";
    BRepMesh_IncrementalMesh mesher(shape, mesh_quality);
    mesher.Perform();

    if (!mesher.IsDone()) {
        std::cerr << "ERROR: Tessellation failed\n";
        return false;
    }

    // Step 2: Extract triangles from all faces
    vertex_buffer_.clear();
    index_buffer_.clear();

    std::map<gp_Pnt, unsigned int, PntComparator> vertex_map;
    unsigned int vertex_index = 0;

    int face_count = 0;
    for (TopExp_Explorer exp(shape, TopAbs_FACE); exp.More(); exp.Next()) {
        face_count++;
        TopoDS_Face face = TopoDS::Face(exp.Current());
        TopLoc_Location loc;
        Handle(Poly_Triangulation) triangulation = BRep_Tool::Triangulation(face, loc);

        if (triangulation.IsNull()) {
            continue;
        }

        // Add vertices with transformation
        for (int i = 1; i <= triangulation->NbNodes(); i++) {
            gp_Pnt pnt = triangulation->Node(i).Transformed(loc);

            // Check if vertex already exists
            auto it = vertex_map.find(pnt);
            if (it == vertex_map.end()) {
                // Add new vertex
                vertex_buffer_.push_back(static_cast<float>(pnt.X()));
                vertex_buffer_.push_back(static_cast<float>(pnt.Y()));
                vertex_buffer_.push_back(static_cast<float>(pnt.Z()));
                vertex_map[pnt] = vertex_index++;
            }
        }

        // Add triangles
        for (int i = 1; i <= triangulation->NbTriangles(); i++) {
            Poly_Triangle triangle = triangulation->Triangle(i);
            int n1, n2, n3;
            triangle.Get(n1, n2, n3);

            // Transform triangle nodes
            gp_Pnt p1 = triangulation->Node(n1).Transformed(loc);
            gp_Pnt p2 = triangulation->Node(n2).Transformed(loc);
            gp_Pnt p3 = triangulation->Node(n3).Transformed(loc);

            // Add triangle indices
            index_buffer_.push_back(vertex_map[p1]);
            index_buffer_.push_back(vertex_map[p2]);
            index_buffer_.push_back(vertex_map[p3]);
        }
    }

    std::cout << "  [Embree] Tessellated " << face_count << " faces\n";
    std::cout << "  [Embree] Generated " << (vertex_buffer_.size() / 3) << " vertices, "
              << (index_buffer_.size() / 3) << " triangles\n";

    // Step 3: Create Embree scene
    scene_ = rtcNewScene(device_);
    if (!scene_) {
        std::cerr << "ERROR: Failed to create Embree scene\n";
        return false;
    }

    RTCGeometry geometry = rtcNewGeometry(device_, RTC_GEOMETRY_TYPE_TRIANGLE);
    if (!geometry) {
        std::cerr << "ERROR: Failed to create Embree geometry\n";
        return false;
    }

    // Upload vertex buffer
    float* vertices = (float*)rtcSetNewGeometryBuffer(
        geometry,
        RTC_BUFFER_TYPE_VERTEX,
        0,
        RTC_FORMAT_FLOAT3,
        3 * sizeof(float),
        vertex_buffer_.size() / 3
    );

    if (!vertices) {
        std::cerr << "ERROR: Failed to allocate vertex buffer\n";
        rtcReleaseGeometry(geometry);
        return false;
    }

    std::memcpy(vertices, vertex_buffer_.data(), vertex_buffer_.size() * sizeof(float));

    // Upload index buffer
    unsigned int* indices = (unsigned int*)rtcSetNewGeometryBuffer(
        geometry,
        RTC_BUFFER_TYPE_INDEX,
        0,
        RTC_FORMAT_UINT3,
        3 * sizeof(unsigned int),
        index_buffer_.size() / 3
    );

    if (!indices) {
        std::cerr << "ERROR: Failed to allocate index buffer\n";
        rtcReleaseGeometry(geometry);
        return false;
    }

    std::memcpy(indices, index_buffer_.data(), index_buffer_.size() * sizeof(unsigned int));

    // Commit geometry
    rtcCommitGeometry(geometry);
    rtcAttachGeometry(scene_, geometry);
    rtcReleaseGeometry(geometry);  // Scene holds reference

    // Commit scene (builds BVH)
    std::cout << "  [Embree] Building BVH acceleration structure...\n";
    rtcCommitScene(scene_);

    std::cout << "  [Embree] Scene built successfully\n";
    return true;
}

double EmbreeRayTracer::CastRay(const gp_Pnt& origin, const gp_Dir& direction, double max_distance) const {
    if (!scene_) {
        return -1.0;
    }

    // Setup ray
    RTCRayHit rayhit;
    rayhit.ray.org_x = static_cast<float>(origin.X());
    rayhit.ray.org_y = static_cast<float>(origin.Y());
    rayhit.ray.org_z = static_cast<float>(origin.Z());
    rayhit.ray.dir_x = static_cast<float>(direction.X());
    rayhit.ray.dir_y = static_cast<float>(direction.Y());
    rayhit.ray.dir_z = static_cast<float>(direction.Z());
    rayhit.ray.tnear = 0.01f;  // Avoid self-intersection
    rayhit.ray.tfar = static_cast<float>(max_distance);
    rayhit.ray.mask = 0xFFFFFFFF;
    rayhit.ray.flags = 0;
    rayhit.hit.geomID = RTC_INVALID_GEOMETRY_ID;
    rayhit.hit.instID[0] = RTC_INVALID_GEOMETRY_ID;

    // Cast ray
    RTCIntersectArguments args;
    rtcInitIntersectArguments(&args);

    rtcIntersect1(scene_, &rayhit, &args);

    // Check if hit
    if (rayhit.hit.geomID != RTC_INVALID_GEOMETRY_ID) {
        return static_cast<double>(rayhit.ray.tfar);
    }

    return -1.0;
}

void EmbreeRayTracer::CastRays(
    const std::vector<gp_Pnt>& origins,
    const std::vector<gp_Dir>& directions,
    std::vector<double>& distances,
    double max_distance
) const {
    distances.resize(origins.size());

    for (size_t i = 0; i < origins.size(); i++) {
        distances[i] = CastRay(origins[i], directions[i], max_distance);
    }
}

bool EmbreeRayTracer::IsInside(const gp_Pnt& point) const {
    if (!scene_) return false;

    // Use single ray cast to check inside/outside
    // Cast in +X, +Y, +Z directions and use majority vote
    int inside_votes = 0;

    static const float directions[3][3] = {
        {1.0f, 0.0f, 0.0f},  // +X
        {0.0f, 1.0f, 0.0f},  // +Y
        {0.0f, 0.0f, 1.0f}   // +Z
    };

    for (int dir = 0; dir < 3; dir++) {
        RTCRayHit rayhit;
        rayhit.ray.org_x = static_cast<float>(point.X());
        rayhit.ray.org_y = static_cast<float>(point.Y());
        rayhit.ray.org_z = static_cast<float>(point.Z());
        rayhit.ray.dir_x = directions[dir][0];
        rayhit.ray.dir_y = directions[dir][1];
        rayhit.ray.dir_z = directions[dir][2];
        rayhit.ray.tnear = 0.01f;
        rayhit.ray.tfar = 1e10f;
        rayhit.ray.mask = 0xFFFFFFFF;
        rayhit.ray.flags = 0;
        rayhit.hit.geomID = RTC_INVALID_GEOMETRY_ID;
        rayhit.hit.instID[0] = RTC_INVALID_GEOMETRY_ID;

        // Count intersections by repeatedly casting
        int count = 0;
        float ray_pos = 0.0f;

        // Maximum 50 intersections per direction
        for (int i = 0; i < 50; i++) {
            RTCIntersectArguments args;
            rtcInitIntersectArguments(&args);
            rtcIntersect1(scene_, &rayhit, &args);

            if (rayhit.hit.geomID == RTC_INVALID_GEOMETRY_ID) {
                break;  // No more hits
            }

            count++;

            // Advance ray start beyond this hit
            ray_pos += rayhit.ray.tfar + 0.01f;
            rayhit.ray.org_x = static_cast<float>(point.X()) + ray_pos * directions[dir][0];
            rayhit.ray.org_y = static_cast<float>(point.Y()) + ray_pos * directions[dir][1];
            rayhit.ray.org_z = static_cast<float>(point.Z()) + ray_pos * directions[dir][2];
            rayhit.ray.tnear = 0.0f;
            rayhit.ray.tfar = 1e10f;
            rayhit.hit.geomID = RTC_INVALID_GEOMETRY_ID;
            rayhit.hit.instID[0] = RTC_INVALID_GEOMETRY_ID;
        }

        // Odd count = inside for this direction
        if ((count % 2) == 1) {
            inside_votes++;
        }
    }

    // Majority vote (2 out of 3 directions say inside)
    return inside_votes >= 2;
}
