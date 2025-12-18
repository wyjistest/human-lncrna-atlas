#!/usr/bin/env python3
"""
Regulations数据导入脚本
=====================

导入lncRNA调控关系数据到regulations和sequences表

数据来源:
- human_batch_human.txt: 人类调控数据
- chimp_batch_BA50.txt: 黑猩猩调控数据（BA>=50）
- macaque_batch_BA50.txt: 猕猴调控数据（BA>=50）
- marmoset_batch_BA50.txt: 狨猴调控数据（BA>=50）

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
from typing import Dict, List, Optional

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class RegulationsImporter:
    """导入regulations数据"""

    def __init__(self, db_config: Dict[str, str]):
        self.db_config = db_config
        self.conn = None
        self.species_map = {}
        self.gene_cache = {}  # {(species_id, gene_ensembl_id): gene_id}
        self._loaded_species = set()  # 追踪已加载缓存的物种ID
        self.stats = {
            'total_rows': 0,
            'regulations_inserted': 0,
            'sequences_inserted': 0,
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

    def _check_required_index(self) -> bool:
        """
        检查 ON CONFLICT 所需的唯一索引是否存在

        Returns:
            True 如果索引存在，否则抛出异常
        """
        index_name = "idx_regulations_unique_key"
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT 1 FROM pg_indexes
            WHERE indexname = %s
        """, (index_name,))
        exists = cursor.fetchone() is not None
        cursor.close()

        if not exists:
            error_msg = f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║  ❌ 缺少必需的唯一索引: {index_name}
║
║  ETL 使用 IS NOT DISTINCT FROM 进行去重，需要此索引支持。
║
║  请先运行迁移脚本创建 NULL 安全索引 (需 PostgreSQL 15+):
║    psql -U amax -d lncrna_production -f etl/migrations/002_fix_regulations_unique_null_safe.sql
║
║  或手动创建 (需 PostgreSQL 15+):
║    CREATE UNIQUE INDEX IF NOT EXISTS {index_name}
║    ON regulations (species_id, lncrna_gene_id, target_gene_id,
║                    lncrna_start, lncrna_end, dna_start, dna_end)
║    NULLS NOT DISTINCT;
╚══════════════════════════════════════════════════════════════════════════════╝
"""
            logger.error(error_msg)
            raise RuntimeError(f"Missing required index: {index_name}")

        logger.info(f"✅ 唯一索引检查通过: {index_name}")
        return True

    def disconnect(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()
            logger.info("数据库连接已关闭")

    def _load_species_map(self):
        """加载物种映射"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT species_code, species_id FROM species")
        self.species_map = dict(cursor.fetchall())
        cursor.close()
        logger.info(f"物种映射: {self.species_map}")

    def _load_gene_cache(self, species_id: int):
        """加载指定物种的基因缓存"""
        # 使用 Set 检查，O(1) 复杂度替代 O(n) 的列表遍历
        if species_id in self._loaded_species:
            return  # 已加载

        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT gene_id, gene_ensembl_id, species_id
            FROM genes
            WHERE species_id = %s
        """, (species_id,))

        count = 0
        for gene_id, gene_ensembl_id, sp_id in cursor.fetchall():
            self.gene_cache[(sp_id, gene_ensembl_id)] = gene_id
            count += 1

        self._loaded_species.add(species_id)  # 标记为已加载
        cursor.close()
        logger.info(f"加载物种{species_id}的基因缓存: {count} 条")

    def _get_gene_id(self, species_id: int, gene_ensembl_id: str) -> Optional[int]:
        """获取gene_id"""
        # 移除版本号
        gene_ensembl_id_base = gene_ensembl_id.split('.')[0] if '.' in gene_ensembl_id else gene_ensembl_id

        # 尝试精确匹配
        gene_id = self.gene_cache.get((species_id, gene_ensembl_id))
        if gene_id:
            return gene_id

        # 尝试不带版本号匹配
        gene_id = self.gene_cache.get((species_id, gene_ensembl_id_base))
        if gene_id:
            return gene_id

        # 对于非human物种，尝试添加物种后缀
        if species_id != 1:  # 非human
            species_suffixes = {
                2: '_chimp',
                3: '_macaque',
                4: '_marmoset'
            }
            suffix = species_suffixes.get(species_id)
            if suffix:
                # 尝试带后缀的匹配
                gene_id_with_suffix = f"{gene_ensembl_id}{suffix}"
                gene_id = self.gene_cache.get((species_id, gene_id_with_suffix))
                if gene_id:
                    return gene_id

                # 尝试带后缀但不带版本号的匹配
                gene_id_base_with_suffix = f"{gene_ensembl_id_base}{suffix}"
                gene_id = self.gene_cache.get((species_id, gene_id_base_with_suffix))
                if gene_id:
                    return gene_id

        # 如果找不到，返回None
        return None

    def _create_batch(self, batch_name: str, species_id: int, file_path: str) -> int:
        """创建批次记录"""
        cursor = self.conn.cursor()

        cursor.execute("""
            INSERT INTO import_batches (batch_name, batch_type, species_id, source_file, status)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING batch_id
        """, (batch_name, 'regulations', species_id, file_path, 'in_progress'))

        batch_id = cursor.fetchone()[0]
        self.conn.commit()
        cursor.close()

        logger.info(f"创建批次: {batch_name} (batch_id={batch_id})")
        return batch_id

    def _update_batch(self, batch_id: int, status: str, record_count: int):
        """更新批次状态"""
        cursor = self.conn.cursor()

        cursor.execute("""
            UPDATE import_batches
            SET status = %s, record_count = %s, completed_at = CURRENT_TIMESTAMP
            WHERE batch_id = %s
        """, (status, record_count, batch_id))

        self.conn.commit()
        cursor.close()

    def _set_batch_error(self, batch_id: int, error_message: str):
        """设置批次错误信息（用于断点续传提示）"""
        cursor = self.conn.cursor()
        # 使用 notes 字段存储错误详情
        cursor.execute("""
            UPDATE import_batches
            SET notes = %s
            WHERE batch_id = %s
        """, (error_message, batch_id))
        self.conn.commit()
        cursor.close()

    def _validate_columns(self, file_path: str) -> None:
        """
        验证文件必需列是否存在

        Args:
            file_path: TSV 文件路径

        Raises:
            ValueError: 缺少必需列时抛出异常
        """
        required_columns = [
            'LncRNA_ID', 'Target_Gene_ID', 'Best_Avg_BA',
            'Best_Peak_Chr', 'Best_Peak_Start', 'Best_Peak_End'
        ]

        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter='\t')
            if reader.fieldnames is None:
                raise ValueError(f"文件无法读取表头: {file_path}")

            missing = set(required_columns) - set(reader.fieldnames)
            if missing:
                raise ValueError(
                    f"文件缺少必需列: {missing}\n"
                    f"文件列: {reader.fieldnames}"
                )

    def import_file(self, file_path: str, batch_name: Optional[str] = None,
                   species_code: Optional[str] = None, dry_run: bool = False,
                   store_sequences: bool = False, batch_size: int = 5000,
                   commit_every: int = 50000, skip_rows: int = 0):
        """
        导入单个regulations文件

        Args:
            file_path: TSV文件路径
            batch_name: 批次名称
            species_code: 物种代码（如果文件中没有Species列）
            dry_run: 试运行模式
            store_sequences: 是否存储序列数据到sequences表
            batch_size: 批量插入大小
            commit_every: 每多少条记录提交一次事务（默认50000，设为0禁用周期提交）
            skip_rows: 跳过前N行（用于断点续传，默认0）
        """
        logger.info(f"开始导入文件: {file_path}")

        # 列校验（快速失败）
        self._validate_columns(file_path)
        logger.info("列校验通过")

        # 索引校验（快速失败）
        # ON CONFLICT DO NOTHING 依赖 idx_regulations_unique_key 索引
        self._check_required_index()

        if skip_rows > 0:
            logger.info(f"断点续传模式：跳过前 {skip_rows} 行")

        # 加载物种映射
        self._load_species_map()

        # 批次管理变量
        batch_id = None
        detected_species_id = None
        committed_count = 0  # 已提交的记录数（用于断点续传）
        current_row = 0  # 当前处理的行号

        if not batch_name:
            batch_name = f"Regulations Import {Path(file_path).stem}"

        # 读取TSV文件
        regulations = []
        sequences = []

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f, delimiter='\t')

                for i, row in enumerate(reader, 1):
                    current_row = i  # 追踪当前行号
                    self.stats['total_rows'] += 1

                    # 断点续传：跳过已处理的行
                    if i <= skip_rows:
                        continue

                    try:
                        # 获取物种ID
                        if species_code:
                            sp_code = species_code
                        else:
                            sp_code = row.get('Species', '').strip().lower()

                        species_id = self.species_map.get(sp_code)
                        if not species_id:
                            self.stats['skipped_rows'] += 1
                            logger.warning(f"第{i}行: 未知物种 '{sp_code}', 跳过")
                            continue

                        # 加载该物种的基因缓存（按需加载，使用Set检查O(1)）
                        if species_id not in self._loaded_species:
                            self._load_gene_cache(species_id)

                        # 获取lncRNA和target基因的gene_id
                        lncrna_id = row['LncRNA_ID'].strip()
                        target_id = row['Target_Gene_ID'].strip()

                        lncrna_gene_id = self._get_gene_id(species_id, lncrna_id)
                        target_gene_id = self._get_gene_id(species_id, target_id)

                        if not lncrna_gene_id:
                            self.stats['skipped_rows'] += 1
                            if i <= 10:  # 只记录前10个错误
                                logger.warning(f"第{i}行: lncRNA '{lncrna_id}' 在genes表中不存在")
                            continue

                        if not target_gene_id:
                            self.stats['skipped_rows'] += 1
                            if i <= 10:
                                logger.warning(f"第{i}行: target '{target_id}' 在genes表中不存在")
                            continue

                        # 解析数据
                        regulation_data = {
                            'species_id': species_id,
                            'lncrna_gene_id': lncrna_gene_id,
                            'target_gene_id': target_gene_id,
                            'target_chromosome': row.get('Best_Peak_Chr', '').strip() or None,
                            'target_start': self._safe_int(row.get('Target_Region_Start')),
                            'target_end': self._safe_int(row.get('Target_Region_End')),
                            'tfo_file': row.get('File', '').strip() or None,
                            'total_sites': self._safe_int(row.get('Total_Sites')),
                            'kept_sites': self._safe_int(row.get('Kept_Sites')),
                            'num_peaks': self._safe_int(row.get('Num_Peaks')),
                            'best_peak_num': self._safe_int(row.get('Best_Peak_Num')),
                            'best_avg_ba': self._safe_float(row.get('Best_Avg_BA')),
                            'best_num_sites': self._safe_int(row.get('Best_Num_Sites')),
                            'best_peak_chr': row.get('Best_Peak_Chr', '').strip() or None,
                            'best_peak_start': self._safe_int(row.get('Best_Peak_Start')),
                            'best_peak_end': self._safe_int(row.get('Best_Peak_End')),
                            'best_site_ba': self._safe_float(row.get('Best_Site_BA')),
                            'lncrna_start': self._safe_int(row.get('LncRNA_Start')),
                            'lncrna_end': self._safe_int(row.get('LncRNA_End')),
                            'dna_start': self._safe_int(row.get('DNA_Start')),
                            'dna_end': self._safe_int(row.get('DNA_End')),
                            'binding_affinity': self._safe_float(row.get('Best_Site_BA')),
                        }

                        regulations.append(regulation_data)

                        # 存储序列数据（如果需要）
                        if store_sequences:
                            sequence_data = {
                                'lncrna_sequence': row.get('LncRNA_Sequence', '').strip() or None,
                                'dna_sequence': row.get('DNA_Sequence', '').strip() or None,
                            }
                            sequences.append(sequence_data)

                    except Exception as e:
                        self.stats['failed_rows'] += 1
                        error_msg = f"第{i}行解析失败: {e}"
                        if len(self.stats['errors']) < 100:  # 只记录前100个错误
                            self.stats['errors'].append(error_msg)
                        if i <= 10:
                            logger.warning(error_msg)

                    # 在第一次插入前创建批次
                    if batch_id is None and len(regulations) > 0 and not dry_run:
                        detected_species_id = regulations[0]['species_id']
                        batch_id = self._create_batch(batch_name, detected_species_id, file_path)
                        logger.info(f"批次已创建: batch_id={batch_id}")

                    # 进度反馈
                    if i % 10000 == 0:
                        logger.info(f"已读取 {i} 行, 有效={len(regulations)}, 跳过={self.stats['skipped_rows']}")

                    # 批量插入（减少内存占用）
                    if len(regulations) >= batch_size and not dry_run:
                        self._batch_insert(regulations, sequences if store_sequences else None, batch_id)
                        regulations = []
                        sequences = []

                    # 周期性提交（创建检查点）
                    if commit_every > 0 and not dry_run:
                        records_since_commit = self.stats['regulations_inserted'] - committed_count
                        if records_since_commit >= commit_every:
                            self.conn.commit()
                            committed_count = self.stats['regulations_inserted']
                            self._update_batch(batch_id, 'in_progress', committed_count)
                            logger.info(f"检查点: 已提交 {committed_count} 条记录 (当前行: {current_row})")

            logger.info(f"文件读取完成: 总行数={self.stats['total_rows']}, "
                       f"待插入={len(regulations)}, 跳过={self.stats['skipped_rows']}, "
                       f"失败={self.stats['failed_rows']}")

            if dry_run:
                logger.info("试运行模式，不实际写入数据")
                return

            # 如果还没有创建批次（所有数据都被跳过的情况），现在创建
            if batch_id is None and not dry_run:
                detected_species_id = regulations[0]['species_id'] if regulations else 1
                batch_id = self._create_batch(batch_name, detected_species_id, file_path)
                logger.info(f"延迟创建批次: batch_id={batch_id}")

            # 插入剩余数据
            if regulations and not dry_run:
                self._batch_insert(regulations, sequences if store_sequences else None, batch_id)

            # 统一提交事务
            if not dry_run:
                self.conn.commit()
                logger.info("所有数据已提交")

            # 更新批次状态为完成
            if batch_id is not None:
                self._update_batch(batch_id, 'completed', self.stats['regulations_inserted'])

            logger.info(f"导入完成! regulations={self.stats['regulations_inserted']}, "
                       f"sequences={self.stats['sequences_inserted']}")

        except Exception as e:
            # 异常时回滚未提交事务并标记批次失败
            logger.error(f"导入过程出错 (行 {current_row}): {e}")
            if not dry_run:
                self.conn.rollback()
                logger.info(f"事务已回滚（仅未提交部分，已提交 {committed_count} 条）")

                # 标记批次失败，记录已提交数量和断点信息
                if batch_id is not None:
                    self._update_batch(batch_id, 'failed', committed_count)
                    # 设置错误详情，包含断点续传提示
                    error_detail = (
                        f"PARTIAL_IMPORT: {committed_count} records committed before error at row {current_row}. "
                        f"Resume with: --skip-rows={current_row - 1}"
                    )
                    self._set_batch_error(batch_id, error_detail)
                    logger.info(f"批次 {batch_id} 已标记为失败")
                    logger.info(f"断点续传提示: python import_regulations.py --file {file_path} --skip-rows={current_row - 1}")
            raise

    def _batch_insert(self, regulations: List[Dict], sequences: Optional[List[Dict]], batch_id: Optional[int]):
        """
        批量插入数据

        使用 ON CONFLICT DO NOTHING 防止重复导入。
        去重基于 (species_id, lncrna_gene_id, target_gene_id, lncrna_start, lncrna_end, dna_start, dna_end) 组合。

        注意：需要在数据库中创建唯一约束：
        CREATE UNIQUE INDEX IF NOT EXISTS idx_regulations_unique_key
        ON regulations (species_id, lncrna_gene_id, target_gene_id, lncrna_start, lncrna_end, dna_start, dna_end);

        修复说明 (2025-12-13):
        原实现使用 RETURNING 获取插入的 regulation_id，但当发生 ON CONFLICT DO NOTHING 时，
        RETURNING 只返回实际插入的行，无法建立与原始序列列表的正确对应关系。
        修复方案：使用临时表传递行索引，确保每个 regulation_id 能正确映射到其对应的 sequence。

        Args:
            regulations: 调控关系数据列表
            sequences: 序列数据列表（可选）
            batch_id: 批次 ID
        """
        cursor = self.conn.cursor()

        try:
            # 准备regulations数据，添加行索引以便追踪序列对应关系
            reg_values = []
            for idx, reg in enumerate(regulations):
                reg_values.append((
                    idx,  # 行索引，用于追踪序列对应关系
                    batch_id,
                    reg['species_id'],
                    reg['lncrna_gene_id'],
                    reg['target_gene_id'],
                    reg['target_chromosome'],
                    reg['target_start'],
                    reg['target_end'],
                    reg['tfo_file'],
                    reg['total_sites'],
                    reg['kept_sites'],
                    reg['num_peaks'],
                    reg['best_peak_num'],
                    reg['best_avg_ba'],
                    reg['best_num_sites'],
                    reg['best_peak_chr'],
                    reg['best_peak_start'],
                    reg['best_peak_end'],
                    reg['best_site_ba'],
                    reg['lncrna_start'],
                    reg['lncrna_end'],
                    reg['dna_start'],
                    reg['dna_end'],
                    reg['binding_affinity'],
                ))

            # 创建临时表存储待插入数据及其行索引
            cursor.execute("""
                CREATE TEMP TABLE IF NOT EXISTS temp_regulations_batch (
                    row_idx INTEGER,
                    batch_id INTEGER,
                    species_id INTEGER,
                    lncrna_gene_id INTEGER,
                    target_gene_id INTEGER,
                    target_chromosome VARCHAR(20),
                    target_start BIGINT,
                    target_end BIGINT,
                    tfo_file VARCHAR(255),
                    total_sites INTEGER,
                    kept_sites INTEGER,
                    num_peaks INTEGER,
                    best_peak_num INTEGER,
                    best_avg_ba DECIMAL(10, 4),
                    best_num_sites INTEGER,
                    best_peak_chr VARCHAR(20),
                    best_peak_start BIGINT,
                    best_peak_end BIGINT,
                    best_site_ba DECIMAL(10, 4),
                    lncrna_start INTEGER,
                    lncrna_end INTEGER,
                    dna_start BIGINT,
                    dna_end BIGINT,
                    binding_affinity DECIMAL(10, 4)
                ) ON COMMIT DELETE ROWS
            """)

            # 清空临时表（以防之前的批次未清理）
            cursor.execute("TRUNCATE temp_regulations_batch")

            # 批量插入到临时表
            execute_values(cursor, """
                INSERT INTO temp_regulations_batch (
                    row_idx, batch_id, species_id, lncrna_gene_id, target_gene_id,
                    target_chromosome, target_start, target_end, tfo_file,
                    total_sites, kept_sites, num_peaks, best_peak_num,
                    best_avg_ba, best_num_sites, best_peak_chr,
                    best_peak_start, best_peak_end, best_site_ba,
                    lncrna_start, lncrna_end, dna_start, dna_end,
                    binding_affinity
                )
                VALUES %s
            """, reg_values)

            # 从临时表插入到正式表
            # 修复 (2025-12-13):
            #   1. 使用 DISTINCT ON 去除批次内重复（保留最小 row_idx）
            #   2. 使用 CTE + JOIN 代替子查询，确保 row_idx 映射唯一确定
            cursor.execute("""
                WITH deduplicated AS (
                    -- 批次内去重：对每个唯一键只保留最小 row_idx 的行
                    SELECT DISTINCT ON (
                        species_id, lncrna_gene_id, target_gene_id,
                        lncrna_start, lncrna_end, dna_start, dna_end
                    )
                        row_idx, batch_id, species_id, lncrna_gene_id, target_gene_id,
                        target_chromosome, target_start, target_end, tfo_file,
                        total_sites, kept_sites, num_peaks, best_peak_num,
                        best_avg_ba, best_num_sites, best_peak_chr,
                        best_peak_start, best_peak_end, best_site_ba,
                        lncrna_start, lncrna_end, dna_start, dna_end,
                        binding_affinity
                    FROM temp_regulations_batch
                    ORDER BY species_id, lncrna_gene_id, target_gene_id,
                             lncrna_start, lncrna_end, dna_start, dna_end,
                             row_idx  -- 保留最小 row_idx
                ),
                inserted AS (
                    INSERT INTO regulations (
                        batch_id, species_id, lncrna_gene_id, target_gene_id,
                        target_chromosome, target_start, target_end, tfo_file,
                        total_sites, kept_sites, num_peaks, best_peak_num,
                        best_avg_ba, best_num_sites, best_peak_chr,
                        best_peak_start, best_peak_end, best_site_ba,
                        lncrna_start, lncrna_end, dna_start, dna_end,
                        binding_affinity
                    )
                    SELECT
                        batch_id, species_id, lncrna_gene_id, target_gene_id,
                        target_chromosome, target_start, target_end, tfo_file,
                        total_sites, kept_sites, num_peaks, best_peak_num,
                        best_avg_ba, best_num_sites, best_peak_chr,
                        best_peak_start, best_peak_end, best_site_ba,
                        lncrna_start, lncrna_end, dna_start, dna_end,
                        binding_affinity
                    FROM deduplicated t
                    WHERE NOT EXISTS (
                        SELECT 1 FROM regulations r
                        WHERE r.species_id = t.species_id
                          AND r.lncrna_gene_id = t.lncrna_gene_id
                          AND r.target_gene_id = t.target_gene_id
                          -- NULL 安全比较：IS NOT DISTINCT FROM 将 NULL 视为相等
                          AND r.lncrna_start IS NOT DISTINCT FROM t.lncrna_start
                          AND r.lncrna_end IS NOT DISTINCT FROM t.lncrna_end
                          AND r.dna_start IS NOT DISTINCT FROM t.dna_start
                          AND r.dna_end IS NOT DISTINCT FROM t.dna_end
                    )
                    RETURNING regulation_id, species_id, lncrna_gene_id, target_gene_id,
                              lncrna_start, lncrna_end, dna_start, dna_end
                )
                -- JOIN back to deduplicated to get the unique row_idx
                SELECT i.regulation_id, d.row_idx
                FROM inserted i
                JOIN deduplicated d ON (
                    i.species_id = d.species_id
                    AND i.lncrna_gene_id = d.lncrna_gene_id
                    AND i.target_gene_id = d.target_gene_id
                    -- NULL 安全比较：IS NOT DISTINCT FROM 将 NULL 视为相等
                    AND i.lncrna_start IS NOT DISTINCT FROM d.lncrna_start
                    AND i.lncrna_end IS NOT DISTINCT FROM d.lncrna_end
                    AND i.dna_start IS NOT DISTINCT FROM d.dna_start
                    AND i.dna_end IS NOT DISTINCT FROM d.dna_end
                )
            """)

            # 获取插入结果：(regulation_id, row_idx) 的列表
            inserted_rows = cursor.fetchall()

            # 统计实际插入数量（可能因为去重而少于提交数量）
            actual_inserted = len(inserted_rows)
            skipped_duplicates = len(reg_values) - actual_inserted
            self.stats['regulations_inserted'] += actual_inserted

            if skipped_duplicates > 0:
                if 'duplicates_skipped' not in self.stats:
                    self.stats['duplicates_skipped'] = 0
                self.stats['duplicates_skipped'] += skipped_duplicates
                logger.debug(f"跳过 {skipped_duplicates} 条重复记录")

            # 插入sequences（如果有且有成功插入的 regulation）
            if sequences and inserted_rows:
                seq_values = []
                # 使用 row_idx 正确映射 regulation_id 到对应的 sequence
                for reg_id, row_idx in inserted_rows:
                    if row_idx is not None and row_idx < len(sequences):
                        seq = sequences[row_idx]
                        if seq['lncrna_sequence'] or seq['dna_sequence']:
                            seq_values.append((
                                reg_id,
                                seq['lncrna_sequence'],
                                seq['dna_sequence']
                            ))

                if seq_values:
                    execute_values(cursor, """
                        INSERT INTO sequences (regulation_id, lncrna_sequence, dna_sequence)
                        VALUES %s
                        ON CONFLICT (regulation_id) DO UPDATE SET
                            lncrna_sequence = EXCLUDED.lncrna_sequence,
                            dna_sequence = EXCLUDED.dna_sequence
                    """, seq_values)

                    self.stats['sequences_inserted'] += len(seq_values)

            # 不在这里commit，由调用者统一管理事务

        except Exception as e:
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
        print("Regulations数据导入统计")
        print("="*60)
        print(f"总行数:             {self.stats['total_rows']}")
        print(f"regulations插入:    {self.stats['regulations_inserted']}")
        print(f"sequences插入:      {self.stats['sequences_inserted']}")
        print(f"重复跳过:           {self.stats.get('duplicates_skipped', 0)}")
        print(f"跳过:               {self.stats['skipped_rows']}")
        print(f"失败:               {self.stats['failed_rows']}")
        print(f"错误数:             {len(self.stats['errors'])}")

        if self.stats['errors']:
            print("\n错误详情（前20条）:")
            for error in self.stats['errors'][:20]:
                print(f"  - {error}")

        print("="*60 + "\n")


def main():
    parser = argparse.ArgumentParser(description='导入Regulations数据')
    parser.add_argument('--file', required=True, help='Regulations TSV文件路径')
    parser.add_argument('--batch-name', help='批次名称')
    parser.add_argument('--species', help='物种代码（human/chimp/macaque/marmoset）')
    parser.add_argument('--host', default='localhost', help='数据库主机')
    parser.add_argument('--port', default='5432', help='数据库端口')
    parser.add_argument('--dbname', default='lncrna_production', help='数据库名称')
    parser.add_argument('--user', required=True, help='数据库用户')
    parser.add_argument('--password', help='数据库密码（可选，使用.pgpass）')
    parser.add_argument('--store-sequences', action='store_true', help='是否存储序列数据')
    parser.add_argument('--batch-size', type=int, default=5000, help='批量插入大小')
    parser.add_argument('--commit-every', type=int, default=50000,
                       help='每多少条记录提交一次（创建检查点，默认50000，0=最后统一提交）')
    parser.add_argument('--skip-rows', type=int, default=0,
                       help='跳过前N行（用于断点续传）')
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

    importer = RegulationsImporter(db_config)

    try:
        importer.connect()

        importer.import_file(
            file_path=args.file,
            batch_name=args.batch_name,
            species_code=args.species,
            dry_run=args.dry_run,
            store_sequences=args.store_sequences,
            batch_size=args.batch_size,
            commit_every=args.commit_every,
            skip_rows=args.skip_rows
        )

        importer.print_stats()

        # 验证结果
        if not args.dry_run:
            cursor = importer.conn.cursor()

            cursor.execute("""
                SELECT s.species_code, COUNT(*)
                FROM regulations r
                JOIN species s ON r.species_id = s.species_id
                GROUP BY s.species_code
            """)
            results = cursor.fetchall()

            print("\n数据库验证 - Regulations按物种统计:")
            print("-" * 60)
            for species, count in results:
                print(f"  {species}: {count:,} 条")

            cursor.execute("SELECT COUNT(*) FROM sequences")
            seq_count = cursor.fetchone()[0]
            print(f"\nSequences表: {seq_count:,} 条")

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
