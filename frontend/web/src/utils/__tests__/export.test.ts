import { describe, expect, it, vi } from 'vitest'

vi.mock('file-saver', () => ({
  saveAs: vi.fn(),
}))

import { saveAs } from 'file-saver'
import { parseContentDispositionFilename, saveBlobWithFilename } from '@/utils/export'

describe('parseContentDispositionFilename', () => {
  it('prefers filename* and decodes UTF-8 values', () => {
    expect(
      parseContentDispositionFilename(
        "attachment; filename=\"fallback.csv\"; filename*=UTF-8''analysis-%E4%B8%AD%E6%96%87.csv",
      ),
    ).toBe('analysis-中文.csv')
  })

  it('falls back to filename when filename* is absent', () => {
    expect(
      parseContentDispositionFilename('attachment; filename="analysis-export.csv"'),
    ).toBe('analysis-export.csv')
  })
})

describe('saveBlobWithFilename', () => {
  it('uses the parsed filename from headers when present', () => {
    const blob = new Blob(['demo'])

    const filename = saveBlobWithFilename(
      blob,
      {
        get: (name: string) =>
          name.toLowerCase() === 'content-disposition'
            ? "attachment; filename*=UTF-8''epigenetic-results.json"
            : null,
      },
      'fallback.json',
    )

    expect(filename).toBe('epigenetic-results.json')
    expect(saveAs).toHaveBeenCalledWith(blob, 'epigenetic-results.json')
  })
})
