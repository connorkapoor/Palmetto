"""
Palmetto - CAD Feature Recognition Tool
FastAPI main application.
"""

import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.api.routes import graph, analyze, query, aag

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown events.
    """
    # Startup
    logger.info("Starting Palmetto CAD Feature Recognition API...")
    logger.info(f"Configuration: {settings.app_name} v{settings.app_version}")
    logger.info(f"Listening on port: {os.environ.get('PORT', '8000')}")

    # Check C++ Analysis Situs engine (non-blocking)
    from app.core.cpp_engine import get_engine
    try:
        engine = get_engine()
        available = engine.check_available()
        if available:
            logger.info(f"✅ C++ Analysis Situs engine available at: {engine.engine_path}")
            modules = engine.list_modules()
            logger.info(f"Available C++ modules: {[m.get('name') for m in modules]}")
        else:
            logger.warning("⚠️  C++ engine not responding to --version check")
    except FileNotFoundError as e:
        logger.error(f"❌ C++ engine binary not found: {e}")
        logger.error("Application will start but CAD processing will not work")
    except Exception as e:
        logger.error(f"❌ C++ engine initialization failed: {e}")
        logger.error("Application will start but CAD processing may not work")

    yield

    # Shutdown
    logger.info("Shutting down...")


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Graph-based CAD feature recognition with natural language interface",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(analyze.router)  # C++ engine-based analysis
app.include_router(query.router)    # Natural language query execution
app.include_router(aag.router)      # AAG data access
app.include_router(graph.router)    # AAG graph visualization


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "description": "CAD Feature Recognition API powered by Analysis Situs C++ Engine",
        "docs": "/docs",
        "endpoints": {
            "analyze": "/api/analyze - Upload and process CAD files",
            "query": "/api/query - Natural language geometric queries",
            "aag": "/api/aag - AAG data access",
            "graph": "/api/graph - AAG graph visualization",
            "health": "/health - Health check"
        }
    }


@app.get("/health")
async def health_check():
    """
    Health check endpoint for Railway/container orchestration.
    Returns 200 OK if the API is responding.
    """
    return {
        "status": "healthy",
        "service": "palmetto-backend",
        "version": settings.app_version
    }


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler for unhandled errors."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error occurred"}
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower()
    )
