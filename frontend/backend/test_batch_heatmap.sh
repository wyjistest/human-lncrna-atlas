#!/bin/bash
# Curl test commands for batch heatmap matrix API

API_URL="http://localhost:8000/api/v1/features/chipseq"

echo "=========================================="
echo "Batch Heatmap Matrix API - Curl Tests"
echo "=========================================="

# Test 1: Basic batch query (3 genes)
echo ""
echo "Test 1: Basic batch query (3 genes)"
echo "----"
curl -X POST "${API_URL}/genes/batch-heatmap-matrix" \
  -H "Content-Type: application/json" \
  -d '{
    "gene_ids": [17276, 17277, 17278],
    "marks": ["H3K27me3", "H3K4me3", "H3K27ac"],
    "cell_types": ["K562", "HepG2", "GM12878"],
    "metric": "median_fold_enrichment",
    "flanking": 10000,
    "include_details": false
  }' | jq '.' | head -100

# Test 2: Single gene with details
echo ""
echo ""
echo "Test 2: Single gene with peak_count metric and details"
echo "----"
curl -X POST "${API_URL}/genes/batch-heatmap-matrix" \
  -H "Content-Type: application/json" \
  -d '{
    "gene_ids": [17276],
    "marks": ["H3K27me3", "H3K4me3"],
    "cell_types": ["K562", "HepG2"],
    "metric": "peak_count",
    "flanking": 5000,
    "include_details": true
  }' | jq '.'

# Test 3: Total coverage metric (5 genes)
echo ""
echo ""
echo "Test 3: 5 genes with total_coverage_bp metric"
echo "----"
curl -X POST "${API_URL}/genes/batch-heatmap-matrix" \
  -H "Content-Type: application/json" \
  -d '{
    "gene_ids": [17276, 17277, 17278, 17279, 17280],
    "marks": ["H3K27me3", "H3K4me3"],
    "cell_types": ["K562", "HepG2", "GM12878"],
    "metric": "total_coverage_bp",
    "flanking": 10000
  }' | jq '.total_genes, .successful_genes, .query_time_ms'

# Test 4: Average signal metric
echo ""
echo ""
echo "Test 4: Average signal metric"
echo "----"
curl -X POST "${API_URL}/genes/batch-heatmap-matrix" \
  -H "Content-Type: application/json" \
  -d '{
    "gene_ids": [17276, 17277],
    "marks": ["H3K27ac", "H3K4me1"],
    "cell_types": ["K562"],
    "metric": "avg_signal",
    "flanking": 10000
  }' | jq '.genes[0].matrix'

# Test 5: Error handling - empty gene_ids
echo ""
echo ""
echo "Test 5: Error handling - empty gene_ids (should fail)"
echo "----"
curl -X POST "${API_URL}/genes/batch-heatmap-matrix" \
  -H "Content-Type: application/json" \
  -d '{
    "gene_ids": [],
    "marks": ["H3K27me3"],
    "cell_types": ["K562"]
  }' | jq '.'

# Test 6: Non-existent genes
echo ""
echo ""
echo "Test 6: Non-existent genes (should return empty results)"
echo "----"
curl -X POST "${API_URL}/genes/batch-heatmap-matrix" \
  -H "Content-Type: application/json" \
  -d '{
    "gene_ids": [999999, 999998],
    "marks": ["H3K27me3"],
    "cell_types": ["K562"]
  }' | jq '.total_genes, .successful_genes, .failed_genes'

echo ""
echo "=========================================="
echo "Tests completed"
echo "=========================================="
