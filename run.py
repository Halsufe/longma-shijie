import sys
import os
import logging


# --- 启动前环境信息 ---
_boot_log = logging.getLogger("boot")
_boot_log.setLevel(logging.INFO)
_boot_handler = logging.StreamHandler(sys.stdout)
_boot_handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"))
_boot_log.addHandler(_boot_handler)

_boot_log.info("=" * 56)
_boot_log.info("龙马·视界  后端启动中 ...")
_boot_log.info("=" * 56)
_boot_log.info("  Python:    %s", sys.version.replace("\n", " "))
_boot_log.info("  工作目录:  %s", os.getcwd())
_boot_log.info("  脚本路径:  %s", os.path.abspath(__file__))
_boot_log.info("  父目录:    %s", os.path.dirname(os.path.abspath(__file__)))
_boot_log.info("  平台:      %s", sys.platform)
_boot_log.info("=" * 56)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def _upgrade_database() -> None:
    """Apply pending schema migrations before the local server starts."""
    from alembic import command
    from alembic.config import Config

    project_root = os.path.dirname(os.path.abspath(__file__))
    alembic_config = Config(os.path.join(project_root, "alembic.ini"))
    alembic_config.set_main_option("script_location", os.path.join(project_root, "alembic"))
    _boot_log.info("  数据库迁移: 检查并升级到最新版本")
    command.upgrade(alembic_config, "head")
    _boot_log.info("  数据库迁移: 已是最新版本")


if __name__ == "__main__":
    _upgrade_database()
    import uvicorn
    uvicorn.run(
        "backend.app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
