#!/usr/bin/env python3
"""
修复黑猩猩空DNA序列问题

从 8chimpManualProPromoterSeq 目录读取DNA文件，
匹配空DNA序列记录（考虑1bp坐标偏差），
更新数据库中的sequences表。

Usage:
    python fix_chimp_empty_dna.py [--dna-dir /path/to/dna/files]

Environment Variables:
    CHIMP_DNA_DIR: DNA文件目录路径
    DB_HOST, DB_PORT, DB_USER, DB_NAME: 数据库连接配置
"""

import os
import psycopg2
from psycopg2.extras import execute_batch

# 配置 - 优先使用环境变量
DNA_DIR = os.environ.get('CHIMP_DNA_DIR', './data/chimp/8chimpManualProPromoterSeq/')
BATCH_FILE = os.environ.get('CHIMP_BATCH_FILE', './data/chimp_batch_BA50.txt')

# Phase 9.13: 添加 DB_PASSWORD 支持，解决在启用密码的生产库中无法运行的问题
# 如果未设置 DB_PASSWORD 且需要密码认证，可使用 .pgpass 文件或 PGPASSWORD 环境变量
DB_CONFIG = {
    'host': os.environ.get('DB_HOST', 'localhost'),
    'port': int(os.environ.get('DB_PORT', '5432')),
    'user': os.environ.get('DB_USER', 'amax'),
    'password': os.environ.get('DB_PASSWORD', ''),  # 空字符串时 psycopg2 会尝试 .pgpass
    'dbname': os.environ.get('DB_NAME', 'lncrna_production')
}
# 如果密码为空，移除该键以允许 .pgpass 或 trust 认证生效
if not DB_CONFIG['password']:
    del DB_CONFIG['password']


def load_dna_files(dna_dir):
    """加载DNA文件，建立坐标到文件路径的映射"""
    dna_map = {}  # (gene_id, start, end) -> (file_path, seq_start_in_file)

    for filename in os.listdir(dna_dir):
        if not filename.endswith('.fa'):
            continue

        parts = filename.replace('.fa', '').split('-')
        if len(parts) >= 3:
            gene_id = parts[0]
            file_start = int(parts[1])
            file_end = int(parts[2])

            filepath = os.path.join(dna_dir, filename)

            # 读取文件获取header中的实际坐标
            with open(filepath, 'r') as f:
                header = f.readline().strip()
                sequence = ''.join(line.strip() for line in f if not line.startswith('>'))

            # 解析header获取序列起始位置
            # 格式: >chimp_pantro5_singleMerged|chr10_NW_015973899v1_random|32270-38259
            seq_start = file_start
            if '|' in header:
                parts_h = header.split('|')
                if len(parts_h) >= 3:
                    coord_part = parts_h[-1]
                    if '-' in coord_part:
                        try:
                            seq_start = int(coord_part.split('-')[0])
                        except ValueError:
                            pass

            # 存储映射（考虑±1坐标容差）
            for offset in range(-1, 2):
                key = (gene_id, file_start + offset, file_end)
                if key not in dna_map:
                    dna_map[key] = (filepath, sequence, seq_start)

    return dna_map


def get_empty_dna_regulations(conn):
    """获取所有空DNA序列的regulation记录"""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            r.regulation_id,
            g.gene_ensembl_id as target_gene,
            r.dna_start,
            r.dna_end,
            -- 从文件名解析的region坐标（用于匹配DNA文件）
            -- 需要从原始数据获取
            r.dna_start as region_start,
            r.dna_end as region_end
        FROM sequences seq
        JOIN regulations r ON seq.regulation_id = r.regulation_id
        JOIN genes g ON r.target_gene_id = g.gene_id
        JOIN species s ON r.species_id = s.species_id
        WHERE s.species_code = 'chimp'
        AND (seq.dna_sequence IS NULL OR seq.dna_sequence = '')
    """)
    return cursor.fetchall()


def extract_dna_sequence(sequence, seq_start, dna_start, dna_end):
    """从完整序列中提取指定坐标的DNA片段"""
    # 计算偏移量
    offset_start = dna_start - seq_start
    offset_end = dna_end - seq_start

    if offset_start < 0:
        offset_start = 0
    if offset_end > len(sequence):
        offset_end = len(sequence)

    if offset_start >= len(sequence) or offset_end <= 0:
        return None

    return sequence[offset_start:offset_end]


def main():
    print("=" * 60)
    print("修复黑猩猩空DNA序列")
    print("=" * 60)

    # 1. 加载DNA文件
    print("\n1. 加载DNA文件...")
    dna_map = load_dna_files(DNA_DIR)
    print(f"   找到 {len(dna_map)} 个坐标映射")

    # 显示可用文件
    seen_files = set()
    for key, (filepath, seq, start) in dna_map.items():
        if filepath not in seen_files:
            seen_files.add(filepath)
            print(f"   - {os.path.basename(filepath)}")

    # 2. 连接数据库
    print("\n2. 连接数据库...")
    conn = psycopg2.connect(**DB_CONFIG)

    # 3. 从原始文件读取空DNA记录的完整信息
    print("\n3. 读取原始数据文件中的空DNA记录...")
    import csv

    empty_records = []
    with open(BATCH_FILE, 'r') as f:
        reader = csv.DictReader(f, delimiter='\t')
        for row in reader:
            dna_seq = row.get('DNA_Sequence', '').strip()
            if not dna_seq or dna_seq == 'None':
                empty_records.append({
                    'lncrna_id': row.get('LncRNA_ID', ''),
                    'target_gene': row.get('Target_Gene_ID', ''),
                    'region_start': int(row.get('Target_Region_Start', 0)),
                    'region_end': int(row.get('Target_Region_End', 0)),
                    'dna_start': int(row.get('DNA_Start', 0)),
                    'dna_end': int(row.get('DNA_End', 0)),
                })

    print(f"   找到 {len(empty_records)} 条空DNA记录")

    # 4. 获取数据库中的regulation_id映射
    print("\n4. 构建数据库映射...")
    cursor = conn.cursor()

    # 获取基因ID映射
    cursor.execute("""
        SELECT gene_ensembl_id, gene_id FROM genes WHERE species_id = 2
    """)
    gene_map = {row[0]: row[1] for row in cursor.fetchall()}
    # 添加去后缀的映射
    for ensembl_id, gene_id in list(gene_map.items()):
        if ensembl_id.endswith('_chimp'):
            gene_map[ensembl_id.replace('_chimp', '')] = gene_id

    # 获取regulation映射
    cursor.execute("""
        SELECT regulation_id, lncrna_gene_id, target_gene_id, dna_start, dna_end
        FROM regulations WHERE species_id = 2
    """)
    reg_map = {}
    for row in cursor.fetchall():
        reg_id, lnc_id, tgt_id, dna_s, dna_e = row
        reg_map[(lnc_id, tgt_id, dna_s, dna_e)] = reg_id

    print(f"   基因映射: {len(gene_map)} 条")
    print(f"   Regulation映射: {len(reg_map)} 条")

    # 5. 匹配并提取DNA序列
    print("\n5. 匹配DNA序列...")
    updates = []
    matched = 0
    not_matched_file = 0
    not_matched_reg = 0

    for rec in empty_records:
        target_gene = rec['target_gene']
        region_start = rec['region_start']
        region_end = rec['region_end']
        dna_start = rec['dna_start']
        dna_end = rec['dna_end']
        lncrna_id = rec['lncrna_id']

        # 查找DNA文件（考虑±1坐标偏差）
        dna_info = None
        for offset in range(-1, 2):
            key = (target_gene, region_start + offset, region_end)
            if key in dna_map:
                dna_info = dna_map[key]
                break

        if not dna_info:
            not_matched_file += 1
            continue

        filepath, sequence, seq_start = dna_info

        # 提取DNA片段
        dna_seq = extract_dna_sequence(sequence, seq_start, dna_start, dna_end)
        if not dna_seq:
            not_matched_file += 1
            continue

        # 查找regulation_id
        lnc_gene_id = gene_map.get(lncrna_id) or gene_map.get(lncrna_id.replace('_chimp', ''))
        tgt_gene_id = gene_map.get(target_gene)

        if not lnc_gene_id or not tgt_gene_id:
            not_matched_reg += 1
            continue

        reg_key = (lnc_gene_id, tgt_gene_id, dna_start, dna_end)
        reg_id = reg_map.get(reg_key)

        if not reg_id:
            not_matched_reg += 1
            continue

        updates.append((dna_seq, reg_id))
        matched += 1

    print(f"   匹配成功: {matched}")
    print(f"   文件未找到: {not_matched_file}")
    print(f"   Regulation未找到: {not_matched_reg}")

    # 6. 更新数据库
    if updates:
        print(f"\n6. 更新数据库 ({len(updates)} 条记录)...")

        cursor = conn.cursor()
        execute_batch(cursor, """
            UPDATE sequences
            SET dna_sequence = %s
            WHERE regulation_id = %s
        """, updates, page_size=100)

        conn.commit()
        print("   ✓ 更新完成")
    else:
        print("\n6. 没有需要更新的记录")

    # 7. 验证结果
    print("\n7. 验证结果...")
    cursor.execute("""
        SELECT COUNT(*) FROM sequences seq
        JOIN regulations r ON seq.regulation_id = r.regulation_id
        JOIN species s ON r.species_id = s.species_id
        WHERE s.species_code = 'chimp'
        AND (seq.dna_sequence IS NULL OR seq.dna_sequence = '')
    """)
    remaining = cursor.fetchone()[0]
    print(f"   剩余空DNA序列: {remaining}")

    conn.close()
    print("\n" + "=" * 60)
    print("修复完成!")
    print("=" * 60)


if __name__ == '__main__':
    main()
