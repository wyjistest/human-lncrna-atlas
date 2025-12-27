"""
ETL基类模板
============

提供统一的数据导入接口和错误处理机制

版本: v2.3
日期: 2025-11-20
"""

import psycopg2
from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Tuple, Iterator
import logging
import csv
from pathlib import Path

from etl.templates.batch_manager import BatchManager

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class BaseImporter(ABC):
    """
    ETL基类 - 所有导入器的父类

    子类需实现:
    - parse_row(): 解析单行数据
    - get_batch_type(): 返回批次类型
    - validate_data(): 数据验证逻辑
    """

    def __init__(self, db_config: Dict[str, str]):
        """
        初始化导入器

        Args:
            db_config: 数据库配置 {'host', 'port', 'dbname', 'user', 'password'}
        """
        self.db_config = db_config
        self.conn: Optional[psycopg2.extensions.connection] = None
        self.stats = {
            'total_rows': 0,
            'imported_rows': 0,
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

    @abstractmethod
    def parse_row(self, row: Dict) -> Optional[Dict]:
        """
        解析单行数据

        Args:
            row: 原始数据行（字典格式）

        Returns:
            解析后的数据（字典）或None（跳过该行）

        Raises:
            ValueError: 数据格式错误
        """
        pass

    @abstractmethod
    def get_batch_type(self) -> str:
        """返回批次类型（regulations, traits, genes等）"""
        pass

    @abstractmethod
    def validate_data(self, data: List[Dict]) -> Tuple[List[Dict], List[str]]:
        """
        验证数据

        Args:
            data: 待验证的数据列表

        Returns:
            (valid_data, errors): 有效数据和错误信息列表
        """
        pass

    def load_csv(self, file_path: str, encoding: str = 'utf-8',
                 delimiter: str = '\t', skip_rows: int = 0) -> List[Dict]:
        """
        从CSV文件加载数据

        Args:
            file_path: CSV文件路径
            encoding: 文件编码
            delimiter: 分隔符
            skip_rows: 跳过的行数（如标题行）

        Returns:
            数据列表（字典格式）
        """
        return list(self.iter_csv(file_path, encoding=encoding, delimiter=delimiter, skip_rows=skip_rows))

    def iter_csv(
        self,
        file_path: str,
        *,
        encoding: str = 'utf-8',
        delimiter: str = '\t',
        skip_rows: int = 0,
    ) -> Iterator[Dict]:
        """
        从CSV文件逐行解析数据（流式，避免一次性加载到内存）

        Notes:
        - 仅 yield parse_row() 返回的有效数据（None 表示跳过）
        - 统计信息（total_rows/skipped_rows/failed_rows）与 load_csv() 保持一致
        """
        logger.info(f"加载文件: {file_path}")

        with open(file_path, 'r', encoding=encoding) as f:
            reader = csv.DictReader(f, delimiter=delimiter)

            # 跳过指定行数
            for _ in range(skip_rows):
                next(reader, None)

            for i, row in enumerate(reader, start=1):
                self.stats['total_rows'] += 1

                try:
                    parsed = self.parse_row(row)
                    if parsed:
                        yield parsed
                    else:
                        self.stats['skipped_rows'] += 1

                except Exception as e:
                    self.stats['failed_rows'] += 1
                    error_msg = f"第{i}行解析失败: {e}"
                    self.stats['errors'].append(error_msg)
                    logger.warning(error_msg)

                # 进度反馈
                if i % 10000 == 0:
                    logger.info(f"已读取 {i} 行...")

        logger.info(
            f"文件读取完成: 总行数={self.stats['total_rows']}, 跳过={self.stats['skipped_rows']}, "
            f"失败={self.stats['failed_rows']}"
        )

    def import_data(self, file_path: str, batch_name: Optional[str] = None,
                   species_id: Optional[int] = None,
                   dry_run: bool = False,
                   batch_size: Optional[int] = 10000) -> Dict:
        """
        执行完整的导入流程

        Args:
            file_path: 数据文件路径
            batch_name: 批次名称（如不提供则自动生成）
            species_id: 物种ID
            dry_run: 是否为试运行（不实际写入数据库）
            batch_size: 分批大小（默认 10000）。设为 None 表示全量加载到内存后再处理（不建议大文件）。

        Returns:
            导入统计信息字典
        """
        if batch_name is None:
            batch_name = f"{self.get_batch_type()} Import {Path(file_path).stem}"

        # 1. 连接数据库
        self.connect()

        try:
            # 2. 加载/验证/导入（支持分批，降低内存峰值）
            if batch_size is not None and batch_size <= 0:
                raise ValueError("batch_size must be > 0 or None")

            # Dry-run: 仅解析与验证，不创建批次、不写入数据库
            if dry_run:
                if batch_size is None:
                    data = self.load_csv(file_path)
                    if not data:
                        logger.warning("没有数据需要导入")
                        return self.stats

                    valid_data, errors = self.validate_data(data)
                    self.stats['errors'].extend(errors)

                    if not valid_data:
                        logger.error("所有数据验证失败，终止导入")
                        return self.stats

                    logger.info(f"数据验证完成: 有效={len(valid_data)}, 无效={len(errors)}")
                else:
                    buffer: List[Dict] = []
                    for parsed in self.iter_csv(file_path):
                        buffer.append(parsed)
                        if len(buffer) < batch_size:
                            continue
                        _, errors = self.validate_data(buffer)
                        self.stats['errors'].extend(errors)
                        buffer.clear()

                    if buffer:
                        _, errors = self.validate_data(buffer)
                        self.stats['errors'].extend(errors)

                logger.info("试运行模式，不实际写入数据")
                return self.stats

            imported_total = 0
            with BatchManager(self.conn, batch_name, self.get_batch_type(),
                              species_id, file_path) as batch:

                if batch_size is None:
                    data = self.load_csv(file_path)
                    if not data:
                        logger.warning("没有数据需要导入")
                        return self.stats

                    valid_data, errors = self.validate_data(data)
                    self.stats['errors'].extend(errors)

                    if not valid_data:
                        logger.error("所有数据验证失败，终止导入")
                        return self.stats

                    logger.info(f"数据验证完成: 有效={len(valid_data)}, 无效={len(errors)}")

                    self._insert_data(valid_data, batch)
                    batch.add_records(len(valid_data))
                    imported_total += len(valid_data)

                else:
                    buffer: List[Dict] = []
                    for parsed in self.iter_csv(file_path):
                        buffer.append(parsed)
                        if len(buffer) < batch_size:
                            continue

                        valid_batch, errors = self.validate_data(buffer)
                        self.stats['errors'].extend(errors)
                        if valid_batch:
                            self._insert_data(valid_batch, batch)
                            batch.add_records(len(valid_batch))
                            imported_total += len(valid_batch)
                        buffer.clear()

                    if buffer:
                        valid_batch, errors = self.validate_data(buffer)
                        self.stats['errors'].extend(errors)
                        if valid_batch:
                            self._insert_data(valid_batch, batch)
                            batch.add_records(len(valid_batch))
                            imported_total += len(valid_batch)

                self.stats['imported_rows'] = imported_total
                logger.info(f"批次 {batch.get_batch_id()} 导入完成: imported_rows={imported_total}")

            # 5. 数据质量检查
            self._run_quality_checks()

        except Exception as e:
            logger.error(f"导入失败: {e}")
            self.stats['errors'].append(str(e))
            raise

        finally:
            self.disconnect()

        return self.stats

    @abstractmethod
    def _insert_data(self, data: List[Dict], batch: BatchManager):
        """
        实际插入数据到数据库

        Args:
            data: 待插入的数据
            batch: 批次管理器实例
        """
        pass

    def _run_quality_checks(self):
        """运行数据质量检查（子类应覆盖此方法添加具体检查）"""
        # 默认实现不执行任何检查，避免误导性的"通过"日志
        # 子类应覆盖此方法并调用具体的check_*方法
        # 例如:
        # logger.info("运行数据质量检查...")
        # checker = DataQualityChecker(self.conn)
        # checker.check_required_fields('genes', ['gene_name', 'gene_ensembl_id'])
        # checker.check_duplicates('genes', ['species_id', 'gene_ensembl_id'])
        # report = checker.generate_report()
        # logger.info(f"\n{report}")
        pass

    def print_stats(self):
        """打印导入统计信息"""
        print("\n" + "="*60)
        print("导入统计")
        print("="*60)
        print(f"总行数:     {self.stats['total_rows']}")
        print(f"导入成功:   {self.stats['imported_rows']}")
        print(f"跳过:       {self.stats['skipped_rows']}")
        print(f"失败:       {self.stats['failed_rows']}")
        print(f"错误数:     {len(self.stats['errors'])}")

        if self.stats['errors']:
            print("\n错误详情（前10条）:")
            for error in self.stats['errors'][:10]:
                print(f"  - {error}")

        print("="*60 + "\n")


# 工具函数
def safe_int(value: str, default: Optional[int] = None) -> Optional[int]:
    """安全转换为整数"""
    try:
        return int(value) if value and value.strip() else default
    except (ValueError, TypeError):
        return default


def safe_float(value: str, default: Optional[float] = None) -> Optional[float]:
    """安全转换为浮点数"""
    try:
        return float(value) if value and value.strip() else default
    except (ValueError, TypeError):
        return default


def safe_str(value: str, default: str = '') -> str:
    """安全转换为字符串"""
    return str(value).strip() if value else default
