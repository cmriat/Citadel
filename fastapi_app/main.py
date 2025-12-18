"""FastAPI main application"""

import logging
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

from .routers import config, scanner, worker, monitor
from .services.scanner_service import scanner_service
from .services.worker_service import worker_service

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# 前端静态文件目录
frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger.info("Starting LeRobot Converter API...")
    yield
    # 关闭时停止后台服务
    logger.info("Shutting down...")
    scanner_service.stop()
    worker_service.stop()
    logger.info("Shutdown complete")


app = FastAPI(
    title="LeRobot Converter API",
    description="API for managing LeRobot data conversion",
    version="1.0.0",
    lifespan=lifespan
)

# CORS 配置（开发环境允许所有来源）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 健康检查（放在路由注册之前）
@app.get("/api/health")
async def health_check():
    """健康检查"""
    return {"status": "ok", "service": "lerobot-converter"}


# 注册路由
app.include_router(config.router, prefix="/api/config", tags=["Config"])
app.include_router(scanner.router, prefix="/api/scanner", tags=["Scanner"])
app.include_router(worker.router, prefix="/api/worker", tags=["Worker"])
app.include_router(monitor.router, prefix="/api", tags=["Monitor"])

# 静态文件服务（生产环境提供前端文件）
if frontend_dist.exists():
    # 挂载静态资源目录
    app.mount("/assets", StaticFiles(directory=str(frontend_dist / "assets")), name="assets")
    logger.info(f"Serving static files from {frontend_dist}")

    # SPA fallback: 所有非 API 路由返回 index.html
    @app.get("/{full_path:path}")
    async def serve_spa(request: Request, full_path: str):
        """Serve index.html for SPA routes"""
        # 检查是否是静态文件
        file_path = frontend_dist / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        # 否则返回 index.html (SPA 路由)
        return FileResponse(frontend_dist / "index.html")
