/**
 * GenomeBrowser Toolbar Component
 * Provides species selection and gene search functionality
 */
import { memo, useState, useEffect, useMemo, useRef } from 'react'
import { Space, Select, Button, AutoComplete, Spin } from 'antd'
import { SearchOutlined } from '@ant-design/icons'
import { useTranslation } from 'react-i18next'
import { useQuery } from '@tanstack/react-query'
import { genomeApi, type GenomeSearchResult } from '@/api/genome'
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
  gene: GenomeSearchResult
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
  const [searchQuery, setSearchQuery] = useState('')
  const [options, setOptions] = useState<AutoCompleteOption[]>([])

  // Species options with translations
  const speciesOptions = [
    { label: tCommon('species.human'), value: 1 },
    { label: tCommon('species.chimpanzee'), value: 2 },
    { label: tCommon('species.macaque'), value: 3 },
    { label: tCommon('species.marmoset'), value: 4 },
  ]

  // Search query for gene autocomplete
  const { data: searchResults, isLoading: isSearching } = useQuery({
    queryKey: ['genome-search', speciesId, searchQuery],
    queryFn: async () => {
      if (!searchQuery || searchQuery.length < 2) return []
      const res = await genomeApi.searchGene(speciesId, searchQuery)
      return res.data
    },
    enabled: searchQuery.length >= 2,
    staleTime: 30000,
  })

  // Update autocomplete options when search results change
  useEffect(() => {
    if (searchResults && searchResults.length > 0) {
      const newOptions: AutoCompleteOption[] = searchResults.map((gene) => ({
        value: `${gene.chromosome}:${gene.gene_start}-${gene.gene_end}`,
        label: (
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span style={{ fontWeight: 500 }}>{gene.gene_name}</span>
            <span style={{ color: '#888', fontSize: 12 }}>
              {gene.chromosome}:{gene.gene_start.toLocaleString()}-{gene.gene_end.toLocaleString()}
            </span>
          </div>
        ),
        gene,
      }))
      setOptions(newOptions)
    } else {
      setOptions([])
    }
  }, [searchResults])

  // Debounced search query update using useMemo + useRef pattern
  const debouncedSetSearchQueryRef = useRef(
    debounce((value: string) => {
      setSearchQuery(value)
    }, 300)
  )

  // Memoize the debounced function to avoid recreating on every render
  const debouncedSetSearchQuery = useMemo(
    () => debouncedSetSearchQueryRef.current,
    []
  )

  const handleSearchChange = (value: string) => {
    setSearchValue(value)
    debouncedSetSearchQuery(value)
  }

  const handleSelect = (value: string, option: AutoCompleteOption) => {
    setSearchValue(option.gene.gene_name)
    onSearch(value)
  }

  const handleSearchClick = () => {
    if (searchValue.trim()) {
      // Check if it looks like a locus (chr:start-end) or a gene name
      const locusPattern = /^(chr)?[\dXYxy]+:\d+-\d+$/
      if (locusPattern.test(searchValue.trim())) {
        onSearch(searchValue.trim())
      } else if (options.length > 0) {
        // Use first result if available
        const firstOption = options[0]
        onSearch(firstOption.value)
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
          value={searchValue}
          onChange={handleSearchChange}
          onSelect={handleSelect}
          options={options}
          style={{ width: 300 }}
          placeholder={t('searchPlaceholder')}
          disabled={disabled}
          onKeyDown={handleKeyPress}
          notFoundContent={
            isSearching ? (
              <Spin size="small" />
            ) : searchQuery.length >= 2 ? (
              <span style={{ color: '#999' }}>{t('noResults')}</span>
            ) : null
          }
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
