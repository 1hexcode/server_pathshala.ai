import os
import traceback

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.logging import logger


def create_application() -> FastAPI:
    """Create and configure the FastAPI application."""
    application = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        description=settings.DESCRIPTION,
        openapi_url=f"{settings.API_V1_STR}/openapi.json",
        docs_url="/docs",
        redoc_url="/redoc",
        debug=settings.DEBUG,
    )

    # Set up CORS middleware
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include API router
    application.include_router(api_router, prefix=settings.API_V1_STR)

    # Serve uploaded files locally in dev mode only
    if not settings.PRODUCTION:
        from fastapi.staticfiles import StaticFiles

        uploads_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
        os.makedirs(uploads_dir, exist_ok=True)
        application.mount("/uploads", StaticFiles(directory=uploads_dir), name="uploads")
        logger.info(f"Dev mode: serving uploads from {uploads_dir}")

    # Register exception handlers
    register_exception_handlers(application)

    return application


def register_exception_handlers(app: FastAPI) -> None:
    """Register custom exception handlers."""

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """Global exception handler - logs details to console."""
        
        # Always log to console
        logger.error(f"Exception: {exc.__class__.__name__}: {exc}")
        
        if settings.DEBUG:
            # Log detailed info to console in debug mode
            logger.error(
                f"Request: {request.method} {request.url}\n"
                f"   Path Params: {request.path_params}\n"
                f"   Query Params: {dict(request.query_params)}\n"
                f"   Client: {request.client.host if request.client else 'unknown'}\n"
                f"   Traceback:\n{traceback.format_exc()}"
            )

        # Clean response to client
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": "Internal server error",
                "message": str(exc) if settings.DEBUG else "An unexpected error occurred",
            },
        )


app = create_application()


@app.on_event("startup")
async def startup_event():
    """Initialize database and log startup information."""
    # Import models so they register with Base.metadata
    import app.models  # noqa: F401
    from app.core.database import engine, Base

    async with engine.begin() as conn:
        try:
            await conn.run_sync(Base.metadata.create_all)
        except Exception as e:
            # Ignore "already exists" errors (e.g. ENUM types on restart)
            if "already exists" in str(e):
                logger.warning(f"Some DB objects already exist (safe to ignore): {e}")
            else:
                raise

    logger.info(f"Starting {settings.PROJECT_NAME} v{settings.VERSION}")
    logger.info("Documentation: http://127.0.0.1:8000/docs")
    logger.info("ReDoc: http://127.0.0.1:8000/redoc")
    logger.info("Database connected & tables created")
    if settings.DEBUG:
        logger.warning("DEBUG mode is ON - detailed errors will be logged to console")


@app.get("/", tags=["Health"])
async def root():
    """Root endpoint - health check."""
    return {
        "message": "Welcome to Patshal.ai API",
        "version": settings.VERSION,
        "docs": "/docs",
    }


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


# Debug-only endpoint to test error handling
if settings.DEBUG:
    @app.get("/debug/error", tags=["Debug"])
    async def trigger_test_error():
        """Test endpoint to trigger an error (DEBUG mode only)."""
        raise ValueError("This is a test error to demonstrate error handling.")
