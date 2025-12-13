#!/usr/bin/env python3
"""
Regulations数据导入器
======================

从*_batch_BA*.txt文件导入lncRNA调控关系数据

用法:
    python3 import_regulations.py \
        --file /path/to/human_batch_BA60.txt \
        --species-id 1 \
        --batch-name "Human Regulations BA60" \
        --dry-run  # 可选，试运行

版本: v2.3
日期: 2025-11-20
"""

import sys
import argparse
from pathlib import Path
from typing import List, Dict, Optional, Tuple

# 添加templates目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent / 'templates'))

from import_base import BaseImporter, safe_int, safe_float, safe_str
from batch_manager import BatchManager
from psycopg2.extras import execute_values


class RegulationsImporter(BaseImporter):
    """
    Regulations表导入器

    输入文件格式 (Tab分隔):
    LncRNA  TargetGene  Chr  Start  End  Strand  BA  ...  LncRNA_Seq  DNA_Seq
    """

    def __init__(self, db_config: Dict[str, str], species_id: int,
                 min_ba: float = 0.0):
        """
        Args:
            db_config: 数据库配置
            species_id: 物种ID (1=human, 2=chimp, 3=macaque, 4=marmoset)
            min_ba: 最小binding affinity阈值
        """
        super().__init__(db_config)
        self.species_id = species_id
        self.min_ba = min_ba

        # 缓存基因ID映射 (gene_name -> gene_id)
        self.gene_id_cache: Dict[str, int] = {}

    def get_batch_type(self) -> str:
        return "regulations"

    def parse_row(self, row: Dict) -> Optional[Dict]:
        """
        解析单行数据

        输入row示例:
        {
            'LncRNA': 'CATG00000000034.1',
            'TargetGene': 'ENSG00000012048.1',
            'Chr': 'chr10',
            'Start': '81181096',
            'End': '81181143',
            'Strand': '+',
            'BA': '75.5',
            ...
            'LncRNA_Seq': 'ACGT...',
            'DNA_Seq': 'TGCA...'
        }
        """
        lncrna_name = safe_str(row.get('LncRNA'))
        target_name = safe_str(row.get('TargetGene'))
        binding_affinity = safe_float(row.get('BA'), 0.0)

        # 过滤低BA值
        if binding_affinity < self.min_ba:
            return None

        if not lncrna_name or not target_name:
            raise ValueError(f"缺少必填字段: LncRNA={lncrna_name}, TargetGene={target_name}")

        parsed = {
            'lncrna_name': lncrna_name,
            'target_name': target_name,
            'target_chromosome': safe_str(row.get('Chr')),
            'target_start': safe_int(row.get('Start')),
            'target_end': safe_int(row.get('End')),
            # target_strand: regulations表没有此列，不解析
            'binding_affinity': binding_affinity,
            'lncrna_sequence': safe_str(row.get('LncRNA_Seq')),
            'dna_sequence': safe_str(row.get('DNA_Seq'))
        }

        return parsed

    def validate_data(self, data: List[Dict]) -> Tuple[List[Dict], List[str]]:
        """
        验证数据

        检查项:
        1. 基因名是否存在于genes表
        2. 坐标是否合法
        3. BA范围是否正确
        """
        errors = []
        valid_data = []

        # 1. 加载基因ID缓存
        self._load_gene_id_cache()

        for i, record in enumerate(data):
            try:
                # 检查lncRNA是否存在
                lncrna_id = self.gene_id_cache.get(record['lncrna_name'])
                if not lncrna_id:
                    errors.append(f"第{i+1}行: lncRNA '{record['lncrna_name']}' 不存在于genes表")
                    continue

                # 检查target基因是否存在
                target_id = self.gene_id_cache.get(record['target_name'])
                if not target_id:
                    errors.append(f"第{i+1}行: TargetGene '{record['target_name']}' 不存在于genes表")
                    continue

                # 检查坐标合法性
                if record['target_start'] and record['target_end']:
                    if record['target_end'] <= record['target_start']:
                        errors.append(f"第{i+1}行: 非法坐标 start={record['target_start']}, end={record['target_end']}")
                        continue

                # 检查BA范围
                if not (0 <= record['binding_affinity'] <= 1000):
                    errors.append(f"第{i+1}行: BA值超出范围: {record['binding_affinity']}")
                    continue

                # 添加gene_id
                record['lncrna_gene_id'] = lncrna_id
                record['target_gene_id'] = target_id
                valid_data.append(record)

            except Exception as e:
                errors.append(f"第{i+1}行验证失败: {e}")

        return valid_data, errors

    def _load_gene_id_cache(self):
        """从数据库加载基因ID映射"""
        if self.gene_id_cache:
            return  # 已加载

        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT gene_id, gene_ensembl_id, gene_name
                FROM genes
                WHERE species_id = %s
            """, (self.species_id,))

            for gene_id, ensembl_id, gene_name in cur.fetchall():
                # 同时缓存ensembl_id和gene_name
                self.gene_id_cache[ensembl_id] = gene_id
                if gene_name:
                    self.gene_id_cache[gene_name] = gene_id

        logger.info(f"加载基因ID缓存: {len(self.gene_id_cache)} 个基因")

    def _insert_data(self, data: List[Dict], batch: BatchManager):
        """
        批量插入regulations和sequences数据
        """
        batch_id = batch.get_batch_id()

        # 准备regulations数据（注意：regulations表没有target_strand列）
        regulations_values = [
            (
                self.species_id,
                record['lncrna_gene_id'],
                record['target_gene_id'],
                record['target_chromosome'],
                record['target_start'],
                record['target_end'],
                record['binding_affinity'],
                batch_id
            )
            for record in data
        ]

        # 批量插入regulations
        with self.conn.cursor() as cur:
            regulation_ids = execute_values(
                cur,
                """
                INSERT INTO regulations
                    (species_id, lncrna_gene_id, target_gene_id,
                     target_chromosome, target_start, target_end,
                     binding_affinity, batch_id)
                VALUES %s
                RETURNING regulation_id
                """,
                regulations_values,
                fetch=True
            )

            logger.info(f"插入 {len(regulations_values)} 条regulations记录")

            # 准备sequences数据（只保存非空序列）
            sequences_values = []
            for i, record in enumerate(data):
                regulation_id = regulation_ids[i][0]

                if record['lncrna_sequence'] or record['dna_sequence']:
                    sequences_values.append((
                        regulation_id,
                        record['lncrna_sequence'],
                        record['dna_sequence']
                    ))

            if sequences_values:
                execute_values(
                    cur,
                    """
                    INSERT INTO sequences (regulation_id, lncrna_sequence, dna_sequence)
                    VALUES %s
                    """,
                    sequences_values
                )

                logger.info(f"插入 {len(sequences_values)} 条sequences记录")

        self.conn.commit()


def main():
    parser = argparse.ArgumentParser(description='导入lncRNA调控关系数据')
    parser.add_argument('--file', required=True, help='输入文件路径')
    parser.add_argument('--species-id', type=int, required=True,
                       choices=[1, 2, 3, 4],
                       help='物种ID (1=human, 2=chimp, 3=macaque, 4=marmoset)')
    parser.add_argument('--batch-name', help='批次名称（可选）')
    parser.add_argument('--min-ba', type=float, default=0.0,
                       help='最小binding affinity阈值（默认0）')
    parser.add_argument('--dry-run', action='store_true',
                       help='试运行模式，不实际写入数据库')

    # 数据库连接参数
    parser.add_argument('--db-host', default='localhost')
    parser.add_argument('--db-port', default='5432')
    parser.add_argument('--db-name', default='lncrna_network')
    parser.add_argument('--db-user', default='postgres')
    parser.add_argument('--db-password', default='')

    args = parser.parse_args()

    # 数据库配置
    db_config = {
        'host': args.db_host,
        'port': args.db_port,
        'dbname': args.db_name,
        'user': args.db_user,
        'password': args.db_password
    }

    # 创建导入器
    importer = RegulationsImporter(db_config, args.species_id, args.min_ba)

    # 执行导入
    stats = importer.import_data(
        file_path=args.file,
        batch_name=args.batch_name,
        species_id=args.species_id,
        dry_run=args.dry_run
    )

    # 打印统计信息
    importer.print_stats()

    # 返回退出码
    return 0 if stats['failed_rows'] == 0 else 1


if __name__ == "__main__":
    import logging
    logger = logging.getLogger(__name__)
    sys.exit(main())
