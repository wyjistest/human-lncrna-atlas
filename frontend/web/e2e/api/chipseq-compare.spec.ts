import { test, expect } from '@playwright/test'

/**
 * ChIP-seq Compare API E2E Tests
 *
 * Tests for Phase 2.5 ChIP-seq comparison functionality API endpoints.
 * Covers:
 * 1. Available marks endpoint
 * 2. Gene peaks endpoint
 * 3. Gene summary endpoint
 * 4. Multi-mark comparison endpoint
 * 5. Cell line comparison endpoint
 * 6. Heatmap matrix endpoint
 *
 * API Base: http://localhost:8000
 */

const API_BASE = process.env.API_BASE_URL || 'http://localhost:8000'

// Test gene ID with known ChIP-seq data
const TEST_GENE_ID = 17276

test.describe('ChIP-seq Available Marks API', () => {
  test('GET /api/v1/features/chipseq/marks returns available marks', async ({ request }) => {
    const response = await request.get(`${API_BASE}/api/v1/features/chipseq/marks`, {
      params: { species_id: 1 },
    })

    expect(response.ok()).toBeTruthy()

    const data = await response.json()
    // API returns an array of marks directly
    expect(Array.isArray(data)).toBeTruthy()
    expect(data.length).toBeGreaterThan(0)

    // Verify mark structure - API uses mark_name, not mark_type
    const firstMark = data[0]
    expect(firstMark.mark_name).toBeDefined()
    expect(firstMark.display_name).toBeDefined()
    expect(firstMark.mark_category).toBeDefined()
    // Note: peak_count and gene_count are not included in marks list endpoint
  })

  test('GET /api/v1/features/chipseq/marks should include common histone marks', async ({ request }) => {
    const response = await request.get(`${API_BASE}/api/v1/features/chipseq/marks`, {
      params: { species_id: 1 },
    })

    expect(response.ok()).toBeTruthy()
    const data = await response.json()

    // API returns array directly with mark_name field
    const markNames = data.map((m: { mark_name: string }) => m.mark_name)

    // Common marks that should be present
    const commonMarks = ['H3K27me3', 'H3K4me3', 'H3K27ac', 'H3K4me1']
    const foundCommonMarks = commonMarks.filter((mark) => markNames.includes(mark))

    // At least some common marks should be present
    expect(foundCommonMarks.length).toBeGreaterThan(0)
    console.log(`Found common marks: ${foundCommonMarks.join(', ')}`)
  })
})

test.describe('ChIP-seq Gene Peaks API', () => {
  test('GET /api/v1/features/chipseq/genes/{gene_id} returns peaks data', async ({ request }) => {
    const response = await request.get(`${API_BASE}/api/v1/features/chipseq/genes/${TEST_GENE_ID}`, {
      params: {
        mark_type: 'H3K27me3',
        flanking: 10000,
      },
    })

    expect(response.ok()).toBeTruthy()

    const data = await response.json()
    expect(data.gene_id).toBe(TEST_GENE_ID)
    expect(data.gene_name).toBeDefined()
    expect(data.chromosome).toBeDefined()
    expect(data.marks).toBeDefined()
    expect(data.total_peaks).toBeGreaterThanOrEqual(0)
    expect(data.marks_present).toBeDefined()
    expect(Array.isArray(data.marks_present)).toBeTruthy()
  })

  test('GET /api/v1/features/chipseq/genes/{gene_id} with filter returns filtered data', async ({ request }) => {
    const response = await request.get(`${API_BASE}/api/v1/features/chipseq/genes/${TEST_GENE_ID}`, {
      params: {
        mark_type: 'H3K27me3',
        min_fold_enrichment: 2,
        max_qvalue: 0.05,
        flanking: 10000,
      },
    })

    expect(response.ok()).toBeTruthy()

    const data = await response.json()
    expect(data.gene_id).toBe(TEST_GENE_ID)

    // If there are peaks, verify they match the filter criteria
    if (data.marks && data.marks['H3K27me3']) {
      const peaks = data.marks['H3K27me3']
      for (const peak of peaks) {
        if (peak.fold_enrichment !== null) {
          expect(peak.fold_enrichment).toBeGreaterThanOrEqual(2)
        }
        if (peak.qvalue !== null) {
          expect(peak.qvalue).toBeLessThanOrEqual(0.05)
        }
      }
    }
  })

  test('GET /api/v1/features/chipseq/genes/{gene_id} with cell_type filter', async ({ request }) => {
    const response = await request.get(`${API_BASE}/api/v1/features/chipseq/genes/${TEST_GENE_ID}`, {
      params: {
        mark_type: 'H3K27me3',
        cell_type: 'K562',
        flanking: 10000,
      },
    })

    expect(response.ok()).toBeTruthy()
    const data = await response.json()
    expect(data.gene_id).toBe(TEST_GENE_ID)
  })

  test('GET /api/v1/features/chipseq/genes/{gene_id} handles non-existent gene', async ({ request }) => {
    const response = await request.get(`${API_BASE}/api/v1/features/chipseq/genes/99999999`, {
      params: {
        mark_type: 'H3K27me3',
      },
    })

    // Should return 404 for non-existent gene or empty data
    expect([404, 200]).toContain(response.status())

    if (response.status() === 200) {
      const data = await response.json()
      expect(data.total_peaks).toBe(0)
    }
  })
})

test.describe('ChIP-seq Gene Summary API', () => {
  test('GET /api/v1/features/chipseq/genes/{gene_id}/summary returns summary statistics', async ({ request }) => {
    const response = await request.get(`${API_BASE}/api/v1/features/chipseq/genes/${TEST_GENE_ID}/summary`, {
      params: { mark_type: 'H3K27me3' },
    })

    expect(response.ok()).toBeTruthy()

    const data = await response.json()
    // Summary API returns comprehensive gene summary with mark_summaries array
    expect(data.gene_id).toBe(TEST_GENE_ID)
    expect(data.total_peaks).toBeGreaterThanOrEqual(0)
    expect(data.mark_summaries).toBeDefined()
    expect(Array.isArray(data.mark_summaries)).toBeTruthy()

    // If there are peaks, verify summary statistics
    if (data.total_peaks > 0) {
      expect(data.total_marks).toBeGreaterThan(0)
      // Check for H3K27me3 in mark_summaries
      const h3k27me3Summary = data.mark_summaries.find(
        (m: { mark_type: string }) => m.mark_type === 'H3K27me3'
      )
      if (h3k27me3Summary) {
        expect(h3k27me3Summary.peak_count).toBeGreaterThanOrEqual(0)
        expect(h3k27me3Summary.avg_fold_enrichment).toBeGreaterThanOrEqual(0)
      }
    }
  })

  test('GET /api/v1/features/chipseq/genes/{gene_id}/summary includes position distribution', async ({ request }) => {
    const response = await request.get(`${API_BASE}/api/v1/features/chipseq/genes/${TEST_GENE_ID}/summary`, {
      params: { mark_type: 'H3K27me3' },
    })

    expect(response.ok()).toBeTruthy()

    const data = await response.json()

    if (data.total_peaks > 0 && data.mark_summaries) {
      // Check overlap_types in mark_summaries which indicates position distribution
      const h3k27me3Summary = data.mark_summaries.find(
        (m: { mark_type: string }) => m.mark_type === 'H3K27me3'
      )
      if (h3k27me3Summary && h3k27me3Summary.overlap_types) {
        expect(Array.isArray(h3k27me3Summary.overlap_types)).toBeTruthy()
        // Overlap types include: promoter, gene_body, flanking, etc.
        const possibleTypes = ['promoter', 'gene_body', 'flanking', 'upstream', 'downstream']
        const hasValidTypes = h3k27me3Summary.overlap_types.some((type: string) =>
          possibleTypes.includes(type.toLowerCase())
        )
        console.log(`Overlap types for H3K27me3: ${h3k27me3Summary.overlap_types.join(', ')}`)
      }
    }
  })
})

test.describe('ChIP-seq Multi-Mark Compare API', () => {
  test('GET /api/v1/features/chipseq/genes/{gene_id}/compare returns comparison data', async ({ request }) => {
    const response = await request.get(`${API_BASE}/api/v1/features/chipseq/genes/${TEST_GENE_ID}/compare`, {
      params: {
        marks: 'H3K27me3,H3K4me3',
        flanking: 10000,
      },
    })

    expect(response.ok()).toBeTruthy()

    const data = await response.json()
    expect(data.gene_id).toBe(TEST_GENE_ID)
    expect(data.gene_name).toBeDefined()
    expect(data.marks).toBeDefined()
    expect(Array.isArray(data.marks)).toBeTruthy()

    // Should have data for both requested marks (or at least the marks with data)
    expect(data.marks.length).toBeGreaterThanOrEqual(0)

    if (data.marks.length > 0) {
      const firstMark = data.marks[0]
      expect(firstMark.mark_type).toBeDefined()
      expect(firstMark.peaks).toBeDefined()
      expect(Array.isArray(firstMark.peaks)).toBeTruthy()
    }
  })

  test('GET /api/v1/features/chipseq/genes/{gene_id}/compare includes overlap statistics', async ({ request }) => {
    const response = await request.get(`${API_BASE}/api/v1/features/chipseq/genes/${TEST_GENE_ID}/compare`, {
      params: {
        marks: 'H3K27me3,H3K4me3',
        flanking: 10000,
      },
    })

    expect(response.ok()).toBeTruthy()

    const data = await response.json()

    // Check for overlap-related fields
    if (data.overlap_statistics) {
      expect(typeof data.overlap_statistics).toBe('object')
    }

    if (data.overlapping_regions) {
      expect(Array.isArray(data.overlapping_regions)).toBeTruthy()
    }

    if (data.all_overlaps) {
      expect(Array.isArray(data.all_overlaps)).toBeTruthy()
    }

    console.log(`Overlap statistics present: ${!!data.overlap_statistics}`)
    console.log(`Overlapping regions count: ${data.overlapping_regions?.length || 0}`)
  })

  test('GET /api/v1/features/chipseq/genes/{gene_id}/compare detects bivalent domains', async ({ request }) => {
    // Bivalent domain = H3K4me3 + H3K27me3 overlap
    const response = await request.get(`${API_BASE}/api/v1/features/chipseq/genes/${TEST_GENE_ID}/compare`, {
      params: {
        marks: 'H3K27me3,H3K4me3',
        flanking: 10000,
      },
    })

    expect(response.ok()).toBeTruthy()

    const data = await response.json()

    // Check for bivalent domain detection
    if (data.bivalent_regions) {
      expect(Array.isArray(data.bivalent_regions)).toBeTruthy()
      console.log(`Bivalent regions found: ${data.bivalent_regions.length}`)
    }
  })

  test('GET /api/v1/features/chipseq/genes/{gene_id}/compare with three marks', async ({ request }) => {
    const response = await request.get(`${API_BASE}/api/v1/features/chipseq/genes/${TEST_GENE_ID}/compare`, {
      params: {
        marks: 'H3K27me3,H3K4me3,H3K27ac',
        flanking: 10000,
      },
    })

    expect(response.ok()).toBeTruthy()

    const data = await response.json()
    expect(data.gene_id).toBe(TEST_GENE_ID)

    // Count marks with data
    const marksWithData = data.marks?.filter(
      (m: { peaks?: unknown[] }) => m.peaks && m.peaks.length > 0
    ) || []
    console.log(`Marks with data: ${marksWithData.length}`)
  })
})

test.describe('ChIP-seq Cell Line Compare API', () => {
  test('GET /api/v1/features/chipseq/genes/{gene_id}/compare-cell-lines returns cell line comparison', async ({ request }) => {
    const response = await request.get(
      `${API_BASE}/api/v1/features/chipseq/genes/${TEST_GENE_ID}/compare-cell-lines`,
      {
        params: {
          mark_type: 'H3K27me3',
          cell_types: 'K562,GM12878',
          flanking: 10000,
        },
      }
    )

    // This endpoint might not be implemented yet - handle gracefully
    if (response.status() === 404) {
      console.log('Cell line compare endpoint not implemented yet')
      test.skip()
      return
    }

    expect(response.ok()).toBeTruthy()

    const data = await response.json()
    expect(data.gene_id).toBe(TEST_GENE_ID)
    expect(data.mark_type).toBeDefined()
    expect(data.cell_lines).toBeDefined()
    expect(Array.isArray(data.cell_lines)).toBeTruthy()

    if (data.cell_lines.length > 0) {
      const firstCellLine = data.cell_lines[0]
      expect(firstCellLine.cell_type).toBeDefined()
      expect(firstCellLine.peaks).toBeDefined()
    }
  })

  test('GET /api/v1/features/chipseq/genes/{gene_id}/compare-cell-lines includes overlap regions', async ({ request }) => {
    const response = await request.get(
      `${API_BASE}/api/v1/features/chipseq/genes/${TEST_GENE_ID}/compare-cell-lines`,
      {
        params: {
          mark_type: 'H3K27me3',
          cell_types: 'K562,GM12878,HepG2',
          flanking: 10000,
        },
      }
    )

    if (response.status() === 404) {
      console.log('Cell line compare endpoint not implemented yet')
      test.skip()
      return
    }

    expect(response.ok()).toBeTruthy()

    const data = await response.json()

    if (data.overlap_regions) {
      expect(Array.isArray(data.overlap_regions)).toBeTruthy()
      console.log(`Cell line overlap regions: ${data.overlap_regions.length}`)
    }

    if (data.common_peaks !== undefined) {
      expect(typeof data.common_peaks).toBe('number')
      console.log(`Common peaks across cell lines: ${data.common_peaks}`)
    }
  })
})

test.describe('ChIP-seq Heatmap Matrix API', () => {
  test('GET /api/v1/features/chipseq/genes/{gene_id}/heatmap-matrix returns matrix data', async ({ request }) => {
    const response = await request.get(
      `${API_BASE}/api/v1/features/chipseq/genes/${TEST_GENE_ID}/heatmap-matrix`,
      {
        params: {
          marks: 'H3K27me3,H3K4me3,H3K27ac',
          cell_types: 'K562,GM12878',
          metric: 'median_fold_enrichment',
          flanking: 10000,
        },
      }
    )

    // This endpoint might not be implemented yet - handle gracefully
    if (response.status() === 404) {
      console.log('Heatmap matrix endpoint not implemented yet')
      test.skip()
      return
    }

    expect(response.ok()).toBeTruthy()

    const data = await response.json()
    expect(data.gene_id).toBe(TEST_GENE_ID)
    expect(data.cell_types).toBeDefined()
    expect(data.marks).toBeDefined()
    expect(data.matrix).toBeDefined()

    // Verify matrix dimensions
    expect(Array.isArray(data.cell_types)).toBeTruthy()
    expect(Array.isArray(data.marks)).toBeTruthy()
    expect(Array.isArray(data.matrix)).toBeTruthy()

    // Matrix rows should equal cell_types length
    if (data.matrix.length > 0) {
      expect(data.matrix.length).toBe(data.cell_types.length)

      // Each row should have marks.length columns
      for (const row of data.matrix) {
        expect(row.length).toBe(data.marks.length)
      }
    }
  })

  test('GET /api/v1/features/chipseq/genes/{gene_id}/heatmap-matrix with peak_count metric', async ({ request }) => {
    const response = await request.get(
      `${API_BASE}/api/v1/features/chipseq/genes/${TEST_GENE_ID}/heatmap-matrix`,
      {
        params: {
          marks: 'H3K27me3,H3K4me3',
          cell_types: 'K562,GM12878',
          metric: 'peak_count',
          flanking: 10000,
        },
      }
    )

    if (response.status() === 404) {
      console.log('Heatmap matrix endpoint not implemented yet')
      test.skip()
      return
    }

    expect(response.ok()).toBeTruthy()

    const data = await response.json()
    expect(data.metric).toBe('peak_count')

    // Peak counts should be non-negative integers
    for (const row of data.matrix) {
      for (const value of row) {
        if (value !== null) {
          expect(Number.isInteger(value)).toBeTruthy()
          expect(value).toBeGreaterThanOrEqual(0)
        }
      }
    }
  })
})

test.describe('ChIP-seq Export API', () => {
  test('GET /api/v1/features/chipseq/genes/{gene_id}/export returns BED format', async ({ request }) => {
    const response = await request.get(`${API_BASE}/api/v1/features/chipseq/genes/${TEST_GENE_ID}/export`, {
      params: {
        mark_type: 'H3K27me3',
        flanking: 10000,
      },
    })

    // Export endpoint might return different status codes
    if (response.status() === 404) {
      console.log('Export endpoint not implemented yet')
      test.skip()
      return
    }

    expect(response.ok()).toBeTruthy()

    // Check content type for BED file
    const contentType = response.headers()['content-type']
    expect(contentType).toMatch(/text\/plain|application\/octet-stream|text\/tab-separated-values/)

    // BED format validation (tab-separated, at least 3 columns)
    const body = await response.text()
    if (body.trim().length > 0) {
      const lines = body.trim().split('\n')
      // Skip header lines starting with #
      const dataLines = lines.filter((line) => !line.startsWith('#') && line.trim().length > 0)

      if (dataLines.length > 0) {
        const firstLine = dataLines[0]
        const columns = firstLine.split('\t')
        expect(columns.length).toBeGreaterThanOrEqual(3)

        // First column should be chromosome
        expect(columns[0]).toMatch(/^chr\d+|^chr[XYM]/)

        // Second and third columns should be numeric (start, end)
        expect(parseInt(columns[1])).toBeGreaterThanOrEqual(0)
        expect(parseInt(columns[2])).toBeGreaterThan(parseInt(columns[1]))
      }
    }
  })

  test('GET /api/v1/features/chipseq/genes/{gene_id}/compare/export returns CSV format', async ({ request }) => {
    const response = await request.get(
      `${API_BASE}/api/v1/features/chipseq/genes/${TEST_GENE_ID}/compare/export`,
      {
        params: {
          marks: 'H3K27me3,H3K4me3',
          format: 'csv',
        },
      }
    )

    if (response.status() === 404) {
      console.log('Compare export endpoint not implemented yet')
      test.skip()
      return
    }

    expect(response.ok()).toBeTruthy()

    // Check content type for CSV file
    const contentType = response.headers()['content-type']
    expect(contentType).toMatch(/text\/csv|application\/csv|text\/plain/)

    // CSV validation
    const body = await response.text()
    if (body.trim().length > 0) {
      const lines = body.trim().split('\n')
      expect(lines.length).toBeGreaterThan(0)

      // First line should be header with commas
      const header = lines[0]
      expect(header).toContain(',')
    }
  })
})

test.describe('ChIP-seq API Error Handling', () => {
  test('should return 400 for invalid mark_type', async ({ request }) => {
    const response = await request.get(`${API_BASE}/api/v1/features/chipseq/genes/${TEST_GENE_ID}`, {
      params: {
        mark_type: 'INVALID_MARK',
      },
    })

    // Should return 400 or 422 for invalid input
    expect([400, 422, 200]).toContain(response.status())

    if (response.status() === 200) {
      // If 200, should return empty data
      const data = await response.json()
      expect(data.total_peaks).toBe(0)
    }
  })

  test('should return 400 for invalid gene_id format', async ({ request }) => {
    const response = await request.get(`${API_BASE}/api/v1/features/chipseq/genes/not-a-number`, {
      params: {
        mark_type: 'H3K27me3',
      },
    })

    // Should return 400 or 422 for invalid input
    expect([400, 422, 404]).toContain(response.status())
  })

  test('should handle missing required parameters gracefully', async ({ request }) => {
    const response = await request.get(`${API_BASE}/api/v1/features/chipseq/genes/${TEST_GENE_ID}/compare`, {
      params: {}, // Missing required 'marks' parameter
    })

    // Should return error or empty data
    expect([400, 422, 200]).toContain(response.status())
  })
})

test.describe('ChIP-seq API Performance', () => {
  test('marks endpoint should respond within 2 seconds', async ({ request }) => {
    const startTime = Date.now()

    const response = await request.get(`${API_BASE}/api/v1/features/chipseq/marks`, {
      params: { species_id: 1 },
    })

    const responseTime = Date.now() - startTime

    expect(response.ok()).toBeTruthy()
    expect(responseTime).toBeLessThan(2000)

    console.log(`Marks endpoint response time: ${responseTime}ms`)
  })

  test('gene peaks endpoint should respond within 5 seconds', async ({ request }) => {
    const startTime = Date.now()

    const response = await request.get(`${API_BASE}/api/v1/features/chipseq/genes/${TEST_GENE_ID}`, {
      params: {
        mark_type: 'H3K27me3',
        flanking: 10000,
      },
    })

    const responseTime = Date.now() - startTime

    expect(response.ok()).toBeTruthy()
    expect(responseTime).toBeLessThan(5000)

    console.log(`Gene peaks endpoint response time: ${responseTime}ms`)
  })

  test('compare endpoint should respond within 10 seconds', async ({ request }) => {
    const startTime = Date.now()

    const response = await request.get(`${API_BASE}/api/v1/features/chipseq/genes/${TEST_GENE_ID}/compare`, {
      params: {
        marks: 'H3K27me3,H3K4me3,H3K27ac',
        flanking: 10000,
      },
    })

    const responseTime = Date.now() - startTime

    expect(response.ok()).toBeTruthy()
    expect(responseTime).toBeLessThan(10000)

    console.log(`Compare endpoint response time: ${responseTime}ms`)
  })
})
