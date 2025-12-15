#!/usr/bin/env python3
"""
Ortholog数据导入脚本
==================

导入同源基因/lncRNA数据到core_genes和genes表

数据来源:
- ortholog_lnc_table.csv: lncRNA同源信息
- ortholog_gene_table.csv: 基因同源信息

版本: v1.0
日期: 2025-11-20
"""

import sys
import csv
import psycopg2
from psycopg2.extras import execute_values
import argparse
import logging
from typing import Dict

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class OrthologImporter:
    """导入ortholog数据"""

    def __init__(self, db_config: Dict[str, str]):
        self.db_config = db_config
        self.conn = None
        self.stats = {
            'core_genes_inserted': 0,
            'genes_inserted': 0,
            'core_genes_skipped': 0,
            'genes_skipped': 0,
            'errors': []
        }

    def connect(self):
        """建立数据库连接"""
        try:
            self.conn = psycopg2.connect(**self.db_config)
            logger.info(f"连接数据库: {self.db_config['dbname']}")
        except Exception as e:
            logger.error(f"数据库连接失败: {e}")
            raise

    def disconnect(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()
            logger.info("数据库连接已关闭")

    # ENSG基因的core_id偏移量，用于区分CATG和ENSG编号
    # CATG范围: 11-118375, ENSG范围: 971-273492
    # 使用500000000偏移量确保不会冲突
    ENSG_CORE_ID_OFFSET = 500000000

    def _extract_core_id(self, gene_id: str, expected_prefix: str = None) -> int:
        """
        从基因ID提取数字部分作为core_id，自动处理CATG和ENSG前缀

        CATG和ENSG使用不同的编号空间，数字部分可能重复，
        因此ENSG基因的core_id会加上偏移量(500000000)以避免冲突。

        示例:
        - CATG00000000011.1 -> 11
        - CATG00000000226 -> 226
        - ENSG00000123456.7 -> 500123456 (加偏移量)
        - ENSG00000055118 -> 500055118 (加偏移量)

        Args:
            gene_id: 基因ID (CATG或ENSG开头)
            expected_prefix: 已废弃，保留用于兼容性
        """
        import re

        # 移除版本号(.1, .2等)
        gene_id_clean = gene_id.split('.')[0]

        # 识别前缀类型
        is_catg = gene_id_clean.startswith('CATG')
        is_ensg = gene_id_clean.startswith('ENSG')

        if not is_catg and not is_ensg:
            raise ValueError(f"ID '{gene_id}' 必须以CATG或ENSG开头")

        # 提取数字部分
        match = re.search(r'(\d+)$', gene_id_clean)
        if not match:
            raise ValueError(f"无法从'{gene_id}'提取数字部分")

        num = int(match.group(1))

        # ENSG基因加偏移量，避免与CATG冲突
        if is_ensg:
            return num + self.ENSG_CORE_ID_OFFSET
        else:
            return num

    def get_species_map(self) -> Dict[str, int]:
        """获取物种代码到ID的映射"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT species_code, species_id FROM species")
        species_map = dict(cursor.fetchall())
        cursor.close()
        logger.info(f"物种映射: {species_map}")
        return species_map

    def import_lncrnas(self, file_path: str, dry_run: bool = False):
        """
        导入lncRNA数据

        CSV格式:
        species,species_lnc_id,lnc_core_id,human_reference_lnc_id,sequence_file,species_presence_tag
        """
        logger.info(f"开始导入lncRNA数据: {file_path}")

        species_map = self.get_species_map()
        cursor = self.conn.cursor()

        # 读取CSV文件
        lncrnas = []
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader, 1):
                try:
                    species_code = row['species'].strip()
                    species_id = species_map.get(species_code)

                    if not species_id:
                        logger.warning(f"第{i}行: 未知物种 '{species_code}', 跳过")
                        self.stats['genes_skipped'] += 1
                        continue

                    # 提取core_id (支持CATG和ENSG，ENSG会加偏移量)
                    lnc_core_id_str = row['lnc_core_id'].strip()
                    core_id = self._extract_core_id(lnc_core_id_str)

                    lncrna_data = {
                        'core_id': core_id,
                        'core_id_str': lnc_core_id_str,  # 保存原始字符串用于追踪
                        'species_id': species_id,
                        'species_lnc_id': row['species_lnc_id'].strip(),
                        'human_reference_lnc_id': row['human_reference_lnc_id'].strip(),
                        'sequence_file': row['sequence_file'].strip() if row.get('sequence_file') else None,
                        'species_presence_tag': row['species_presence_tag'].strip() if row.get('species_presence_tag') else None
                    }

                    lncrnas.append(lncrna_data)

                except Exception as e:
                    error_msg = f"第{i}行解析失败: {e}"
                    self.stats['errors'].append(error_msg)
                    logger.warning(error_msg)

                # 进度反馈
                if i % 1000 == 0:
                    logger.info(f"已读取 {i} 行...")

        logger.info(f"CSV文件加载完成: 有效记录={len(lncrnas)}")

        if dry_run:
            logger.info("试运行模式，不实际写入数据")
            cursor.close()
            return

        # 分组: core_id -> [species_data]
        core_groups = {}
        for lnc in lncrnas:
            core_id = lnc['core_id']
            if core_id not in core_groups:
                core_groups[core_id] = []
            core_groups[core_id].append(lnc)

        logger.info(f"发现 {len(core_groups)} 个独立的core_id")

        # 插入core_genes
        core_genes_data = []
        for core_id, lnc_list in core_groups.items():
            # 使用human作为参考
            human_lnc = next((lnc for lnc in lnc_list if lnc['species_id'] == 1), lnc_list[0])

            core_genes_data.append((
                core_id,
                'lncRNA',
                human_lnc['human_reference_lnc_id'],
                human_lnc['human_reference_lnc_id'],
                f"lncRNA {human_lnc['human_reference_lnc_id']}"
            ))

        try:
            # 先插入core_id_assignments（使用标准的INSERT ... SELECT语法，兼容PostgreSQL 10+）
            cursor.execute("""
                INSERT INTO core_id_assignments (core_id, assignment_source, notes)
                SELECT unnest(%s::int[]), 'ortholog_table', 'lncRNA ortholog import'
                ON CONFLICT (core_id) DO NOTHING
            """, ([c[0] for c in core_genes_data],))

            # 插入core_genes
            inserted_core_ids = execute_values(cursor, """
                INSERT INTO core_genes (core_id, gene_type, canonical_symbol, human_ensembl_id, description)
                VALUES %s
                ON CONFLICT (core_id) DO NOTHING
                RETURNING core_id
            """, core_genes_data, fetch=True)

            self.stats['core_genes_inserted'] = len(inserted_core_ids)
            logger.info(f"插入 {len(inserted_core_ids)} 条core_genes记录（尝试 {len(core_genes_data)} 条）")

            # 插入genes
            genes_data = []
            for lnc in lncrnas:
                genes_data.append((
                    lnc['species_id'],
                    lnc['core_id'],
                    lnc['species_lnc_id'],
                    lnc['species_lnc_id'],  # gene_name与gene_ensembl_id相同
                ))

            inserted_gene_ids = execute_values(cursor, """
                INSERT INTO genes (species_id, core_id, gene_ensembl_id, gene_name)
                VALUES %s
                ON CONFLICT (species_id, gene_ensembl_id) DO NOTHING
                RETURNING gene_id
            """, genes_data, fetch=True)

            self.stats['genes_inserted'] += len(inserted_gene_ids)
            logger.info(f"插入 {len(inserted_gene_ids)} 条genes记录（尝试 {len(genes_data)} 条）")

            self.conn.commit()
            logger.info("lncRNA数据导入成功")

        except Exception as e:
            self.conn.rollback()
            logger.error(f"导入失败，已回滚: {e}")
            raise
        finally:
            cursor.close()

    def import_genes(self, file_path: str, dry_run: bool = False):
        """
        导入基因数据

        CSV格式:
        species,species_gene_id,gene_core_id,human_reference_gene_id,gene_name,species_presence_tag
        """
        logger.info(f"开始导入基因数据: {file_path}")

        species_map = self.get_species_map()
        cursor = self.conn.cursor()

        # 读取CSV文件
        genes = []
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader, 1):
                try:
                    species_code = row['species'].strip()
                    species_id = species_map.get(species_code)

                    if not species_id:
                        logger.warning(f"第{i}行: 未知物种 '{species_code}', 跳过")
                        self.stats['genes_skipped'] += 1
                        continue

                    # 提取core_id (支持CATG和ENSG，ENSG会加偏移量)
                    gene_core_id_str = row['gene_core_id'].strip()
                    core_id = self._extract_core_id(gene_core_id_str)

                    gene_data = {
                        'core_id': core_id,
                        'core_id_str': gene_core_id_str,  # 保存原始字符串用于追踪
                        'species_id': species_id,
                        'species_gene_id': row['species_gene_id'].strip(),
                        'human_reference_gene_id': row['human_reference_gene_id'].strip(),
                        'gene_name': row['gene_name'].strip(),
                        'species_presence_tag': row['species_presence_tag'].strip() if row.get('species_presence_tag') else None
                    }

                    genes.append(gene_data)

                except Exception as e:
                    error_msg = f"第{i}行解析失败: {e}"
                    self.stats['errors'].append(error_msg)
                    logger.warning(error_msg)

                # 进度反馈
                if i % 1000 == 0:
                    logger.info(f"已读取 {i} 行...")

        logger.info(f"CSV文件加载完成: 有效记录={len(genes)}")

        if dry_run:
            logger.info("试运行模式，不实际写入数据")
            cursor.close()
            return

        # 分组: core_id -> [species_data]
        core_groups = {}
        for gene in genes:
            core_id = gene['core_id']
            if core_id not in core_groups:
                core_groups[core_id] = []
            core_groups[core_id].append(gene)

        logger.info(f"发现 {len(core_groups)} 个独立的core_id")

        # 插入core_genes
        core_genes_data = []
        for core_id, gene_list in core_groups.items():
            # 使用human作为参考
            human_gene = next((g for g in gene_list if g['species_id'] == 1), gene_list[0])

            core_genes_data.append((
                core_id,
                'protein_coding',
                human_gene['gene_name'],
                human_gene['human_reference_gene_id'],
                f"Protein coding gene {human_gene['gene_name']}"
            ))

        try:
            # 先插入core_id_assignments（使用标准的INSERT ... SELECT语法，兼容PostgreSQL 10+）
            cursor.execute("""
                INSERT INTO core_id_assignments (core_id, assignment_source, notes)
                SELECT unnest(%s::int[]), 'ortholog_table', 'protein_coding gene ortholog import'
                ON CONFLICT (core_id) DO NOTHING
            """, ([c[0] for c in core_genes_data],))

            # 插入core_genes
            inserted_core_ids = execute_values(cursor, """
                INSERT INTO core_genes (core_id, gene_type, canonical_symbol, human_ensembl_id, description)
                VALUES %s
                ON CONFLICT (core_id) DO NOTHING
                RETURNING core_id
            """, core_genes_data, fetch=True)

            self.stats['core_genes_inserted'] += len(inserted_core_ids)
            logger.info(f"插入 {len(inserted_core_ids)} 条core_genes记录（尝试 {len(core_genes_data)} 条）")

            # 插入genes
            genes_data = []
            for gene in genes:
                genes_data.append((
                    gene['species_id'],
                    gene['core_id'],
                    gene['species_gene_id'],
                    gene['gene_name'],
                ))

            inserted_gene_ids = execute_values(cursor, """
                INSERT INTO genes (species_id, core_id, gene_ensembl_id, gene_name)
                VALUES %s
                ON CONFLICT (species_id, gene_ensembl_id) DO NOTHING
                RETURNING gene_id
            """, genes_data, fetch=True)

            self.stats['genes_inserted'] += len(inserted_gene_ids)
            logger.info(f"插入 {len(inserted_gene_ids)} 条genes记录（尝试 {len(genes_data)} 条）")

            self.conn.commit()
            logger.info("基因数据导入成功")

        except Exception as e:
            self.conn.rollback()
            logger.error(f"导入失败，已回滚: {e}")
            raise
        finally:
            cursor.close()

    def print_stats(self):
        """打印导入统计"""
        print("\n" + "="*60)
        print("Ortholog数据导入统计")
        print("="*60)
        print(f"core_genes插入:  {self.stats['core_genes_inserted']}")
        print(f"genes插入:       {self.stats['genes_inserted']}")
        print(f"core_genes跳过:  {self.stats['core_genes_skipped']}")
        print(f"genes跳过:       {self.stats['genes_skipped']}")
        print(f"错误数:          {len(self.stats['errors'])}")

        if self.stats['errors']:
            print("\n错误详情（前10条）:")
            for error in self.stats['errors'][:10]:
                print(f"  - {error}")

        print("="*60 + "\n")


def main():
    parser = argparse.ArgumentParser(description='导入Ortholog数据')
    parser.add_argument('--lncrna-file', required=True, help='lncRNA ortholog CSV文件路径')
    parser.add_argument('--gene-file', required=True, help='基因ortholog CSV文件路径')
    parser.add_argument('--host', default='localhost', help='数据库主机')
    parser.add_argument('--port', default='5432', help='数据库端口')
    parser.add_argument('--dbname', default='lncrna_production', help='数据库名称')
    parser.add_argument('--user', required=True, help='数据库用户')
    parser.add_argument('--password', help='数据库密码（可选，使用.pgpass）')
    parser.add_argument('--dry-run', action='store_true', help='试运行模式')

    args = parser.parse_args()

    db_config = {
        'host': args.host,
        'port': args.port,
        'dbname': args.dbname,
        'user': args.user,
    }

    if args.password:
        db_config['password'] = args.password

    importer = OrthologImporter(db_config)

    try:
        importer.connect()

        # 导入lncRNA
        logger.info("=" * 60)
        logger.info("第1步: 导入lncRNA数据")
        logger.info("=" * 60)
        importer.import_lncrnas(args.lncrna_file, dry_run=args.dry_run)

        # 导入基因
        logger.info("\n" + "=" * 60)
        logger.info("第2步: 导入protein_coding基因数据")
        logger.info("=" * 60)
        importer.import_genes(args.gene_file, dry_run=args.dry_run)

        # 打印统计
        importer.print_stats()

        # 验证结果
        if not args.dry_run:
            cursor = importer.conn.cursor()
            cursor.execute("SELECT gene_type, COUNT(*) FROM core_genes GROUP BY gene_type")
            results = cursor.fetchall()

            print("\n数据库验证:")
            print("-" * 60)
            for gene_type, count in results:
                print(f"  {gene_type}: {count} 条")

            cursor.execute("SELECT s.species_code, COUNT(*) FROM genes g JOIN species s ON g.species_id = s.species_id GROUP BY s.species_code")
            results = cursor.fetchall()

            print("\nGenes表按物种统计:")
            print("-" * 60)
            for species, count in results:
                print(f"  {species}: {count} 条")

            cursor.close()

        logger.info("导入完成！")

    except Exception as e:
        logger.error(f"导入过程出错: {e}")
        sys.exit(1)

    finally:
        importer.disconnect()


if __name__ == '__main__':
    main()
