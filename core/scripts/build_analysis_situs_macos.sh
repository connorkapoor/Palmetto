#!/bin/bash
set -e

# Analysis Situs Build Script for macOS (Headless SDK Only)
# Builds only the algorithm libraries without GUI dependencies

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
CORE_DIR="$(dirname "$SCRIPT_DIR")"
ASITUS_SRC="$CORE_DIR/third_party/AnalysisSitus"
OCCT_INSTALL="$CORE_DIR/.local/occt"
ASITUS_BUILD="$CORE_DIR/.build/analysis_situs"
THIRDPARTY_DIR="$CORE_DIR/.local/3rdparty"

echo "==> Building Analysis Situs (headless SDK)"

# Check OCCT is built
if [ ! -f "$OCCT_INSTALL/lib/libTKernel.dylib" ]; then
    echo "ERROR: OCCT not found. Run build_occt_macos.sh first."
    exit 1
fi

# Create 3rdparty directory structure
mkdir -p "$THIRDPARTY_DIR"

# Install Eigen (header-only library)
if [ ! -d "$THIRDPARTY_DIR/eigen-3.4.0" ]; then
    echo "==> Installing Eigen 3.4.0..."
    cd "$THIRDPARTY_DIR"
    curl -L https://gitlab.com/libeigen/eigen/-/archive/3.4.0/eigen-3.4.0.tar.gz -o eigen.tar.gz
    tar xzf eigen.tar.gz
    rm eigen.tar.gz

    # Create cmake files for eigen
    mkdir -p eigen-3.4.0/cmake
    cat > eigen-3.4.0/cmake/Eigen3Config.cmake << 'EOF'
set(EIGEN3_INCLUDE_DIR "${CMAKE_CURRENT_LIST_DIR}/..")
set(EIGEN3_FOUND TRUE)
EOF
else
    echo "==> Eigen already installed"
fi

# Install RapidJSON (header-only library)
if [ ! -d "$THIRDPARTY_DIR/rapidjson-1.1.0" ]; then
    echo "==> Installing RapidJSON 1.1.0..."
    cd "$THIRDPARTY_DIR"
    curl -L https://github.com/Tencent/rapidjson/archive/refs/tags/v1.1.0.tar.gz -o rapidjson.tar.gz
    tar xzf rapidjson.tar.gz
    rm rapidjson.tar.gz
else
    echo "==> RapidJSON already installed"
fi

# Create build directory
mkdir -p "$ASITUS_BUILD"
cd "$ASITUS_BUILD"

echo "==> Configuring Analysis Situs..."
cmake -G Ninja \
    -DCMAKE_BUILD_TYPE=Release \
    -DDISTRIBUTION_TYPE=Algo \
    -D3RDPARTY_DIR="$THIRDPARTY_DIR" \
    -D3RDPARTY_OCCT_DIR="$OCCT_INSTALL" \
    -D3RDPARTY_OCCT_INCLUDE_DIR="$OCCT_INSTALL/include/opencascade" \
    -D3RDPARTY_OCCT_LIBRARY_DIR="$OCCT_INSTALL/lib" \
    -D3RDPARTY_EIGEN_DIR="$THIRDPARTY_DIR/eigen-3.4.0" \
    -D3RDPARTY_EIGEN_INCLUDE_DIR="$THIRDPARTY_DIR/eigen-3.4.0" \
    -D3RDPARTY_RAPIDJSON_DIR="$THIRDPARTY_DIR/rapidjson-1.1.0" \
    -D3RDPARTY_RAPIDJSON_INCLUDE_DIR="$THIRDPARTY_DIR/rapidjson-1.1.0/include" \
    -DUSE_RAPIDJSON=ON \
    -DUSE_THREADING=OFF \
    -DUSE_MOBIUS=OFF \
    -DUSE_FBX_SDK=OFF \
    -DINSTALL_DIR="$CORE_DIR/.local/analysis_situs" \
    "$ASITUS_SRC"

echo "==> Building Analysis Situs (this may take 5-10 minutes)..."
ninja -j$(sysctl -n hw.ncpu)

echo "==> Installing Analysis Situs..."
ninja install

echo "==> Analysis Situs build complete!"
echo "    Install prefix: $CORE_DIR/.local/analysis_situs"
echo "    Libraries: $CORE_DIR/.local/analysis_situs/lib"
echo "    Headers: $CORE_DIR/.local/analysis_situs/include"

# Verify installation
if [ -f "$CORE_DIR/.local/analysis_situs/lib/libTKASIAlgo.dylib" ]; then
    echo "==> ✓ Verification: libTKASIAlgo.dylib found"
else
    echo "==> ✗ WARNING: libTKASIAlgo.dylib not found!"
    echo "    Build may have succeeded but SDK library names might differ"
    echo "    Check: $CORE_DIR/.local/analysis_situs/lib/"
    ls -la "$CORE_DIR/.local/analysis_situs/lib/" 2>/dev/null || true
fi
