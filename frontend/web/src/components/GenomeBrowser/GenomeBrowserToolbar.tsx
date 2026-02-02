/**
 * GenomeBrowser Toolbar Component
 * Provides species selection and gene search with autocomplete functionality
 *
 * Features:
 * - Gene name autocomplete using /api/v1/igv/autocomplete API
 * - Debounced search (300ms) to avoid excessive API calls
 * - Displays gene name + chromosome position in dropdown
 * - Navigates IGV to selected gene position on selection
 */
import { memo, useState, useEffect, useMemo, useRef, useCallback } from 'react'
import { Space, Select, Button, AutoComplete, Spin } from 'antd'
import { SearchOutlined } from '@ant-design/icons'
import { useTranslation } from 'react-i18next'
import { genomeApi, type GeneAutocompleteItem } from '@/api/genome'
import debounce from 'lodash/debounce'

interface GenomeBrowserToolbarProps {
  speciesId: number
  onSpeciesChange: (speciesId: number) => void
  onSearch: (locus: string) => void
  disabled?: boolean
}

interface AutoCompleteOption {
  value: string
  label: React.ReactNode
  gene: GeneAutocompleteItem
}

const GenomeBrowserToolbar = memo(({
  speciesId,
  onSpeciesChange,
  onSearch,
  disabled = false
}: GenomeBrowserToolbarProps) => {
  const { t } = useTranslation('genomeBrowser')
  const { t: tCommon } = useTranslation('common')

  const [searchValue, setSearchValue] = useState('')
  const [options, setOptions] = useState<AutoCompleteOption[]>([])
  const [isSearching, setIsSearching] = useState(false)

  // Store the selected gene for display
  const selectedGeneRef = useRef<GeneAutocompleteItem | null>(null)

  // Species options with translations
  const speciesOptions = [
    { label: tCommon('species.human'), value: 1 },
    { label: tCommon('species.chimpanzee'), value: 2 },
    { label: tCommon('species.macaque'), value: 3 },
    { label: tCommon('species.marmoset'), value: 4 },
  ]

  // Fetch autocomplete results from API
  const fetchAutocomplete = useCallback(async (query: string) => {
    if (!query || query.length < 2) {
      setOptions([])
      return
    }

    setIsSearching(true)
    try {
      const response = await genomeApi.autocompleteGene(query, speciesId, 10)
      const results = response.data?.data || []

      if (results.length > 0) {
        const newOptions: AutoCompleteOption[] = results.map((gene) => ({
          value: `${gene.chromosome}:${gene.start}-${gene.end}`,
          label: (
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontWeight: 500 }}>{gene.gene_name}</span>
              <span style={{ color: '#888', fontSize: 12, marginLeft: 12 }}>
                {gene.chromosome}:{gene.start.toLocaleString()}-{gene.end.toLocaleString()}
              </span>
            </div>
          ),
          gene,
        }))
        setOptions(newOptions)
      } else {
        setOptions([])
      }
    } catch (error) {
      console.error('Autocomplete search failed:', error)
      setOptions([])
    } finally {
      setIsSearching(false)
    }
  }, [speciesId])

  // Debounced search function (300ms delay)
  const debouncedFetch = useMemo(
    () => debounce(fetchAutocomplete, 300),
    [fetchAutocomplete]
  )

  // Cleanup debounced function on unmount
  useEffect(() => {
    return () => {
      debouncedFetch.cancel()
    }
  }, [debouncedFetch])

  // Clear options when species changes
  useEffect(() => {
    setOptions([])
    setSearchValue('')
    selectedGeneRef.current = null
  }, [speciesId])

  const handleSearchChange = (value: string) => {
    setSearchValue(value)
    selectedGeneRef.current = null
    debouncedFetch(value)
  }

  const handleSelect = (value: string, option: AutoCompleteOption) => {
    // Store the selected gene and display its name
    selectedGeneRef.current = option.gene
    setSearchValue(option.gene.gene_name)
    // Navigate to the selected locus
    onSearch(value)
  }

  const handleSearchClick = () => {
    if (searchValue.trim()) {
      // Check if it looks like a locus (chr:start-end) or a gene name
      const locusPattern = /^(chr)?[\dXYxy]+:\d+-\d+$/
      if (locusPattern.test(searchValue.trim())) {
        // Direct locus input, navigate directly
        onSearch(searchValue.trim())
      } else if (options.length > 0) {
        // Use first result from autocomplete
        const firstOption = options[0]
        selectedGeneRef.current = firstOption.gene
        setSearchValue(firstOption.gene.gene_name)
        onSearch(firstOption.value)
      } else if (selectedGeneRef.current) {
        // Use previously selected gene
        const gene = selectedGeneRef.current
        onSearch(`${gene.chromosome}:${gene.start}-${gene.end}`)
      } else {
        // Just try to search with the value as-is (IGV will handle it)
        onSearch(searchValue.trim())
      }
    }
  }

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleSearchClick()
    }
  }

  return (
    <Space wrap size="middle" style={{ marginBottom: 16 }}>
      <Space>
        <span style={{ fontWeight: 500 }}>{t('species')}:</span>
        <Select
          value={speciesId}
          onChange={onSpeciesChange}
          options={speciesOptions}
          style={{ width: 140 }}
          disabled={disabled}
        />
      </Space>

      <Space.Compact>
        <AutoComplete
          data-testid="genome-locus-autocomplete"
          value={searchValue}
          onChange={handleSearchChange}
          onSelect={handleSelect}
          options={options}
          style={{ width: 320 }}
          placeholder={t('autocompleteSearchPlaceholder') || 'Search gene (e.g., hla-, brca1)'}
          disabled={disabled}
          onKeyDown={handleKeyPress}
          notFoundContent={
            isSearching ? (
              <div style={{ textAlign: 'center', padding: '8px 0' }}>
                <Spin size="small" />
                <span style={{ marginLeft: 8, color: '#999' }}>{t('searching') || 'Searching...'}</span>
              </div>
            ) : searchValue.length >= 2 ? (
              <span style={{ color: '#999', padding: '8px 12px', display: 'block' }}>
                {t('noResults') || 'No matching genes found'}
              </span>
            ) : searchValue.length > 0 ? (
              <span style={{ color: '#999', padding: '8px 12px', display: 'block' }}>
                {t('typeMoreChars') || 'Type at least 2 characters'}
              </span>
            ) : null
          }
          popupMatchSelectWidth={400}
        />
        <Button
          type="primary"
          icon={<SearchOutlined />}
          onClick={handleSearchClick}
          disabled={disabled || !searchValue.trim()}
          loading={isSearching}
        >
          {t('search')}
        </Button>
      </Space.Compact>
    </Space>
  )
})

GenomeBrowserToolbar.displayName = 'GenomeBrowserToolbar'

export default GenomeBrowserToolbar
