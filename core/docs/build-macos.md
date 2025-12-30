# Building Palmetto C++ Engine on macOS

This guide covers building the Palmetto C++ engine with Analysis Situs on macOS.

## Prerequisites

### 1. Install Xcode Command Line Tools
```bash
xcode-select --install
```

### 2. Install Homebrew (if not already installed)
```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

### 3. Install Build Tools
```bash
brew install cmake ninja git python
```

## Build Steps

### Step 1: Build Open CASCADE Technology (OCCT)

OCCT is the CAD kernel that Analysis Situs is built on.

```bash
cd /Users/connorkapoor/Desktop/Palmetto/core
./scripts/build_occt_macos.sh
```

This will:
- Clone OCCT 7.8.1 from the official repository
- Configure with only the modules we need (headless, no GUI)
- Build with Ninja (parallelized)
- Install to `core/.local/occt/`

**Time**: ~10-20 minutes on modern hardware

**Verification**: Check for `core/.local/occt/lib/libTKernel.dylib`

### Step 2: Build Analysis Situs (Headless Libraries)

Analysis Situs provides the feature recognition algorithms.

```bash
cd /Users/connorkapoor/Desktop/Palmetto/core
mkdir -p .build/analysis_situs
cd .build/analysis_situs

cmake -G Ninja \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_PREFIX_PATH="../../.local/occt" \
  -DBUILD_GUI=OFF \
  -DBUILD_SDK=ON \
  ../../third_party/AnalysisSitus

ninja -j$(sysctl -n hw.ncpu)
ninja install
```

This builds only the SDK libraries without the GUI components.

### Step 3: Build Palmetto Engine

```bash
cd /Users/connorkapoor/Desktop/Palmetto/core
mkdir -p .build/palmetto_engine
cd .build/palmetto_engine

cmake -G Ninja \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_PREFIX_PATH="../../.local/occt" \
  ../..

ninja
```

**Verification**:
```bash
./palmetto_engine --help
```

Should display usage information.

## Directory Structure

After building:

```
Palmetto/
  core/
    .local/
      occt/               # OCCT installation
        lib/              # OCCT dylibs
        include/          # OCCT headers
    .build/
      occt/               # OCCT build artifacts
      analysis_situs/     # Analysis Situs build artifacts
      palmetto_engine/    # Palmetto engine build
    third_party/
      AnalysisSitus/      # Analysis Situs source (submodule)
      occt/               # OCCT source
    apps/
      palmetto_engine/    # Palmetto engine source
```

## Troubleshooting

### OCCT Build Fails
- Ensure cmake and ninja are installed
- Check that you have Xcode Command Line Tools
- Try cleaning: `rm -rf core/.build/occt core/.local/occt`

### Analysis Situs Build Fails
- Ensure OCCT built successfully first
- Check CMAKE_PREFIX_PATH points to OCCT install
- Verify OCCT dylibs exist in `core/.local/occt/lib/`

### Runtime Linking Issues
If `palmetto_engine` can't find dylibs:

```bash
otool -L palmetto_engine  # Check linked libraries
```

Fix with:
```bash
install_name_tool -add_rpath @executable_path/../.local/occt/lib palmetto_engine
```

## Next Steps

Once built, see:
- [Architecture](../../docs/architecture.md) - System design
- [Integration Guide](../../backend/docs/cpp-integration.md) - Calling from FastAPI
