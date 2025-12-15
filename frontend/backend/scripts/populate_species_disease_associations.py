"""
补充其他物种的疾病关联数据

逻辑：
1. 从人类的疾病关联数据中获取所有 core_id（lncRNA和蛋白质编码基因）
2. 通过 core_id 找到这些基因在其他物种的同源基因
3. 为其他物种创建相同的疾病关联记录（复制 trait_id, ontology_id 等信息）
"""
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models import TraitGeneAssociation, Gene, Species
from app.core.config import settings

# 创建数据库连接
engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine)
db = SessionLocal()

def populate_species_associations():
    """补充其他物种的疾病关联数据"""
    
    # 获取所有物种
    species_list = db.query(Species).all()
    human_species_id = 1
    
    print(f"找到 {len(species_list)} 个物种")
    for sp in species_list:
        print(f"  - {sp.species_id}: {sp.display_name}")
    
    # 获取人类的所有疾病关联
    human_associations = db.query(TraitGeneAssociation).filter(
        TraitGeneAssociation.evidence_species_id == human_species_id
    ).all()
    
    print(f"\n人类有 {len(human_associations)} 条疾病关联记录")
    
    # 统计信息
    stats = {sp.species_id: {'added': 0, 'skipped': 0} for sp in species_list if sp.species_id != human_species_id}
    
    # 为每个非人类物种创建关联
    for assoc in human_associations:
        # 获取该 core_id 在其他物种的同源基因
        orthologs = db.query(Gene).filter(
            Gene.core_id == assoc.core_id,
            Gene.species_id != human_species_id
        ).all()
        
        for ortholog in orthologs:
            species_id = ortholog.species_id
            
            # 检查是否已存在该关联
            existing = db.query(TraitGeneAssociation).filter(
                TraitGeneAssociation.core_id == assoc.core_id,
                TraitGeneAssociation.trait_id == assoc.trait_id,
                TraitGeneAssociation.ontology_id == assoc.ontology_id,
                TraitGeneAssociation.evidence_species_id == species_id
            ).first()
            
            if existing:
                stats[species_id]['skipped'] += 1
                continue
            
            # 创建新的关联记录
            new_assoc = TraitGeneAssociation(
                core_id=assoc.core_id,
                trait_id=assoc.trait_id,
                ontology_id=assoc.ontology_id,
                odds_ratio=assoc.odds_ratio,
                fdr=assoc.fdr,
                trait_snp_pvalue=assoc.trait_snp_pvalue,
                ontology_mw_pvalue=assoc.ontology_mw_pvalue,
                ontology_fold_enrichment=assoc.ontology_fold_enrichment,
                literature_support=assoc.literature_support,
                evidence_species_id=species_id,  # 使用同源基因的物种ID
                source_table=assoc.source_table,
                source_row_number=assoc.source_row_number,
            )
            
            db.add(new_assoc)
            stats[species_id]['added'] += 1
    
    # 提交事务
    db.commit()
    
    # 打印统计信息
    print("\n补充完成！统计信息：")
    for sp in species_list:
        if sp.species_id == human_species_id:
            continue
        print(f"\n{sp.display_name} (species_id={sp.species_id}):")
        print(f"  新增: {stats[sp.species_id]['added']} 条")
        print(f"  跳过: {stats[sp.species_id]['skipped']} 条（已存在）")
    
    # 验证结果
    print("\n\n验证结果：")
    for sp in species_list:
        count = db.query(TraitGeneAssociation).filter(
            TraitGeneAssociation.evidence_species_id == sp.species_id
        ).count()
        print(f"{sp.display_name}: {count} 条疾病关联记录")
    
    db.close()

if __name__ == '__main__':
    print("开始补充其他物种的疾病关联数据...\n")
    populate_species_associations()
    print("\n完成！")
