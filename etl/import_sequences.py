#!/usr/bin/env python3
"""
补充导入序列数据到 sequences 表
从源文件读取 LncRNA_Sequence 和 DNA_Sequence，匹配已有的 regulations 记录
"""

import os
import csv
import psycopg2
from psycopg2.extras import execute_batch
from typing import Dict, List, Tuple
import argparse

# 数据库配置
DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "user": "amax",
    "password": "",
    "dbname": "lncrna_production"
}

# 源文件配置
SOURCE_FILES = {
    1: "/data/wenyujianData/humanLncAtlas/human_batch_human.txt",      # Human
    2: "/data/wenyujianData/humanLncAtlas/chimp_batch_BA50.txt",       # Chimp
    3: "/data/wenyujianData/humanLncAtlas/macaque_batch_BA50.txt",     # Macaque
    4: "/data/wenyujianData/humanLncAtlas/marmoset_batch_BA50.txt",    # Marmoset
}

# 物种名到 ID 的映射
SPECIES_MAP = {
    'human': 1,
    'chimp': 2,
    'macaque': 3,
    'marmoset': 4,
}


def strip_version(gene_id: str) -> str:
    """去掉基因 ID 的版本号，如 ENSG00000129484.9 -> ENSG00000129484

    支持 ENSG 和 CATG 格式
    """
    if '.' in gene_id and (gene_id.startswith('ENSG') or gene_id.startswith('CATG')):
        return gene_id.rsplit('.', 1)[0]
    return gene_id


def get_gene_id_map(conn, species_id: int) -> Dict[str, int]:
    """获取基因名到 gene_id 的映射

    建立多种格式的映射，以处理不同的基因 ID 格式：
    - 原始 ID
    - 去掉物种后缀（如 _marmoset）
    - 去掉版本号（如 .9）
    """
    cursor = conn.cursor()
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
        # 例如 CATG00000016469.1_marmoset -> CATG00000016469.1
        base_id = ensembl_id
        for suffix in ['_human', '_chimp', '_macaque', '_marmoset', '_chimpanzee']:
            if ensembl_id.endswith(suffix):
                base_id = ensembl_id[:-len(suffix)]
                result[base_id] = gene_id
                break

        # 也建立去掉版本号的映射（如果数据库中有版本号）
        no_ver = strip_version(base_id)
        if no_ver != base_id:
            result[no_ver] = gene_id

    return result


def lookup_gene(gene_map: Dict[str, int], gene_id: str) -> int:
    """查找基因 ID，尝试多种格式"""
    # 先直接查找
    if gene_id in gene_map:
        return gene_map[gene_id]

    # 尝试去掉版本号查找
    no_ver = strip_version(gene_id)
    if no_ver in gene_map:
        return gene_map[no_ver]

    return None


def get_regulation_map(conn, species_id: int) -> Dict[Tuple, int]:
    """获取 regulation 唯一键到 regulation_id 的映射"""
    cursor = conn.cursor()
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


def process_file(conn, species_id: int, filepath: str, batch_size: int = 5000):
    """处理单个源文件，导入序列数据"""
    print(f"\n处理文件: {filepath}")
    print(f"物种 ID: {species_id}")

    # 获取映射
    print("加载基因映射...")
    gene_map = get_gene_id_map(conn, species_id)
    print(f"  基因数: {len(gene_map)}")

    print("加载 regulation 映射...")
    reg_map = get_regulation_map(conn, species_id)
    print(f"  Regulation 数: {len(reg_map)}")

    # 读取文件并匹配
    sequences = []
    matched = 0
    not_matched = 0
    empty_seq = 0

    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter='\t')

        for i, row in enumerate(reader, 1):
            lncrna_id = row.get('LncRNA_ID', '').strip()
            target_id = row.get('Target_Gene_ID', '').strip()
            lncrna_seq = row.get('LncRNA_Sequence', '').strip()
            dna_seq = row.get('DNA_Sequence', '').strip()

            # 跳过空序列
            if (not lncrna_seq or lncrna_seq == 'None') and (not dna_seq or dna_seq == 'None'):
                empty_seq += 1
                continue

            # 清理 None 值
            if lncrna_seq == 'None':
                lncrna_seq = None
            if dna_seq == 'None':
                dna_seq = None

            # 获取 gene_id（使用灵活查找，处理版本号差异）
            lnc_gene_id = lookup_gene(gene_map, lncrna_id)
            tgt_gene_id = lookup_gene(gene_map, target_id)

            if not lnc_gene_id or not tgt_gene_id:
                not_matched += 1
                continue

            # 获取位置信息
            try:
                lnc_start = int(row.get('LncRNA_Start', 0))
                lnc_end = int(row.get('LncRNA_End', 0))
                dna_start = int(row.get('DNA_Start', 0))
                dna_end = int(row.get('DNA_End', 0))
            except (ValueError, TypeError):
                not_matched += 1
                continue

            # 查找 regulation_id
            key = (lnc_gene_id, tgt_gene_id, lnc_start, lnc_end, dna_start, dna_end)
            reg_id = reg_map.get(key)

            if not reg_id:
                not_matched += 1
                continue

            matched += 1
            sequences.append((reg_id, lncrna_seq, dna_seq))

            # 批量插入
            if len(sequences) >= batch_size:
                insert_sequences(conn, sequences)
                print(f"  已处理: {i:,} 行, 匹配: {matched:,}, 插入: {len(sequences)}")
                sequences = []

            if i % 50000 == 0:
                print(f"  进度: {i:,} 行...")

    # 插入剩余数据
    if sequences:
        insert_sequences(conn, sequences)

    print(f"\n完成! 匹配: {matched:,}, 未匹配: {not_matched:,}, 空序列: {empty_seq:,}")
    return matched


def insert_sequences(conn, sequences: List[Tuple]):
    """批量插入序列数据"""
    cursor = conn.cursor()
    execute_batch(cursor, """
        INSERT INTO sequences (regulation_id, lncrna_sequence, dna_sequence)
        VALUES (%s, %s, %s)
        ON CONFLICT (regulation_id) DO UPDATE SET
            lncrna_sequence = EXCLUDED.lncrna_sequence,
            dna_sequence = EXCLUDED.dna_sequence
    """, sequences, page_size=1000)
    conn.commit()


def main():
    parser = argparse.ArgumentParser(description='补充导入序列数据')
    parser.add_argument('--species', type=int, choices=[1, 2, 3, 4],
                        help='指定物种 ID (1=Human, 2=Chimp, 3=Macaque, 4=Marmoset)')
    parser.add_argument('--batch-size', type=int, default=5000, help='批量大小')
    args = parser.parse_args()

    conn = psycopg2.connect(**DB_CONFIG)

    try:
        # 检查当前 sequences 表状态
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM sequences")
        before_count = cursor.fetchone()[0]
        print(f"当前 sequences 表记录数: {before_count:,}")

        total_matched = 0

        if args.species:
            # 处理指定物种
            filepath = SOURCE_FILES.get(args.species)
            if filepath and os.path.exists(filepath):
                total_matched += process_file(conn, args.species, filepath, args.batch_size)
        else:
            # 处理所有物种
            for species_id, filepath in SOURCE_FILES.items():
                if os.path.exists(filepath):
                    total_matched += process_file(conn, species_id, filepath, args.batch_size)
                else:
                    print(f"文件不存在: {filepath}")

        # 检查最终状态
        cursor.execute("SELECT COUNT(*) FROM sequences")
        after_count = cursor.fetchone()[0]
        print(f"\n=== 导入完成 ===")
        print(f"导入前: {before_count:,}")
        print(f"导入后: {after_count:,}")
        print(f"新增: {after_count - before_count:,}")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
