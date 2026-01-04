cmake_minimum_required(VERSION 3.20)
project(PalmettoEngine VERSION 1.0.0 LANGUAGES CXX)

# C++ Standard
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Build type
if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Release)
endif()

# Output directories
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/bin)
set(CMAKE_LIBRARY_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/lib)
set(CMAKE_ARCHIVE_OUTPUT_DIRECTORY ${CMAKE_BINARY_DIR}/lib)

# macOS-specific settings
if(APPLE)
    set(CMAKE_MACOSX_RPATH ON)
    set(CMAKE_INSTALL_RPATH "@executable_path/../lib;@executable_path/../.local/occt/lib")
    set(CMAKE_BUILD_WITH_INSTALL_RPATH ON)
endif()

# Add custom CMake modules path
list(APPEND CMAKE_MODULE_PATH "${CMAKE_SOURCE_DIR}/cmake")

# Find OpenCASCADE
# First try CMAKE_PREFIX_PATH, then system paths
find_package(OpenCASCADE REQUIRED)

if(OpenCASCADE_FOUND)
    message(STATUS "Found OpenCASCADE ${OpenCASCADE_VERSION}")
    message(STATUS "  Include: ${OpenCASCADE_INCLUDE_DIR}")
    message(STATUS "  Libraries: ${OpenCASCADE_LIBRARIES}")
else()
    message(FATAL_ERROR "OpenCASCADE not found. Set CMAKE_PREFIX_PATH to OCCT install directory.")
endif()

# Intel Embree (optional GPU acceleration)
option(ENABLE_EMBREE "Enable Intel Embree ray tracing acceleration" ON)

if(ENABLE_EMBREE)
    # Try to find Embree (note: embree uses uppercase EMBREE_ variables)
    find_package(embree QUIET)

    if(DEFINED EMBREE_VERSION)
        message(STATUS "Found Intel Embree ${EMBREE_VERSION}")
        message(STATUS "  Include: ${EMBREE_INCLUDE_DIRS}")
        message(STATUS "  Library: ${EMBREE_LIBRARY}")
        add_definitions(-DUSE_EMBREE)
        set(EMBREE_ENABLED TRUE)
    else()
        message(WARNING "Intel Embree not found. Falling back to CPU-only mode.")
        message(WARNING "  Install with: brew install embree (macOS) or apt-get install libembree-dev (Linux)")
        set(ENABLE_EMBREE OFF)
        set(EMBREE_ENABLED FALSE)
    endif()
else()
    set(EMBREE_ENABLED FALSE)
endif()

# Include directories
include_directories(
    ${OpenCASCADE_INCLUDE_DIR}
    ${CMAKE_SOURCE_DIR}/apps/palmetto_engine
    ${CMAKE_SOURCE_DIR}/third_party
)

if(EMBREE_ENABLED)
    include_directories(${EMBREE_INCLUDE_DIRS})
endif()

# Source files
set(PALMETTO_SOURCES
    apps/palmetto_engine/main.cpp
    apps/palmetto_engine/engine.cpp
    apps/palmetto_engine/aag.cpp
    apps/palmetto_engine/hole_recognizer.cpp
    apps/palmetto_engine/fillet_recognizer.cpp
    apps/palmetto_engine/chamfer_recognizer.cpp
    apps/palmetto_engine/cavity_recognizer.cpp
    apps/palmetto_engine/blend_recognizer.cpp
    apps/palmetto_engine/thin_wall_recognizer.cpp
    apps/palmetto_engine/thin_wall_recognizer_v2.cpp
    apps/palmetto_engine/thickness_analyzer.cpp
    apps/palmetto_engine/sdf_generator.cpp
    apps/palmetto_engine/json_exporter.cpp
    apps/palmetto_engine/thickness_variance_analyzer.cpp
    apps/palmetto_engine/draft_angle_analyzer.cpp
    apps/palmetto_engine/sdf_gradient_analyzer.cpp
    apps/palmetto_engine/accessibility_analyzer.cpp
    apps/palmetto_engine/pocket_depth_analyzer.cpp
)

# Add Embree ray tracer if enabled
if(EMBREE_ENABLED)
    list(APPEND PALMETTO_SOURCES apps/palmetto_engine/embree_ray_tracer.cpp)
endif()

# Palmetto Engine executable
add_executable(palmetto_engine ${PALMETTO_SOURCES})

# Link libraries
target_link_libraries(palmetto_engine
    PRIVATE
    ${OpenCASCADE_LIBRARIES}
)

# macOS-specific OpenCASCADE library (for STEP file support)
if(APPLE)
    target_link_libraries(palmetto_engine PRIVATE /opt/homebrew/Cellar/opencascade/7.8.1_1/lib/libTKDESTEP.dylib)
endif()

# Link Embree if enabled
if(EMBREE_ENABLED)
    target_link_libraries(palmetto_engine PRIVATE ${EMBREE_LIBRARIES})
endif()

# Platform-specific libraries
if(APPLE)
    # Nothing specific needed for macOS
endif()

# Installation
install(TARGETS palmetto_engine
    RUNTIME DESTINATION bin
)

# Print configuration summary
message(STATUS "")
message(STATUS "=== Palmetto Engine Build Configuration ===")
message(STATUS "Build type: ${CMAKE_BUILD_TYPE}")
message(STATUS "C++ compiler: ${CMAKE_CXX_COMPILER}")
message(STATUS "C++ standard: ${CMAKE_CXX_STANDARD}")
message(STATUS "OpenCASCADE: ${OpenCASCADE_VERSION}")
if(EMBREE_ENABLED)
    message(STATUS "Intel Embree: ${embree_VERSION} (GPU acceleration enabled)")
else()
    message(STATUS "Intel Embree: Not found (CPU-only mode)")
endif()
message(STATUS "Install prefix: ${CMAKE_INSTALL_PREFIX}")
message(STATUS "==========================================")
message(STATUS "")
