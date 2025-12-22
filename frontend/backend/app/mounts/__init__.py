"""
Application mount points

Phase 9.16: 静态文件挂载模块
"""
from app.mounts.genomes import mount_genomes_app

__all__ = ["mount_genomes_app"]
