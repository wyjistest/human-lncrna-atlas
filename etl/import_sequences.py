#!/usr/bin/env python3
"""
补充导入序列数据到 sequences 表
从源文件读取 LncRNA_Sequence 和 DNA_Sequence，匹配已有的 regulations 记录

安全改进：
- 数据库连接信息通过环境变量或命令行参数配置
- 使用 with 语句管理 cursor 资源
- 事务支持回滚
- 完善的异常处理

使用示例：
  # 使用环境变量
  export DB_HOST=localhost DB_PORT=5432 DB_USER=amax DB_PASSWORD=xxx DB_NAME=lncrna_production
  python3 import_sequences.py --species 1

  # 使用命令行参数
  python3 import_sequences.py --host localhost --user amax --password xxx --dbname lncrna_production --species 1

  # 预览模式（不实际导入）
  python3 import_sequences.py --species 1 --dry-run
"""

import os
import csv
import sys
import logging
import argparse
from typing import Dict, List, Tuple, Optional
from contextlib import contextmanager

import psycopg2
from psycopg2.extras import execute_batch

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_db_config_from_env() -> Dict[str, any]:
    """
    从环境变量获取数据库配置

    Returns:
        数据库配置字典
    """
    return {
        "host": os.environ.get("DB_HOST", "localhost"),
        "port": int(os.environ.get("DB_PORT", "5432")),
        "user": os.environ.get("DB_USER", ""),
        "password": os.environ.get("DB_PASSWORD", ""),
        "dbname": os.environ.get("DB_NAME", "lncrna_production"),
    }


def get_source_files() -> Dict[int, str]:
    """
    获取源文件路径配置

    优先使用环境变量，否则报错（必填配置）

    Returns:
        物种ID到文件路径的映射

    Raises:
        ValueError: 如果未设置 LNCRNA_DATA_PATH 环境变量
    """
    base_path = os.environ.get("LNCRNA_DATA_PATH")
    if base_path is None:
        raise ValueError("LNCRNA_DATA_PATH environment variable is required")
    return {
        1: os.path.join(base_path, "human_batch_human.txt"),
        2: os.path.join(base_path, "chimp_batch_BA50.txt"),
        3: os.path.join(base_path, "macaque_batch_BA50.txt"),
        4: os.path.join(base_path, "marmoset_batch_BA50.txt"),
    }


# 物种名到 ID 的映射
SPECIES_MAP = {
    'human': 1,
    'chimp': 2,
    'macaque': 3,
    'marmoset': 4,
}


@contextmanager
def get_cursor(conn):
    """
    游标上下文管理器，确保资源正确释放

    Args:
        conn: 数据库连接

    Yields:
        数据库游标
    """
    cursor = conn.cursor()
    try:
        yield cursor
    finally:
        cursor.close()


def strip_version(gene_id: str) -> str:
    """
    去掉基因 ID 的版本号，如 ENSG00000129484.9 -> ENSG00000129484

    支持 ENSG 和 CATG 格式

    Args:
        gene_id: 基因 ID 字符串

    Returns:
        去除版本号后的基因 ID
    """
    if '.' in gene_id and (gene_id.startswith('ENSG') or gene_id.startswith('CATG')):
        return gene_id.rsplit('.', 1)[0]
    return gene_id


def get_gene_id_map(conn, species_id: int) -> Dict[str, int]:
    """
    获取基因名到 gene_id 的映射

    建立多种格式的映射，以处理不同的基因 ID 格式：
    - 原始 ID
    - 去掉物种后缀（如 _marmoset）
    - 去掉版本号（如 .9）

    Args:
        conn: 数据库连接
        species_id: 物种 ID

    Returns:
        基因 Ensembl ID 到 gene_id 的映射字典
    """
    with get_cursor(conn) as cursor:
        cursor.execute("""
            SELECT gene_ensembl_id, gene_id
            FROM genes
            WHERE species_id = %s
        """, (species_id,))

        result = {}
        for row in cursor.fetchall():
            ensembl_id, gene_id = row
            result[ensembl_id] = gene_id

            # 去掉物种后缀的映射
            base_id = ensembl_id
            for suffix in ['_human', '_chimp', '_macaque', '_marmoset', '_chimpanzee']:
                if ensembl_id.endswith(suffix):
                    base_id = ensembl_id[:-len(suffix)]
                    result[base_id] = gene_id
                    break

            # 也建立去掉版本号的映射
            no_ver = strip_version(base_id)
            if no_ver != base_id:
                result[no_ver] = gene_id

        return result


def lookup_gene(gene_map: Dict[str, int], gene_id: str) -> Optional[int]:
    """
    查找基因 ID，尝试多种格式

    Args:
        gene_map: 基因映射字典
        gene_id: 要查找的基因 ID

    Returns:
        gene_id 或 None
    """
    # 先直接查找
    if gene_id in gene_map:
        return gene_map[gene_id]

    # 尝试去掉版本号查找
    no_ver = strip_version(gene_id)
    if no_ver in gene_map:
        return gene_map[no_ver]

    return None


def get_regulation_map(conn, species_id: int) -> Dict[Tuple, int]:
    """
    获取 regulation 唯一键到 regulation_id 的映射

    Args:
        conn: 数据库连接
        species_id: 物种 ID

    Returns:
        (lnc_id, tgt_id, lnc_start, lnc_end, dna_start, dna_end) -> regulation_id 映射
    """
    with get_cursor(conn) as cursor:
        cursor.execute("""
            SELECT regulation_id, lncrna_gene_id, target_gene_id,
                   lncrna_start, lncrna_end, dna_start, dna_end
            FROM regulations
            WHERE species_id = %s
        """, (species_id,))

        result = {}
        for row in cursor.fetchall():
            reg_id, lnc_id, tgt_id, lnc_start, lnc_end, dna_start, dna_end = row
            key = (lnc_id, tgt_id, lnc_start, lnc_end, dna_start, dna_end)
            result[key] = reg_id
        return result


def insert_sequences(conn, sequences: List[Tuple], dry_run: bool = False) -> int:
    """
    批量插入序列数据

    Args:
        conn: 数据库连接
        sequences: 序列数据列表 [(regulation_id, lncrna_sequence, dna_sequence), ...]
        dry_run: 预览模式，不实际插入

    Returns:
        插入的记录数
    """
    if dry_run:
        logger.info(f"[DRY-RUN] 将插入 {len(sequences)} 条序列记录")
        return len(sequences)

    with get_cursor(conn) as cursor:
        execute_batch(cursor, """
            INSERT INTO sequences (regulation_id, lncrna_sequence, dna_sequence)
            VALUES (%s, %s, %s)
            ON CONFLICT (regulation_id) DO UPDATE SET
                lncrna_sequence = EXCLUDED.lncrna_sequence,
                dna_sequence = EXCLUDED.dna_sequence
        """, sequences, page_size=1000)
        # 不在这里 commit，由调用者统一管理事务
        return len(sequences)


def process_file(
    conn,
    species_id: int,
    filepath: str,
    batch_size: int = 5000,
    dry_run: bool = False
) -> Dict[str, int]:
    """
    处理单个源文件，导入序列数据

    Args:
        conn: 数据库连接
        species_id: 物种 ID
        filepath: 源文件路径
        batch_size: 批量插入大小
        dry_run: 预览模式

    Returns:
        处理统计信息字典
    """
    logger.info(f"处理文件: {filepath}")
    logger.info(f"物种 ID: {species_id}")

    stats = {
        "matched": 0,
        "not_matched": 0,
        "empty_seq": 0,
        "inserted": 0,
        "errors": 0,
    }

    # 获取映射
    logger.info("加载基因映射...")
    gene_map = get_gene_id_map(conn, species_id)
    logger.info(f"  基因数: {len(gene_map)}")

    logger.info("加载 regulation 映射...")
    reg_map = get_regulation_map(conn, species_id)
    logger.info(f"  Regulation 数: {len(reg_map)}")

    # 读取文件并匹配
    sequences = []

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter='\t')

            for i, row in enumerate(reader, 1):
                try:
                    lncrna_id = row.get('LncRNA_ID', '').strip()
                    target_id = row.get('Target_Gene_ID', '').strip()
                    lncrna_seq = row.get('LncRNA_Sequence', '').strip()
                    dna_seq = row.get('DNA_Sequence', '').strip()

                    # 跳过空序列
                    if (not lncrna_seq or lncrna_seq == 'None') and (not dna_seq or dna_seq == 'None'):
                        stats["empty_seq"] += 1
                        continue

                    # 清理 None 值
                    if lncrna_seq == 'None':
                        lncrna_seq = None
                    if dna_seq == 'None':
                        dna_seq = None

                    # 获取 gene_id
                    lnc_gene_id = lookup_gene(gene_map, lncrna_id)
                    tgt_gene_id = lookup_gene(gene_map, target_id)

                    if not lnc_gene_id or not tgt_gene_id:
                        stats["not_matched"] += 1
                        continue

                    # 获取位置信息
                    try:
                        lnc_start = int(row.get('LncRNA_Start', 0))
                        lnc_end = int(row.get('LncRNA_End', 0))
                        dna_start = int(row.get('DNA_Start', 0))
                        dna_end = int(row.get('DNA_End', 0))
                    except (ValueError, TypeError):
                        stats["not_matched"] += 1
                        continue

                    # 查找 regulation_id
                    key = (lnc_gene_id, tgt_gene_id, lnc_start, lnc_end, dna_start, dna_end)
                    reg_id = reg_map.get(key)

                    if not reg_id:
                        stats["not_matched"] += 1
                        continue

                    stats["matched"] += 1
                    sequences.append((reg_id, lncrna_seq, dna_seq))

                    # 批量插入
                    if len(sequences) >= batch_size:
                        inserted = insert_sequences(conn, sequences, dry_run)
                        stats["inserted"] += inserted
                        logger.info(f"  已处理: {i:,} 行, 匹配: {stats['matched']:,}, 插入: {stats['inserted']:,}")
                        sequences = []

                except Exception as e:
                    stats["errors"] += 1
                    if stats["errors"] <= 10:
                        logger.warning(f"第 {i} 行处理错误: {e}")

                if i % 50000 == 0:
                    logger.info(f"  进度: {i:,} 行...")

        # 插入剩余数据
        if sequences:
            inserted = insert_sequences(conn, sequences, dry_run)
            stats["inserted"] += inserted

        logger.info(f"完成! 匹配: {stats['matched']:,}, 未匹配: {stats['not_matched']:,}, "
                   f"空序列: {stats['empty_seq']:,}, 错误: {stats['errors']:,}")

    except Exception as e:
        logger.error(f"处理文件时发生错误: {e}")
        raise

    return stats


def main():
    parser = argparse.ArgumentParser(
        description='补充导入序列数据到 sequences 表',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 使用环境变量配置数据库
  export DB_HOST=localhost DB_USER=amax DB_PASSWORD=xxx
  python3 import_sequences.py --species 1

  # 使用命令行参数
  python3 import_sequences.py --host localhost --user amax --password xxx --species 1

  # 预览模式
  python3 import_sequences.py --species 1 --dry-run
        """
    )

    # 数据库配置参数
    parser.add_argument('--host', type=str, help='数据库主机 (或设置 DB_HOST 环境变量)')
    parser.add_argument('--port', type=int, help='数据库端口 (或设置 DB_PORT 环境变量)')
    parser.add_argument('--user', type=str, help='数据库用户 (或设置 DB_USER 环境变量)')
    parser.add_argument('--password', type=str, help='数据库密码 (或设置 DB_PASSWORD 环境变量)')
    parser.add_argument('--dbname', type=str, help='数据库名称 (或设置 DB_NAME 环境变量)')

    # 导入选项
    parser.add_argument('--species', type=int, choices=[1, 2, 3, 4],
                        help='指定物种 ID (1=Human, 2=Chimp, 3=Macaque, 4=Marmoset)')
    parser.add_argument('--file', type=str, help='指定源文件路径（覆盖默认路径）')
    parser.add_argument('--batch-size', type=int, default=5000, help='批量插入大小 (默认: 5000)')
    parser.add_argument('--dry-run', action='store_true', help='预览模式，不实际导入数据')

    args = parser.parse_args()

    # 构建数据库配置（命令行参数优先于环境变量）
    db_config = get_db_config_from_env()
    if args.host:
        db_config['host'] = args.host
    if args.port:
        db_config['port'] = args.port
    if args.user:
        db_config['user'] = args.user
    if args.password:
        db_config['password'] = args.password
    if args.dbname:
        db_config['dbname'] = args.dbname

    # 验证必要的配置
    if not db_config['user']:
        logger.error("必须提供数据库用户名（--user 参数或 DB_USER 环境变量）")
        sys.exit(1)

    # 移除空密码键（使用 .pgpass 认证）
    if not db_config['password']:
        del db_config['password']

    # 获取源文件配置
    source_files = get_source_files()
    if args.file and args.species:
        source_files[args.species] = args.file

    conn = None
    try:
        logger.info(f"连接数据库: {db_config['host']}:{db_config['port']}/{db_config['dbname']}")
        conn = psycopg2.connect(**db_config)

        # 使用事务
        conn.autocommit = False

        # 检查当前 sequences 表状态
        with get_cursor(conn) as cursor:
            cursor.execute("SELECT COUNT(*) FROM sequences")
            before_count = cursor.fetchone()[0]
        logger.info(f"当前 sequences 表记录数: {before_count:,}")

        total_stats = {
            "matched": 0,
            "inserted": 0,
            "not_matched": 0,
            "empty_seq": 0,
            "errors": 0,
        }

        if args.species:
            # 处理指定物种
            filepath = source_files.get(args.species)
            if filepath and os.path.exists(filepath):
                stats = process_file(conn, args.species, filepath, args.batch_size, args.dry_run)
                for key in total_stats:
                    total_stats[key] += stats.get(key, 0)
            else:
                logger.error(f"文件不存在: {filepath}")
                sys.exit(1)
        else:
            # 处理所有物种
            for species_id, filepath in source_files.items():
                if os.path.exists(filepath):
                    stats = process_file(conn, species_id, filepath, args.batch_size, args.dry_run)
                    for key in total_stats:
                        total_stats[key] += stats.get(key, 0)
                else:
                    logger.warning(f"文件不存在: {filepath}")

        # 提交事务
        if not args.dry_run:
            conn.commit()
            logger.info("事务已提交")

        # 检查最终状态
        with get_cursor(conn) as cursor:
            cursor.execute("SELECT COUNT(*) FROM sequences")
            after_count = cursor.fetchone()[0]

        print("\n" + "=" * 60)
        print("导入完成")
        print("=" * 60)
        print(f"导入前记录数: {before_count:,}")
        print(f"导入后记录数: {after_count:,}")
        print(f"新增记录数:   {after_count - before_count:,}")
        print(f"匹配记录数:   {total_stats['matched']:,}")
        print(f"未匹配记录:   {total_stats['not_matched']:,}")
        print(f"空序列跳过:   {total_stats['empty_seq']:,}")
        print(f"处理错误:     {total_stats['errors']:,}")
        print("=" * 60)

    except psycopg2.Error as e:
        logger.error(f"数据库错误: {e}")
        if conn:
            conn.rollback()
            logger.info("事务已回滚")
        sys.exit(1)
    except Exception as e:
        logger.error(f"导入过程出错: {e}")
        if conn:
            conn.rollback()
            logger.info("事务已回滚")
        sys.exit(1)
    finally:
        if conn:
            conn.close()
            logger.info("数据库连接已关闭")


if __name__ == "__main__":
    main()
