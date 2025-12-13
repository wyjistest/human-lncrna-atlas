"""
批次管理模块
=============

功能:
- 创建导入批次
- 追踪导入状态
- 失败回滚
- 数据质量检查

版本: v2.3
日期: 2025-11-20
"""

import os
import psycopg2
from psycopg2 import sql
from typing import Optional, Dict, List
import logging
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

VALID_SQL_IDENTIFIER = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')

def validate_sql_identifier(name: str, max_length: int = 63) -> str:
    """Validate SQL identifier to prevent injection"""
    if not name or not VALID_SQL_IDENTIFIER.match(name) or len(name) > max_length:
        raise ValueError(f"Invalid SQL identifier: {name}")
    return name


class BatchManager:
    """
    批次管理器 - 提供数据导入的批次追踪和回滚能力

    Usage:
        with BatchManager(conn, "Human Regulations Import") as batch:
            batch.insert_regulations(data)
            batch.commit()  # 成功

        # 或者失败自动回滚:
        with BatchManager(conn, "Import") as batch:
            batch.insert_regulations(data)
            raise Exception("Error")  # 自动回滚
    """

    def __init__(self, connection, batch_name: str, batch_type: str,
                 species_id: Optional[int] = None, source_file: Optional[str] = None):
        """
        初始化批次管理器

        Args:
            connection: psycopg2 connection对象
            batch_name: 批次名称（如 "Human Regulations 2025-11-20"）
            batch_type: 批次类型（regulations, traits, genes, repeatmasker等）
            species_id: 物种ID（如果适用）
            source_file: 源文件路径
        """
        self.conn = connection
        self.batch_name = batch_name
        self.batch_type = batch_type
        self.species_id = species_id
        self.source_file = source_file
        self.batch_id: Optional[int] = None
        self.record_count = 0

    def __enter__(self):
        """上下文管理器入口 - 创建批次"""
        self._create_batch()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口 - 自动提交或回滚"""
        if exc_type is not None:
            # 发生异常，回滚
            logger.error(f"批次 {self.batch_id} 导入失败: {exc_val}")
            self._rollback_batch()
            return False  # 传播异常
        else:
            # 正常退出但未显式commit
            if self.record_count == 0:
                logger.warning(f"批次 {self.batch_id} 未导入任何数据")
            logger.info(f"批次 {self.batch_id} 自动提交")
            self._complete_batch()
            return True

    def _create_batch(self):
        """创建批次记录"""
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO import_batches
                    (batch_name, batch_type, species_id, source_file, status, created_at)
                VALUES (%s, %s, %s, %s, 'in_progress', NOW())
                RETURNING batch_id
            """, (self.batch_name, self.batch_type, self.species_id, self.source_file))

            self.batch_id = cur.fetchone()[0]
            self.conn.commit()
            logger.info(f"创建批次 {self.batch_id}: {self.batch_name}")

    def _complete_batch(self):
        """标记批次完成"""
        if self.batch_id is None:
            raise RuntimeError("批次未创建")

        with self.conn.cursor() as cur:
            cur.execute("""
                UPDATE import_batches
                SET status = 'completed',
                    record_count = %s,
                    completed_at = NOW()
                WHERE batch_id = %s
            """, (self.record_count, self.batch_id))

            self.conn.commit()
            logger.info(f"批次 {self.batch_id} 完成，共导入 {self.record_count} 条记录")

    def _rollback_batch(self):
        """回滚批次 - 删除所有关联数据"""
        if self.batch_id is None:
            logger.warning("批次未创建，无需回滚")
            return

        try:
            with self.conn.cursor() as cur:
                # 1. 先删除sequences表数据（必须在删除regulations之前）
                cur.execute("""
                    DELETE FROM sequences
                    WHERE regulation_id IN (
                        SELECT regulation_id FROM regulations WHERE batch_id = %s
                    )
                """, (self.batch_id,))
                deleted_seqs = cur.rowcount

                # 2. 再删除regulations表数据
                cur.execute("DELETE FROM regulations WHERE batch_id = %s", (self.batch_id,))
                deleted_regs = cur.rowcount

                # 3. 标记批次失败
                cur.execute("""
                    UPDATE import_batches
                    SET status = 'failed',
                        record_count = 0,
                        completed_at = NOW()
                    WHERE batch_id = %s
                """, (self.batch_id,))

                self.conn.commit()
                logger.info(f"批次 {self.batch_id} 回滚完成: "
                           f"删除 {deleted_seqs} sequences, {deleted_regs} regulations")

        except Exception as e:
            logger.error(f"回滚批次 {self.batch_id} 失败: {e}")
            self.conn.rollback()
            raise

    def commit(self):
        """显式提交批次"""
        self._complete_batch()

    def add_records(self, count: int):
        """增加记录计数"""
        self.record_count += count

    def get_batch_id(self) -> int:
        """获取批次ID"""
        if self.batch_id is None:
            raise RuntimeError("批次未创建")
        return self.batch_id


class DataQualityChecker:
    """
    数据质量检查器

    功能:
    - 检查必填字段非空
    - 检查重复数据
    - 检查外键完整性
    - 检查数值范围
    """

    def __init__(self, connection):
        self.conn = connection
        self.issues: List[Dict] = []

    def check_required_fields(self, table: str, columns: List[str]) -> int:
        """
        检查必填字段非空

        Returns:
            问题记录数量
        """
        # Validate table and column names to prevent SQL injection
        validated_table = validate_sql_identifier(table)

        with self.conn.cursor() as cur:
            for col in columns:
                validated_col = validate_sql_identifier(col)
                query = sql.SQL("""
                    SELECT COUNT(*)
                    FROM {table}
                    WHERE {column} IS NULL
                """).format(
                    table=sql.Identifier(validated_table),
                    column=sql.Identifier(validated_col),
                )
                cur.execute(query)
                null_count = cur.fetchone()[0]

                if null_count > 0:
                    issue = {
                        'table': validated_table,
                        'column': validated_col,
                        'type': 'null_value',
                        'count': null_count
                    }
                    self.issues.append(issue)
                    logger.warning(f"发现 {null_count} 条记录的 {validated_table}.{validated_col} 为NULL")

        return len(self.issues)

    def check_duplicates(self, table: str, unique_columns: List[str]) -> int:
        """
        检查重复记录

        Args:
            table: 表名
            unique_columns: 应唯一的列组合

        Returns:
            重复记录数量
        """
        # Validate table and column names to prevent SQL injection
        validated_table = validate_sql_identifier(table)
        validated_columns = [validate_sql_identifier(col) for col in unique_columns]
        cols_str = ', '.join(validated_columns)
        cols_sql = sql.SQL(", ").join(sql.Identifier(col) for col in validated_columns)

        with self.conn.cursor() as cur:
            query = sql.SQL("""
                SELECT {cols}, COUNT(*)
                FROM {table}
                GROUP BY {cols}
                HAVING COUNT(*) > 1
            """).format(
                cols=cols_sql,
                table=sql.Identifier(validated_table),
            )
            cur.execute(query)

            duplicates = cur.fetchall()

            if duplicates:
                issue = {
                    'table': validated_table,
                    'type': 'duplicate',
                    'columns': validated_columns,
                    'count': len(duplicates)
                }
                self.issues.append(issue)
                logger.warning(f"发现 {len(duplicates)} 组重复数据在 {validated_table}({cols_str})")

        return len(duplicates)

    def check_foreign_key_integrity(self, table: str, fk_column: str,
                                    ref_table: str, ref_column: str) -> int:
        """
        检查外键完整性（未被数据库约束捕获的孤立记录）

        Returns:
            孤立记录数量
        """
        # Validate identifiers to prevent SQL injection
        validated_table = validate_sql_identifier(table)
        validated_fk_column = validate_sql_identifier(fk_column)
        validated_ref_table = validate_sql_identifier(ref_table)
        validated_ref_column = validate_sql_identifier(ref_column)

        with self.conn.cursor() as cur:
            query = sql.SQL("""
                SELECT COUNT(*)
                FROM {table} AS t
                WHERE t.{fk_column} IS NOT NULL
                  AND NOT EXISTS (
                    SELECT 1 FROM {ref_table} AS r
                    WHERE r.{ref_column} = t.{fk_column}
                  )
            """).format(
                table=sql.Identifier(validated_table),
                fk_column=sql.Identifier(validated_fk_column),
                ref_table=sql.Identifier(validated_ref_table),
                ref_column=sql.Identifier(validated_ref_column),
            )
            cur.execute(query)

            orphan_count = cur.fetchone()[0]

            if orphan_count > 0:
                issue = {
                    'table': validated_table,
                    'type': 'orphan_fk',
                    'fk_column': validated_fk_column,
                    'ref_table': validated_ref_table,
                    'count': orphan_count
                }
                self.issues.append(issue)
                logger.warning(f"发现 {orphan_count} 条孤立外键在 {validated_table}.{validated_fk_column}")

        return orphan_count

    def check_value_range(self, table: str, column: str,
                         min_value: float, max_value: float) -> int:
        """
        检查数值范围

        Returns:
            超出范围的记录数量
        """
        # Validate identifiers to prevent SQL injection
        validated_table = validate_sql_identifier(table)
        validated_column = validate_sql_identifier(column)

        with self.conn.cursor() as cur:
            query = sql.SQL("""
                SELECT COUNT(*)
                FROM {table}
                WHERE {column} < %s OR {column} > %s
            """).format(
                table=sql.Identifier(validated_table),
                column=sql.Identifier(validated_column),
            )
            cur.execute(query, (min_value, max_value))

            out_of_range = cur.fetchone()[0]

            if out_of_range > 0:
                issue = {
                    'table': validated_table,
                    'column': validated_column,
                    'type': 'out_of_range',
                    'range': (min_value, max_value),
                    'count': out_of_range
                }
                self.issues.append(issue)
                logger.warning(f"发现 {out_of_range} 条记录超出范围在 {validated_table}.{validated_column}")

        return out_of_range

    def generate_report(self) -> str:
        """生成质量检查报告"""
        if not self.issues:
            return "✅ 数据质量检查通过，未发现问题"

        report = f"⚠️ 数据质量检查发现 {len(self.issues)} 个问题:\n\n"

        for i, issue in enumerate(self.issues, 1):
            report += f"{i}. {issue['type']} in {issue['table']}: {issue['count']} records\n"
            report += f"   详情: {issue}\n\n"

        return report


# 使用示例
if __name__ == "__main__":
    # 连接数据库
    conn = psycopg2.connect(
        host=os.getenv("PGHOST", "localhost"),
        database=os.getenv("PGDATABASE", "lncrna_network"),
        user=os.getenv("PGUSER", "postgres"),
        password=os.getenv("PGPASSWORD", ""),
    )

    # 示例1: 使用批次管理器
    try:
        with BatchManager(conn, "Test Import", "regulations", species_id=1) as batch:
            # 导入数据（伪代码）
            # batch.add_records(1000)
            batch.commit()
    except Exception as e:
        logger.error(f"导入失败: {e}")

    # 示例2: 数据质量检查
    checker = DataQualityChecker(conn)
    checker.check_required_fields('genes', ['gene_name', 'gene_ensembl_id'])
    checker.check_duplicates('genes', ['species_id', 'gene_ensembl_id'])
    checker.check_foreign_key_integrity('regulations', 'lncrna_gene_id', 'genes', 'gene_id')
    checker.check_value_range('regulations', 'binding_affinity', 0, 1000)

    print(checker.generate_report())

    conn.close()
