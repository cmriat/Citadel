"""
验证API路由

提供路径验证和配置验证功能。
"""

import os
from pathlib import Path
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field


router = APIRouter(prefix="/api/validate", tags=["validation"])


# ============ 请求/响应模型 ============

class PathValidationRequest(BaseModel):
    """路径验证请求"""
    path: str = Field(..., description="要验证的路径")
    check_writable: bool = Field(default=False, description="是否检查可写性")


class PathValidationResponse(BaseModel):
    """路径验证响应"""
    valid: bool = Field(..., description="路径是否有效")
    exists: bool = Field(default=False, description="路径是否存在")
    is_dir: bool = Field(default=False, description="是否为目录")
    is_file: bool = Field(default=False, description="是否为文件")
    is_writable: bool = Field(default=False, description="是否可写")
    message: str = Field(default="", description="验证消息")


class BosPathValidationRequest(BaseModel):
    """BOS路径验证请求"""
    path: str = Field(..., description="BOS路径")


class BosPathValidationResponse(BaseModel):
    """BOS路径验证响应"""
    valid: bool = Field(..., description="路径是否有效")
    format_ok: bool = Field(default=False, description="格式是否正确")
    message: str = Field(default="", description="验证消息")


class ValidationError(BaseModel):
    """验证错误"""
    field: str = Field(..., description="字段名")
    message: str = Field(..., description="错误消息")


class ConfigValidationRequest(BaseModel):
    """配置验证请求"""
    config_type: str = Field(..., description="配置类型: download, convert, upload")
    config: Dict[str, Any] = Field(..., description="配置内容")


class ConfigValidationResponse(BaseModel):
    """配置验证响应"""
    valid: bool = Field(..., description="配置是否有效")
    errors: List[ValidationError] = Field(default=[], description="错误列表")


# ============ API端点 ============

@router.post("/local-path", response_model=PathValidationResponse)
async def validate_local_path(request: PathValidationRequest):
    """
    验证本地路径

    检查路径是否存在、是否为目录、是否可写等。
    """
    path_str = request.path.strip()

    # 空路径检查
    if not path_str:
        return PathValidationResponse(
            valid=False,
            message="路径不能为空"
        )

    # 路径格式检查
    try:
        path = Path(path_str)
    except Exception as e:
        return PathValidationResponse(
            valid=False,
            message=f"路径格式无效: {str(e)}"
        )

    # 路径存在性检查
    exists = path.exists()
    is_dir = path.is_dir() if exists else False
    is_file = path.is_file() if exists else False

    # 可写性检查
    is_writable = False
    if exists and request.check_writable:
        is_writable = os.access(path, os.W_OK)

    # 构建消息
    if not exists:
        message = "路径不存在"
        valid = False
    elif is_dir:
        message = "目录存在"
        valid = True
    elif is_file:
        message = "文件存在"
        valid = True
    else:
        message = "路径存在但类型未知"
        valid = True

    return PathValidationResponse(
        valid=valid,
        exists=exists,
        is_dir=is_dir,
        is_file=is_file,
        is_writable=is_writable,
        message=message
    )


@router.post("/bos-path", response_model=BosPathValidationResponse)
async def validate_bos_path(request: BosPathValidationRequest):
    """
    验证BOS路径格式

    检查BOS路径格式是否正确。
    """
    path_str = request.path.strip()

    # 空路径检查
    if not path_str:
        return BosPathValidationResponse(
            valid=False,
            format_ok=False,
            message="BOS路径不能为空"
        )

    # 格式检查 - BOS路径应该是类似 srgdata/robot/... 的格式
    # 不需要 bos:/ 前缀，后端会自动添加

    # 检查是否包含非法字符
    invalid_chars = ['<', '>', '|', '"', '?', '*']
    for char in invalid_chars:
        if char in path_str:
            return BosPathValidationResponse(
                valid=False,
                format_ok=False,
                message=f"路径包含非法字符: {char}"
            )

    # 规范化路径（去除多余斜杠）
    normalized = '/'.join(filter(None, path_str.split('/')))

    # 检查是否以斜杠开头（不应该）
    if path_str.startswith('/'):
        return BosPathValidationResponse(
            valid=True,
            format_ok=True,
            message=f"路径已规范化为: {normalized}"
        )

    return BosPathValidationResponse(
        valid=True,
        format_ok=True,
        message="BOS路径格式正确"
    )


@router.post("/config", response_model=ConfigValidationResponse)
async def validate_config(request: ConfigValidationRequest):
    """
    验证配置参数

    根据配置类型验证各参数的有效性。
    """
    errors: List[ValidationError] = []
    config = request.config
    config_type = request.config_type

    # 通用验证：并发数
    if 'concurrency' in config:
        concurrency = config['concurrency']
        if not isinstance(concurrency, int) or concurrency < 1 or concurrency > 20:
            errors.append(ValidationError(
                field='concurrency',
                message='并发数必须在 1-20 之间'
            ))

    # 下载配置验证
    if config_type == 'download':
        if 'bos_path' in config and not config['bos_path'].strip():
            errors.append(ValidationError(
                field='bos_path',
                message='BOS路径不能为空'
            ))
        if 'local_path' in config and not config['local_path'].strip():
            errors.append(ValidationError(
                field='local_path',
                message='本地路径不能为空'
            ))

    # 转换配置验证
    elif config_type == 'convert':
        if 'input_dir' in config and not config['input_dir'].strip():
            errors.append(ValidationError(
                field='input_dir',
                message='输入目录不能为空'
            ))
        if 'output_dir' in config and not config['output_dir'].strip():
            errors.append(ValidationError(
                field='output_dir',
                message='输出目录不能为空'
            ))
        if 'fps' in config:
            fps = config['fps']
            if not isinstance(fps, int) or fps < 1 or fps > 120:
                errors.append(ValidationError(
                    field='fps',
                    message='帧率必须在 1-120 之间'
                ))
        if 'parallel_jobs' in config:
            jobs = config['parallel_jobs']
            if not isinstance(jobs, int) or jobs < 1 or jobs > 16:
                errors.append(ValidationError(
                    field='parallel_jobs',
                    message='并行任务数必须在 1-16 之间'
                ))

    # 上传配置验证
    elif config_type == 'upload':
        if 'local_dir' in config and not config['local_dir'].strip():
            errors.append(ValidationError(
                field='local_dir',
                message='本地目录不能为空'
            ))
        if 'bos_path' in config and not config['bos_path'].strip():
            errors.append(ValidationError(
                field='bos_path',
                message='BOS路径不能为空'
            ))

    return ConfigValidationResponse(
        valid=len(errors) == 0,
        errors=errors
    )


@router.get("/check-path")
async def check_path_quick(path: str):
    """
    快速检查路径（GET方法，方便前端调用）
    """
    if not path or not path.strip():
        return {"valid": False, "exists": False, "message": "路径为空"}

    path_obj = Path(path.strip())
    exists = path_obj.exists()

    return {
        "valid": exists,
        "exists": exists,
        "is_dir": path_obj.is_dir() if exists else False,
        "message": "路径存在" if exists else "路径不存在"
    }
