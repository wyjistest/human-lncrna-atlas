#!/usr/bin/env python3
"""
从 FANTOM_CAT.lv3_robust.gtf 更新人类基因的 chromosome, gene_start, gene_end
仅更新 species_id = 1 (人类) 的基因
"""

import re
import psycopg2
from psycopg2.extras import execute_batch
from collections import defaultdict

# 配置
GTF_FILE = "/data/wenyujianData/humanLncAtlas/FANTOM_CAT.lv3_robust.gtf"
DB_CONFIG = {
    "host": "localhost",
    "port": 5432,
    "user": "amax",
    "password": "",
    "dbname": "lncrna_production"
}
HUMAN_SPECIES_ID = 1


def parse_gtf_genes(gtf_path: str) -> dict:
    """解析 GTF 文件，提取基因位置信息

    返回两个字典的合并：
    - 带版本号的 ID (CATG00000000226.1)
    - 不带版本号的 ID (CATG00000000226)
    """
    genes = {}
    gene_id_pattern = re.compile(r'gene_id "([^"]+)"')

    print(f"正在解析 GTF 文件: {gtf_path}")

    with open(gtf_path, 'r') as f:
        for line_num, line in enumerate(f, 1):
            if line.startswith('#'):
                continue

            fields = line.strip().split('\t')
            if len(fields) < 9:
                continue

            # 只处理 gene 类型的记录
            if fields[2] != 'gene':
                continue

            chrom = fields[0]
            start = int(fields[3])
            end = int(fields[4])
            attributes = fields[8]

            # 提取 gene_id
            match = gene_id_pattern.search(attributes)
            if not match:
                continue

            gene_id = match.group(1)
            gene_info = {
                'chromosome': chrom,
                'gene_start': start,
                'gene_end': end
            }

            # 存储带版本号的 ID
            genes[gene_id] = gene_info

            # 也存储不带版本号的 ID (去掉 .1, .2 等后缀)
            base_id = gene_id.rsplit('.', 1)[0] if '.' in gene_id else gene_id
            if base_id not in genes:
                genes[base_id] = gene_info

            if line_num % 50000 == 0:
                print(f"  已处理 {line_num} 行...")

    print(f"从 GTF 解析到基因条目 (含无版本号): {len(genes)} 个")
    return genes


def update_database(genes: dict):
    """更新数据库中的基因位置"""
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    try:
        # 获取数据库中人类基因的 gene_ensembl_id
        cur.execute("""
            SELECT gene_id, gene_ensembl_id
            FROM genes
            WHERE species_id = %s AND gene_ensembl_id IS NOT NULL
        """, (HUMAN_SPECIES_ID,))

        db_genes = cur.fetchall()
        print(f"数据库中人类基因: {len(db_genes)} 个")

        # 准备更新数据
        updates = []
        matched = 0
        not_found = []

        for gene_id, ensembl_id in db_genes:
            if ensembl_id in genes:
                matched += 1
                info = genes[ensembl_id]
                updates.append((
                    info['chromosome'],
                    info['gene_start'],
                    info['gene_end'],
                    gene_id
                ))
            else:
                not_found.append(ensembl_id)

        print(f"匹配成功: {matched} 个")
        print(f"未找到: {len(not_found)} 个")

        if not_found and len(not_found) <= 20:
            print(f"未找到的基因: {not_found}")
        elif not_found:
            print(f"未找到的基因(前20): {not_found[:20]}")

        # 批量更新
        if updates:
            print(f"正在更新 {len(updates)} 条记录...")
            execute_batch(cur, """
                UPDATE genes
                SET chromosome = %s, gene_start = %s, gene_end = %s
                WHERE gene_id = %s
            """, updates, page_size=1000)

            conn.commit()
            print("更新完成!")
        else:
            print("没有需要更新的记录")

        # 验证更新结果
        cur.execute("""
            SELECT COUNT(*) as total,
                   COUNT(gene_start) as has_start,
                   COUNT(gene_end) as has_end,
                   COUNT(chromosome) as has_chrom
            FROM genes
            WHERE species_id = %s
        """, (HUMAN_SPECIES_ID,))

        result = cur.fetchone()
        print(f"\n验证结果 (人类基因):")
        print(f"  总数: {result[0]}")
        print(f"  有 gene_start: {result[1]}")
        print(f"  有 gene_end: {result[2]}")
        print(f"  有 chromosome: {result[3]}")

    except Exception as e:
        conn.rollback()
        print(f"错误: {e}")
        raise
    finally:
        cur.close()
        conn.close()


def main():
    print("=" * 60)
    print("更新人类基因位置信息")
    print("=" * 60)

    # 解析 GTF
    genes = parse_gtf_genes(GTF_FILE)

    # 更新数据库
    update_database(genes)

    print("\n完成!")


if __name__ == "__main__":
    main()
