#!/bin/bash
set -e

# OCCT Build Script for macOS
# Builds Open CASCADE Technology from source

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
CORE_DIR="$(dirname "$SCRIPT_DIR")"
OCCT_VERSION="7.7.0"
OCCT_TAG="V${OCCT_VERSION//./_}"
INSTALL_PREFIX="$CORE_DIR/.local/occt"
BUILD_DIR="$CORE_DIR/.build/occt"

echo "==> Building OCCT ${OCCT_VERSION} for macOS"

# Check dependencies
if ! command -v cmake &> /dev/null; then
    echo "ERROR: cmake not found. Install with: brew install cmake"
    exit 1
fi

if ! command -v ninja &> /dev/null; then
    echo "ERROR: ninja not found. Install with: brew install ninja"
    exit 1
fi

# Clone OCCT if not present
if [ ! -d "$CORE_DIR/third_party/occt" ]; then
    echo "==> Cloning OCCT ${OCCT_TAG}..."
    mkdir -p "$CORE_DIR/third_party"
    cd "$CORE_DIR/third_party"
    git clone --depth 1 --branch "$OCCT_TAG" https://git.dev.opencascade.org/repos/occt.git occt
else
    echo "==> OCCT source already exists"
fi

# Create build directory
mkdir -p "$BUILD_DIR"
cd "$BUILD_DIR"

echo "==> Configuring OCCT..."
cmake -G Ninja \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_INSTALL_PREFIX="$INSTALL_PREFIX" \
    -DBUILD_LIBRARY_TYPE=Shared \
    -DBUILD_MODULE_ApplicationFramework=OFF \
    -DBUILD_MODULE_DataExchange=ON \
    -DBUILD_MODULE_Draw=OFF \
    -DBUILD_MODULE_FoundationClasses=ON \
    -DBUILD_MODULE_ModelingAlgorithms=ON \
    -DBUILD_MODULE_ModelingData=ON \
    -DBUILD_MODULE_Visualization=ON \
    -DUSE_FREETYPE=OFF \
    -DUSE_TBB=OFF \
    -DUSE_VTK=OFF \
    "$CORE_DIR/third_party/occt"

echo "==> Building OCCT (this may take 10-20 minutes)..."
ninja -j$(sysctl -n hw.ncpu)

echo "==> Installing OCCT to $INSTALL_PREFIX..."
ninja install

echo "==> OCCT build complete!"
echo "    Install prefix: $INSTALL_PREFIX"
echo "    Libraries: $INSTALL_PREFIX/lib"
echo "    Headers: $INSTALL_PREFIX/include/opencascade"

# Verify installation
if [ -f "$INSTALL_PREFIX/lib/libTKernel.dylib" ]; then
    echo "==> ✓ Verification: libTKernel.dylib found"
else
    echo "==> ✗ ERROR: libTKernel.dylib not found!"
    exit 1
fi
