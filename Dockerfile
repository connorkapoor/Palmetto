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
    && rm -rf /var/lib/apt/lists/*

# Copy only C++ engine source
WORKDIR /app/core
COPY core/apps ./apps
COPY core/third_party ./third_party
COPY core/CMakeLists.txt .

# Build palmetto_engine
RUN mkdir -p .build && cd .build && \
    cmake .. -DCMAKE_BUILD_TYPE=Release && \
    cmake --build . --config Release -j$(nproc)

# Runtime stage
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    python3.10 \
    python3-pip \
    libocct-data-exchange-7.6t64 \
    libocct-foundation-7.6t64 \
    libocct-modeling-algorithms-7.6t64 \
    libocct-modeling-data-7.6t64 \
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
ENV PORT=8000

# Create data directory
RUN mkdir -p /app/backend/data

EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health').read()"

# Run
CMD ["python3", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
