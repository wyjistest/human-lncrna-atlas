#!/usr/bin/env python3
"""
Table15数据导入脚本
==================

导入trait-gene-ontology关联数据到traits, ontologies, trait_gene_associations表

数据来源:
- table15_normalized_full.csv: 完整的trait-gene关联数据（67k条）
- table15_normalized_sample.csv: 样本数据（200条，用于测试）

版本: v1.0
日期: 2025-11-20
"""

import sys
import csv
import psycopg2
from psycopg2.extras import execute_values
import argparse
import logging
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class Table15Importer:
    """导入table15数据"""

    def __init__(self, db_config: Dict[str, str]):
        self.db_config = db_config
        self.conn = None

        # 缓存
        self.trait_cache = {}  # {trait_doid: trait_id}
        self.ontology_cache = {}  # {ontology_cl_id: ontology_id}
        self.gene_to_core_cache = {}  # {(species_id, gene_ensembl_id): core_id}

        self.stats = {
            'total_rows': 0,
            'traits_inserted': 0,
            'ontologies_inserted': 0,
            'associations_inserted': 0,
            'skipped_rows': 0,
            'failed_rows': 0,
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

    def _load_gene_to_core_cache(self):
        """加载gene_id到core_id的映射"""
        cursor = self.conn.cursor()

        cursor.execute("""
            SELECT g.species_id, g.gene_ensembl_id, g.core_id
            FROM genes g
            WHERE g.core_id IS NOT NULL
        """)

        for species_id, gene_ensembl_id, core_id in cursor.fetchall():
            # 存储带版本号的
            self.gene_to_core_cache[(species_id, gene_ensembl_id)] = core_id

            # 也存储不带版本号的
            gene_base = gene_ensembl_id.split('.')[0] if '.' in gene_ensembl_id else gene_ensembl_id
            if gene_base != gene_ensembl_id:
                self.gene_to_core_cache[(species_id, gene_base)] = core_id

        cursor.close()
        logger.info(f"加载基因到core_id映射: {len(self.gene_to_core_cache)} 条")

    def _get_core_id(self, gene_id: str, species_id: int = 1) -> Optional[int]:
        """
        获取基因的core_id

        Args:
            gene_id: CATG00000000011.1 或 ENSG00000123456.2
            species_id: 物种ID（默认为human=1）
        """
        # 尝试精确匹配
        core_id = self.gene_to_core_cache.get((species_id, gene_id))
        if core_id:
            return core_id

        # 尝试不带版本号
        gene_base = gene_id.split('.')[0] if '.' in gene_id else gene_id
        core_id = self.gene_to_core_cache.get((species_id, gene_base))
        if core_id:
            return core_id

        # 对于非human物种，尝试添加后缀
        if species_id != 1:
            species_suffixes = {2: '_chimp', 3: '_macaque', 4: '_marmoset'}
            suffix = species_suffixes.get(species_id)
            if suffix:
                gene_with_suffix = f"{gene_id}{suffix}"
                core_id = self.gene_to_core_cache.get((species_id, gene_with_suffix))
                if core_id:
                    return core_id

        return None

    def _get_or_create_trait(self, trait_doid: str, trait_name: str) -> int:
        """获取或创建trait"""
        # 检查缓存
        if trait_doid in self.trait_cache:
            return self.trait_cache[trait_doid]

        cursor = self.conn.cursor()

        # 尝试查找
        cursor.execute("""
            SELECT trait_id FROM traits WHERE trait_doid = %s
        """, (trait_doid,))

        result = cursor.fetchone()
        if result:
            trait_id = result[0]
            self.trait_cache[trait_doid] = trait_id
            cursor.close()
            return trait_id

        # 创建新记录
        # 注意：与associations在同一事务中，由_batch_insert_associations统一commit
        cursor.execute("""
            INSERT INTO traits (trait_doid, trait_name)
            VALUES (%s, %s)
            RETURNING trait_id
        """, (trait_doid, trait_name))

        trait_id = cursor.fetchone()[0]

        self.trait_cache[trait_doid] = trait_id
        self.stats['traits_inserted'] += 1

        cursor.close()
        return trait_id

    def _get_or_create_ontology(self, ontology_cl_id: str, ontology_name: str) -> int:
        """获取或创建ontology"""
        # 检查缓存
        if ontology_cl_id in self.ontology_cache:
            return self.ontology_cache[ontology_cl_id]

        cursor = self.conn.cursor()

        # 尝试查找
        cursor.execute("""
            SELECT ontology_id FROM ontologies WHERE ontology_cl_id = %s
        """, (ontology_cl_id,))

        result = cursor.fetchone()
        if result:
            ontology_id = result[0]
            self.ontology_cache[ontology_cl_id] = ontology_id
            cursor.close()
            return ontology_id

        # 创建新记录
        # 注意：与associations在同一事务中，由_batch_insert_associations统一commit
        cursor.execute("""
            INSERT INTO ontologies (ontology_cl_id, ontology_name)
            VALUES (%s, %s)
            RETURNING ontology_id
        """, (ontology_cl_id, ontology_name))

        ontology_id = cursor.fetchone()[0]

        self.ontology_cache[ontology_cl_id] = ontology_id
        self.stats['ontologies_inserted'] += 1

        cursor.close()
        return ontology_id

    def import_file(self, file_path: str, species_id: int = 1,
                   dry_run: bool = False, batch_size: int = 1000):
        """
        导入table15文件

        Args:
            file_path: CSV文件路径
            species_id: 物种ID（table15主要是human数据）
            dry_run: 试运行模式
            batch_size: 批量插入大小
        """
        logger.info(f"开始导入文件: {file_path}")

        # 加载基因映射
        self._load_gene_to_core_cache()

        # 读取CSV文件
        associations = []

        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)

            for i, row in enumerate(reader, 1):
                self.stats['total_rows'] += 1

                try:
                    # 获取core_id
                    gene_id = row['lnc_id'].strip()
                    core_id = self._get_core_id(gene_id, species_id)

                    if not core_id:
                        self.stats['skipped_rows'] += 1
                        if i <= 10:
                            logger.warning(f"第{i}行: 基因 '{gene_id}' 找不到core_id")
                        continue

                    # 获取或创建trait
                    trait_doid = row['trait_id'].strip()
                    trait_name = row['trait_name'].strip()

                    if not dry_run:
                        trait_id = self._get_or_create_trait(trait_doid, trait_name)
                    else:
                        trait_id = 1  # dry-run模式使用假ID

                    # 获取或创建ontology
                    ontology_cl_id = row['ontology_id'].strip()
                    ontology_name = row['ontology_name'].strip()

                    if not dry_run:
                        ontology_id = self._get_or_create_ontology(ontology_cl_id, ontology_name)
                    else:
                        ontology_id = 1  # dry-run模式使用假ID

                    # 准备关联数据
                    association = {
                        'core_id': core_id,
                        'trait_id': trait_id,
                        'ontology_id': ontology_id,
                        'odds_ratio': self._safe_float(row.get('odds_ratio')),
                        'fdr': self._safe_float(row.get('fdr')),
                        'trait_snp_pvalue': self._safe_float(row.get('trait_snp_pvalue')),
                        'ontology_mw_pvalue': self._safe_float(row.get('ontology_mw_pvalue')),
                        'ontology_fold_enrichment': self._safe_float(row.get('ontology_fold_enrichment')),
                        'literature_support': row.get('literature_support', '').strip().lower() == 'yes',
                        'evidence_species_id': species_id,
                        'source_table': row.get('source_table', '').strip() or None,
                        'source_row_number': self._safe_int(row.get('source_row_number')),
                    }

                    associations.append(association)

                except Exception as e:
                    self.stats['failed_rows'] += 1
                    error_msg = f"第{i}行解析失败: {e}"
                    if len(self.stats['errors']) < 100:
                        self.stats['errors'].append(error_msg)
                    if i <= 10:
                        logger.warning(error_msg)

                # 进度反馈
                if i % 10000 == 0:
                    logger.info(f"已读取 {i} 行, 有效={len(associations)}, 跳过={self.stats['skipped_rows']}")

                # 批量插入
                if len(associations) >= batch_size and not dry_run:
                    self._batch_insert_associations(associations)
                    associations = []

        logger.info(f"文件读取完成: 总行数={self.stats['total_rows']}, "
                   f"待插入={len(associations)}, 跳过={self.stats['skipped_rows']}, "
                   f"失败={self.stats['failed_rows']}")

        if dry_run:
            logger.info("试运行模式，不实际写入数据")
            return

        # 插入剩余数据
        if associations:
            self._batch_insert_associations(associations)

        logger.info(f"导入完成! traits={self.stats['traits_inserted']}, "
                   f"ontologies={self.stats['ontologies_inserted']}, "
                   f"associations={self.stats['associations_inserted']}")

    def _batch_insert_associations(self, associations: List[Dict]):
        """批量插入trait_gene_associations"""
        cursor = self.conn.cursor()

        try:
            values = []
            for assoc in associations:
                values.append((
                    assoc['core_id'],
                    assoc['trait_id'],
                    assoc['ontology_id'],
                    assoc['odds_ratio'],
                    assoc['fdr'],
                    assoc['trait_snp_pvalue'],
                    assoc['ontology_mw_pvalue'],
                    assoc['ontology_fold_enrichment'],
                    assoc['literature_support'],
                    assoc['evidence_species_id'],
                    assoc['source_table'],
                    assoc['source_row_number'],
                ))

            inserted_ids = execute_values(cursor, """
                INSERT INTO trait_gene_associations (
                    core_id, trait_id, ontology_id, odds_ratio, fdr,
                    trait_snp_pvalue, ontology_mw_pvalue, ontology_fold_enrichment,
                    literature_support, evidence_species_id, source_table, source_row_number
                )
                VALUES %s
                ON CONFLICT (core_id, trait_id, ontology_id) DO NOTHING
                RETURNING association_id
            """, values, fetch=True)

            self.stats['associations_inserted'] += len(inserted_ids)
            self.conn.commit()

        except Exception as e:
            self.conn.rollback()
            logger.error(f"批量插入失败: {e}")
            raise
        finally:
            cursor.close()

    def _safe_int(self, value) -> Optional[int]:
        """安全转换为整数"""
        try:
            return int(value) if value and str(value).strip() else None
        except (ValueError, TypeError):
            return None

    def _safe_float(self, value) -> Optional[float]:
        """安全转换为浮点数"""
        try:
            return float(value) if value and str(value).strip() else None
        except (ValueError, TypeError):
            return None

    def print_stats(self):
        """打印导入统计"""
        print("\n" + "="*60)
        print("Table15数据导入统计")
        print("="*60)
        print(f"总行数:             {self.stats['total_rows']}")
        print(f"traits插入:         {self.stats['traits_inserted']}")
        print(f"ontologies插入:     {self.stats['ontologies_inserted']}")
        print(f"associations插入:   {self.stats['associations_inserted']}")
        print(f"跳过:               {self.stats['skipped_rows']}")
        print(f"失败:               {self.stats['failed_rows']}")
        print(f"错误数:             {len(self.stats['errors'])}")

        if self.stats['errors']:
            print("\n错误详情（前20条）:")
            for error in self.stats['errors'][:20]:
                print(f"  - {error}")

        print("="*60 + "\n")


def main():
    parser = argparse.ArgumentParser(description='导入Table15数据')
    parser.add_argument('--file', required=True, help='Table15 CSV文件路径')
    parser.add_argument('--species-id', type=int, default=1, help='物种ID（默认1=human）')
    parser.add_argument('--host', default='localhost', help='数据库主机')
    parser.add_argument('--port', default='5432', help='数据库端口')
    parser.add_argument('--dbname', default='lncrna_production', help='数据库名称')
    parser.add_argument('--user', required=True, help='数据库用户')
    parser.add_argument('--password', help='数据库密码（可选，使用.pgpass）')
    parser.add_argument('--batch-size', type=int, default=1000, help='批量插入大小')
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

    importer = Table15Importer(db_config)

    try:
        importer.connect()

        importer.import_file(
            file_path=args.file,
            species_id=args.species_id,
            dry_run=args.dry_run,
            batch_size=args.batch_size
        )

        importer.print_stats()

        # 验证结果
        if not args.dry_run:
            cursor = importer.conn.cursor()

            cursor.execute("SELECT COUNT(*) FROM traits")
            trait_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM ontologies")
            ontology_count = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM trait_gene_associations")
            assoc_count = cursor.fetchone()[0]

            print("\n数据库验证:")
            print("-" * 60)
            print(f"  Traits表: {trait_count:,} 条")
            print(f"  Ontologies表: {ontology_count:,} 条")
            print(f"  Trait_gene_associations表: {assoc_count:,} 条")

            cursor.close()

        logger.info("导入完成！")

    except Exception as e:
        logger.error(f"导入过程出错: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    finally:
        importer.disconnect()


if __name__ == '__main__':
    main()
