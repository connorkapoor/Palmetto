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

# Include directories
include_directories(
    ${OpenCASCADE_INCLUDE_DIR}
    ${CMAKE_SOURCE_DIR}/apps/palmetto_engine
    ${CMAKE_SOURCE_DIR}/third_party
)

# Palmetto Engine executable
add_executable(palmetto_engine
    apps/palmetto_engine/main.cpp
    apps/palmetto_engine/engine.cpp
    apps/palmetto_engine/aag.cpp
    apps/palmetto_engine/hole_recognizer.cpp
    apps/palmetto_engine/fillet_recognizer.cpp
    apps/palmetto_engine/chamfer_recognizer.cpp
    apps/palmetto_engine/cavity_recognizer.cpp
    apps/palmetto_engine/blend_recognizer.cpp
    apps/palmetto_engine/json_exporter.cpp
)

# Link libraries
target_link_libraries(palmetto_engine
    PRIVATE
    ${OpenCASCADE_LIBRARIES}
)

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
message(STATUS "Install prefix: ${CMAKE_INSTALL_PREFIX}")
message(STATUS "==========================================")
message(STATUS "")
