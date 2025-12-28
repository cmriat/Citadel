"""
Citadel Release - 后端API服务

FastAPI应用入口，提供任务管理、下载和转换API。
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.routers import tasks, download, convert

# 创建FastAPI应用
app = FastAPI(
    title="Citadel Release API",
    description="BOS下载和HDF5转换管理系统API",
    version="0.2.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# 配置CORS（允许前端跨域访问）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应该限制具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(tasks.router)
app.include_router(download.router)
app.include_router(convert.router)


@app.get("/")
async def root():
    """API根路径"""
    return {
        "name": "Citadel Release API",
        "version": "0.2.0",
        "docs": "/docs",
        "endpoints": {
            "tasks": "/api/tasks",
            "download": "/api/download",
            "convert": "/api/convert"
        }
    }


@app.get("/health")
async def health():
    """健康检查"""
    from backend.services.download_service import get_download_service
    from backend.services.database import get_database

    # 检查数据库
    try:
        db = get_database()
        db.count()
        db_ok = True
    except Exception as e:
        db_ok = False

    # 检查mc工具
    service = get_download_service()
    mc_ok, _ = service.check_mc()
    bos_ok, _ = service.check_connection()

    return {
        "status": "healthy" if (db_ok and mc_ok) else "degraded",
        "checks": {
            "database": db_ok,
            "mc_tool": mc_ok,
            "bos_connection": bos_ok
        }
    }


@app.get("/api/stats")
async def stats():
    """系统统计"""
    from backend.services.database import get_database
    from backend.models.task import TaskStatus, TaskType

    db = get_database()

    return {
        "tasks": {
            "total": db.count(),
            "pending": db.count(status=TaskStatus.PENDING),
            "running": db.count(status=TaskStatus.RUNNING),
            "completed": db.count(status=TaskStatus.COMPLETED),
            "failed": db.count(status=TaskStatus.FAILED),
            "cancelled": db.count(status=TaskStatus.CANCELLED)
        },
        "by_type": {
            "download": db.count(task_type=TaskType.DOWNLOAD),
            "convert": db.count(task_type=TaskType.CONVERT)
        }
    }


# 启动时初始化
@app.on_event("startup")
async def startup():
    """应用启动时执行"""
    from backend.services.database import get_database

    # 初始化数据库
    db = get_database()
    print(f"✓ 数据库已初始化: {db.db_path}")

    # 检查mc工具
    from backend.services.download_service import get_download_service
    service = get_download_service()
    mc_ok, mc_msg = service.check_mc()
    if mc_ok:
        print(f"✓ mc工具可用: {mc_msg}")
    else:
        print(f"⚠ mc工具不可用: {mc_msg}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
