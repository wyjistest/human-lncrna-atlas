#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Verification script - Check batch heatmap matrix API implementation
"""

import os
import sys
import re


def check_file_exists(path: str, description: str) -> bool:
    """检查文件是否存在"""
    if os.path.exists(path):
        print(f"✓ {description}: {path}")
        return True
    else:
        print(f"✗ {description} NOT FOUND: {path}")
        return False


def check_content(file_path: str, patterns: list, description: str) -> bool:
    """检查文件中是否包含指定的内容"""
    try:
        with open(file_path, 'r') as f:
            content = f.read()

        all_found = True
        for pattern, pattern_desc in patterns:
            if re.search(pattern, content, re.MULTILINE | re.DOTALL):
                print(f"  ✓ Found: {pattern_desc}")
            else:
                print(f"  ✗ NOT FOUND: {pattern_desc}")
                all_found = False

        return all_found
    except Exception as e:
        print(f"  ✗ Error reading file: {e}")
        return False


def main():
    print("\n" + "=" * 70)
    print("  Batch Heatmap Matrix API - Implementation Verification")
    print("=" * 70)

    # 使用脚本所在目录作为基准，或从环境变量获取
    base_dir = os.environ.get('BACKEND_DIR', os.path.dirname(os.path.abspath(__file__)))
    all_checks_passed = True

    # 1. Check Schema file
    print("\n[1] Checking Schema Definitions...")
    schema_file = f"{base_dir}/app/schemas/chipseq.py"
    all_checks_passed &= check_file_exists(schema_file, "Schema file")

    schema_patterns = [
        (r"class BatchHeatmapMatrixRequest\(BaseModel\):", "BatchHeatmapMatrixRequest class"),
        (r"class BatchHeatmapMatrixResponse\(BaseModel\):", "BatchHeatmapMatrixResponse class"),
        (r'gene_ids: List\[int\].*min_length=1.*max_length=100', "gene_ids field with constraints"),
        (r'marks: List\[str\].*min_length=1.*max_length=8', "marks field with constraints"),
        (r'cell_types: List\[str\].*min_length=1.*max_length=10', "cell_types field with constraints"),
        (r'metric: str.*median_fold_enrichment.*peak_count.*total_coverage_bp.*avg_signal', "metric enum"),
        (r'genes: List\[HeatmapMatrixResponse\]', "genes field in response"),
        (r'total_genes: int', "total_genes field"),
        (r'successful_genes: int', "successful_genes field"),
        (r'failed_genes: List\[int\]', "failed_genes field"),
        (r'query_time_ms: Optional\[int\]', "query_time_ms field"),
    ]

    if check_file_exists(schema_file, "Schema file"):
        all_checks_passed &= check_content(schema_file, schema_patterns, "Schema content")

    # 2. Check Router imports
    print("\n[2] Checking Router Imports...")
    router_file = f"{base_dir}/app/routers/chipseq.py"
    all_checks_passed &= check_file_exists(router_file, "Router file")

    import_patterns = [
        (r'import time', "time module import"),
        (r'BatchHeatmapMatrixRequest', "BatchHeatmapMatrixRequest import"),
        (r'BatchHeatmapMatrixResponse', "BatchHeatmapMatrixResponse import"),
    ]

    if check_file_exists(router_file, "Router file"):
        all_checks_passed &= check_content(router_file, import_patterns, "Router imports")

    # 3. Check Endpoint Implementation
    print("\n[3] Checking Endpoint Implementation...")
    endpoint_patterns = [
        (r'@router\.post\("/genes/batch-heatmap-matrix"', "POST endpoint decorator"),
        (r'def get_batch_gene_heatmap_matrix\(', "Endpoint function definition"),
        (r'request: BatchHeatmapMatrixRequest', "Request parameter"),
        (r'response_model=BatchHeatmapMatrixResponse', "Response model"),
        (r'db: Session = Depends\(get_db\)', "Database dependency"),
    ]

    all_checks_passed &= check_content(router_file, endpoint_patterns, "Endpoint definition")

    # 4. Check Endpoint Logic
    print("\n[4] Checking Endpoint Logic...")
    logic_patterns = [
        (r'start_time = time\.time\(\)', "Performance timing start"),
        (r'Gene\)\.filter\(Gene\.gene_id\.in_\(', "Batch gene loading"),
        (r'for gene_id in request\.gene_ids:', "Gene iteration loop"),
        (r'db\.execute\(query,.*marks.*cell_types', "SQL query execution"),
        (r'combo_stats.*Dict.*Dict.*str', "Data aggregation"),
        (r'statistics\.median', "Median calculation"),
        (r'query_time_ms = int\(\(time\.time\(\) - start_time\) \* 1000\)', "Performance timing end"),
        (r'BatchHeatmapMatrixResponse\(', "Response creation"),
    ]

    all_checks_passed &= check_content(router_file, logic_patterns, "Endpoint logic")

    # 5. Check Test Files
    print("\n[5] Checking Test Files...")
    test_py = f"{base_dir}/test_batch_heatmap.py"
    test_sh = f"{base_dir}/test_batch_heatmap.sh"

    all_checks_passed &= check_file_exists(test_py, "Python test file")
    all_checks_passed &= check_file_exists(test_sh, "Shell test file")

    test_patterns = [
        (r'def test_basic_batch_query\(\):', "Basic query test"),
        (r'def test_single_gene\(\):', "Single gene test"),
        (r'def test_multiple_metrics\(\):', "Multiple metrics test"),
        (r'def test_performance_10_genes\(\):', "Performance test"),
        (r'def test_error_handling\(\):', "Error handling test"),
    ]

    if check_file_exists(test_py, "Python test file"):
        all_checks_passed &= check_content(test_py, test_patterns, "Python test content")

    # 6. Check Documentation
    print("\n[6] Checking Documentation Files...")
    doc_md = f"{base_dir}/BATCH_HEATMAP_API.md"
    summary_md = f"{base_dir}/IMPLEMENTATION_SUMMARY.md"

    all_checks_passed &= check_file_exists(doc_md, "API documentation")
    all_checks_passed &= check_file_exists(summary_md, "Implementation summary")

    doc_patterns = [
        (r'##\s+', "Markdown headers"),
        (r'```python', "Code examples"),
        (r'```bash', "Bash examples"),
        (r'curl.*batch-heatmap-matrix', "cURL examples"),
    ]

    if check_file_exists(doc_md, "API documentation"):
        all_checks_passed &= check_content(doc_md, doc_patterns, "Documentation content")

    # 7. Check GitHub Sync (optional)
    print("\n[7] Checking GitHub Repository Sync...")
    github_backend_dir = os.environ.get("GITHUB_BACKEND_DIR")
    if github_backend_dir:
        print(f"  GitHub backend dir: {github_backend_dir}")
    else:
        github_backend_dir = base_dir
        print(f"  GitHub backend dir: (not set; using BACKEND_DIR) {github_backend_dir}")

    github_schema = os.path.join(github_backend_dir, "app", "schemas", "chipseq.py")
    github_router = os.path.join(github_backend_dir, "app", "routers", "chipseq.py")
    github_test = os.path.join(github_backend_dir, "test_batch_heatmap.py")
    github_doc = os.path.join(github_backend_dir, "BATCH_HEATMAP_API.md")

    all_checks_passed &= check_file_exists(github_schema, "GitHub schema sync")
    all_checks_passed &= check_file_exists(github_router, "GitHub router sync")
    all_checks_passed &= check_file_exists(github_test, "GitHub test sync")
    all_checks_passed &= check_file_exists(github_doc, "GitHub doc sync")

    # 8. Count lines added
    print("\n[8] Code Statistics...")
    try:
        with open(schema_file, 'r') as f:
            schema_lines = len(f.readlines())
        print(f"  Schema file: {schema_lines} lines")

        with open(router_file, 'r') as f:
            router_lines = len(f.readlines())
        print(f"  Router file: {router_lines} lines")

        with open(test_py, 'r') as f:
            test_lines = len(f.readlines())
        print(f"  Test file: {test_lines} lines")

        with open(doc_md, 'r') as f:
            doc_lines = len(f.readlines())
        print(f"  API documentation: {doc_lines} lines")

    except Exception as e:
        print(f"  Error reading file statistics: {e}")

    # Final result
    print("\n" + "=" * 70)
    if all_checks_passed:
        print("  ✓ ALL CHECKS PASSED - Implementation is complete")
        print("=" * 70)
        return 0
    else:
        print("  ✗ SOME CHECKS FAILED - Please review the errors above")
        print("=" * 70)
        return 1


if __name__ == "__main__":
    sys.exit(main())
