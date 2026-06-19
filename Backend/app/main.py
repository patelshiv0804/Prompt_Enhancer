from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.router import api_router

app = FastAPI(
    title="PromptIQ API",
    description="Backend service for prompt management and optimization",
    version="1.0.0"
)

# CORS middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health", tags=["System"])
def health_check():
    """Health check status endpoint."""
    return {"status": "healthy", "service": "PromptIQ"}

# Connect aggregated routers under /api prefix
app.include_router(api_router, prefix="/api")
