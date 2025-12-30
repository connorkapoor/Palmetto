# Multi-stage build for Palmetto backend + C++ engine
# Stage 1: Build C++ engine with OpenCASCADE
FROM ubuntu:22.04 as cpp-builder

# Install build dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    git \
    wget \
    libfreetype6-dev \
    libx11-dev \
    libgl1-mesa-dev \
    libglu1-mesa-dev \
    libxi-dev \
    libxmu-dev \
    tcl-dev \
    tk-dev \
    libfreeimage-dev \
    rapidjson-dev \
    && rm -rf /var/lib/apt/lists/*

# Install OpenCASCADE from source (lightweight build)
WORKDIR /opt
RUN wget -q https://github.com/Open-Cascade-SAS/OCCT/archive/refs/tags/V7_8_1.tar.gz && \
    tar -xzf V7_8_1.tar.gz && \
    cd OCCT-7_8_1 && \
    mkdir build && cd build && \
    cmake .. \
    -DCMAKE_BUILD_TYPE=Release \
    -DBUILD_LIBRARY_TYPE=Static \
    -DBUILD_MODULE_Draw=OFF \
    -DBUILD_MODULE_Visualization=OFF \
    -DBUILD_MODULE_ApplicationFramework=OFF \
    -DUSE_FREETYPE=OFF \
    -DUSE_TBB=OFF \
    -DUSE_VTK=OFF \
    && make -j$(nproc) && make install && \
    cd /opt && rm -rf OCCT-7_8_1*

# Copy C++ engine source
WORKDIR /app
COPY core/ ./core/

# Build palmetto_engine
WORKDIR /app/core
RUN mkdir -p .build && cd .build && \
    cmake .. \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_PREFIX_PATH=/usr/local \
    && cmake --build . --config Release -j$(nproc)

# Stage 2: Python backend runtime
FROM ubuntu:22.04

# Install Python and runtime dependencies
RUN apt-get update && apt-get install -y \
    python3.10 \
    python3-pip \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Copy built C++ engine
COPY --from=cpp-builder /app/core/.build/bin/palmetto_engine /app/palmetto_engine
COPY --from=cpp-builder /usr/local/lib/libTK*.so* /usr/local/lib/

# Set library path
ENV LD_LIBRARY_PATH=/usr/local/lib:$LD_LIBRARY_PATH

# Copy backend source
WORKDIR /app/backend
COPY backend/requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

COPY backend/ .

# Set environment variables
ENV PALMETTO_ENGINE_PATH=/app/palmetto_engine
ENV PYTHONUNBUFFERED=1
ENV PORT=8000

# Create data directory
RUN mkdir -p /app/backend/data

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python3 -c "import requests; requests.get('http://localhost:8000/health').raise_for_status()"

# Run backend
CMD ["python3", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
