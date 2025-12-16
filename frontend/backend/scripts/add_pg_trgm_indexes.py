"""
添加 pg_trgm GIN 索引以优化 ILIKE 模糊搜索

问题背景：
- ILIKE '%pattern%' 查询默认使用全表扫描
- 当 traits 表有大量数据时，疾病名称搜索变得很慢

解决方案：
- 使用 PostgreSQL pg_trgm 扩展
- 创建 GIN 索引支持模糊匹配

运行方式：
    python3 scripts/add_pg_trgm_indexes.py

或在代码中调用：
    from scripts.add_pg_trgm_indexes import create_trgm_indexes
    create_trgm_indexes(db_session)
"""
import sys
from pathlib import Path

# 添加 backend 目录到 Python 路径
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from app.core.config import settings  # noqa: E402


def create_trgm_indexes(db_session=None):
    """
    创建 pg_trgm GIN 索引

    Args:
        db_session: 可选的数据库会话，如果不提供则自动创建

    Returns:
        bool: 成功返回 True
    """
    close_session = False
    if db_session is None:
        engine = create_engine(settings.database_url)
        Session = sessionmaker(bind=engine)
        db_session = Session()
        close_session = True

    try:
        print("Step 1: 启用 pg_trgm 扩展...")
        db_session.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        db_session.commit()
        print("  ✓ pg_trgm 扩展已启用")

        print("\nStep 2: 创建 GIN 索引...")

        # 索引 1: traits.trait_name
        print("  创建 idx_traits_trait_name_trgm...")
        db_session.execute(text("DROP INDEX IF EXISTS idx_traits_trait_name_trgm"))
        db_session.execute(text("""
            CREATE INDEX idx_traits_trait_name_trgm
            ON traits USING GIN (trait_name gin_trgm_ops)
        """))
        db_session.commit()
        print("  ✓ idx_traits_trait_name_trgm 创建成功")

        # 索引 2: chipseq_experiments.cell_type
        print("  创建 idx_chipseq_experiments_cell_type_trgm...")
        db_session.execute(text("DROP INDEX IF EXISTS idx_chipseq_experiments_cell_type_trgm"))
        db_session.execute(text("""
            CREATE INDEX idx_chipseq_experiments_cell_type_trgm
            ON chipseq_experiments USING GIN (cell_type gin_trgm_ops)
        """))
        db_session.commit()
        print("  ✓ idx_chipseq_experiments_cell_type_trgm 创建成功")

        print("\nStep 3: 更新表统计信息...")
        db_session.execute(text("ANALYZE traits"))
        db_session.execute(text("ANALYZE chipseq_experiments"))
        db_session.commit()
        print("  ✓ 表统计信息已更新")

        # 验证
        print("\nStep 4: 验证索引...")
        result = db_session.execute(text("""
            SELECT indexname, tablename, indexdef
            FROM pg_indexes
            WHERE indexname IN (
                'idx_traits_trait_name_trgm',
                'idx_chipseq_experiments_cell_type_trgm'
            )
        """))
        indexes = list(result)

        if len(indexes) == 2:
            print(f"  ✓ 成功创建 {len(indexes)} 个 pg_trgm GIN 索引")
            for idx in indexes:
                print(f"    - {idx.indexname} on {idx.tablename}")
            return True
        else:
            print(f"  ⚠ 预期 2 个索引，实际找到 {len(indexes)} 个")
            return False

    except Exception as e:
        print(f"\n❌ 错误: {e}")
        db_session.rollback()
        return False

    finally:
        if close_session:
            db_session.close()


def verify_index_usage():
    """
    验证索引是否被查询规划器使用

    运行示例查询并检查执行计划
    """
    engine = create_engine(settings.database_url)
    Session = sessionmaker(bind=engine)
    db = Session()

    try:
        print("\n验证索引使用情况:")
        print("-" * 60)

        # 测试 traits.trait_name
        result = db.execute(text("""
            EXPLAIN (FORMAT TEXT)
            SELECT * FROM traits WHERE trait_name ILIKE '%diabetes%' LIMIT 10
        """))
        plan = "\n".join(row[0] for row in result)

        if "idx_traits_trait_name_trgm" in plan or "Bitmap Index Scan" in plan:
            print("✓ traits.trait_name 查询使用了索引")
        else:
            print("⚠ traits.trait_name 查询可能未使用索引（数据量小时正常）")
        print(f"  执行计划: {plan.split(chr(10))[0]}")

        print("-" * 60)

        # 测试 chipseq_experiments.cell_type
        result = db.execute(text("""
            EXPLAIN (FORMAT TEXT)
            SELECT * FROM chipseq_experiments WHERE cell_type ILIKE '%liver%' LIMIT 10
        """))
        plan = "\n".join(row[0] for row in result)

        if "idx_chipseq_experiments_cell_type_trgm" in plan or "Bitmap Index Scan" in plan:
            print("✓ chipseq_experiments.cell_type 查询使用了索引")
        else:
            print("⚠ chipseq_experiments.cell_type 查询可能未使用索引（数据量小时正常）")
        print(f"  执行计划: {plan.split(chr(10))[0]}")

    finally:
        db.close()


if __name__ == "__main__":
    print("=" * 60)
    print("pg_trgm GIN 索引迁移脚本")
    print("=" * 60)
    print()

    success = create_trgm_indexes()

    if success:
        print("\n" + "=" * 60)
        verify_index_usage()
        print("\n✅ 迁移完成!")
    else:
        print("\n❌ 迁移失败，请检查错误信息")
        sys.exit(1)
