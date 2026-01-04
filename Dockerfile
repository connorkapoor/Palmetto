# Optimized Dockerfile using pre-built OpenCASCADE packages
# Build time: ~5 minutes (vs 40+ minutes compiling from source)

FROM ubuntu:22.04 as builder

# Prevent interactive prompts
ENV DEBIAN_FRONTEND=noninteractive

# Install OpenCASCADE from Ubuntu repos + build tools
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    git \
    libocct-data-exchange-dev \
    libocct-foundation-dev \
    libocct-modeling-algorithms-dev \
    libocct-modeling-data-dev \
    libocct-ocaf-dev \
    libocct-visualization-dev \
    rapidjson-dev \
    libembree-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy C++ engine source (excluding submodules - they're not needed for current build)
WORKDIR /app/core
COPY core/apps ./apps
COPY core/cmake ./cmake
COPY core/CMakeLists.txt .

# Create third_party directory (submodules not needed for current build)
RUN mkdir -p third_party

# Build palmetto_engine with Embree support
RUN mkdir -p .build && cd .build && \
    cmake .. -DCMAKE_BUILD_TYPE=Release -DENABLE_EMBREE=ON && \
    cmake --build . --config Release -j$(nproc)

# Runtime stage
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

# Install runtime dependencies (using -dev packages as they include runtime libs)
RUN apt-get update && apt-get install -y \
    python3.10 \
    python3-pip \
    libocct-data-exchange-dev \
    libocct-foundation-dev \
    libocct-modeling-algorithms-dev \
    libocct-modeling-data-dev \
    libembree3 \
    && rm -rf /var/lib/apt/lists/*

# Copy built engine
COPY --from=builder /app/core/.build/bin/palmetto_engine /app/palmetto_engine

# Install Python dependencies
WORKDIR /app/backend
COPY backend/requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy backend code
COPY backend/ .

# Environment
ENV PALMETTO_ENGINE_PATH=/app/palmetto_engine
ENV PYTHONUNBUFFERED=1

# Create data directory
RUN mkdir -p /app/backend/data

EXPOSE 8000

# Health check - use PORT env var (Railway sets this at runtime)
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python3 -c "import urllib.request, os; urllib.request.urlopen(f'http://localhost:{os.environ.get(\"PORT\", \"8000\")}/health').read()"

# Run - use shell form with explicit /bin/sh to allow PORT env var substitution
CMD ["/bin/sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
