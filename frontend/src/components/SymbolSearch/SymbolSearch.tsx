import { useState, useEffect, useCallback } from 'react'
import {
  Box,
  TextField,
  Autocomplete,
  Typography,
  Chip,
  CircularProgress,
  InputAdornment,
} from '@mui/material'
import SearchIcon from '@mui/icons-material/Search'
import FunctionsIcon from '@mui/icons-material/Functions'
import ClassIcon from '@mui/icons-material/Class'
import CodeIcon from '@mui/icons-material/Code'

import { searchSymbols, type Symbol } from '@/lib/api'

interface SymbolSearchProps {
  repositoryId?: number
  onSymbolSelect?: (symbol: Symbol) => void
  placeholder?: string
  value?: string
  onValueChange?: (value: string) => void
}

// Get icon for symbol kind
function getSymbolIcon(kind: string) {
  switch (kind.toLowerCase()) {
    case 'class':
      return <ClassIcon fontSize="small" sx={{ color: '#4ec9b0' }} />
    case 'function':
    case 'method':
      return <FunctionsIcon fontSize="small" sx={{ color: '#dcdcaa' }} />
    case 'interface':
    case 'type':
      return <CodeIcon fontSize="small" sx={{ color: '#4fc1ff' }} />
    default:
      return <CodeIcon fontSize="small" sx={{ color: '#9cdcfe' }} />
  }
}

// Get chip color for symbol kind
function getKindColor(
  kind: string
): 'primary' | 'secondary' | 'success' | 'warning' | 'info' | 'default' {
  switch (kind.toLowerCase()) {
    case 'class':
      return 'success'
    case 'function':
      return 'primary'
    case 'method':
      return 'info'
    case 'interface':
    case 'type':
      return 'secondary'
    default:
      return 'default'
  }
}

export function SymbolSearch({
  repositoryId,
  onSymbolSelect,
  placeholder = 'Search symbols...',
  value,
  onValueChange,
}: SymbolSearchProps) {
  const [internalValue, setInternalValue] = useState('')
  const [options, setOptions] = useState<Symbol[]>([])
  const [loading, setLoading] = useState(false)

  // Use external value if provided, otherwise use internal state
  const inputValue = value !== undefined ? value : internalValue
  const setInputValue = (newValue: string) => {
    if (onValueChange) {
      onValueChange(newValue)
    } else {
      setInternalValue(newValue)
    }
  }

  // Debounced search
  const searchDebounced = useCallback(
    async (query: string) => {
      if (!query || query.length < 2) {
        setOptions([])
        return
      }

      setLoading(true)
      try {
        const result = await searchSymbols({
          q: query,
          repository_id: repositoryId,
          limit: 20,
        })
        setOptions(result.items)
      } catch (error) {
        console.error('Search failed:', error)
        setOptions([])
      } finally {
        setLoading(false)
      }
    },
    [repositoryId]
  )

  // Debounce effect
  useEffect(() => {
    const timer = setTimeout(() => {
      searchDebounced(inputValue)
    }, 300)

    return () => clearTimeout(timer)
  }, [inputValue, searchDebounced])

  return (
    <Autocomplete
      freeSolo
      options={options}
      loading={loading}
      inputValue={inputValue}
      onInputChange={(_, value) => setInputValue(value)}
      onChange={(_, value) => {
        if (value && typeof value !== 'string') {
          onSymbolSelect?.(value)
        }
      }}
      getOptionLabel={(option) => (typeof option === 'string' ? option : option.name)}
      filterOptions={(x) => x} // Disable client-side filtering
      renderOption={(props, option) => (
        <Box
          component="li"
          {...props}
          sx={{ display: 'flex', alignItems: 'center', gap: 1, py: 1 }}
        >
          {getSymbolIcon(option.kind)}
          <Box sx={{ flex: 1, minWidth: 0 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Typography
                variant="body2"
                sx={{
                  fontFamily: 'monospace',
                  fontWeight: 500,
                }}
              >
                {option.name}
              </Typography>
              <Chip
                label={option.kind}
                size="small"
                color={getKindColor(option.kind)}
                sx={{ height: 20, fontSize: '0.7rem' }}
              />
            </Box>
            {option.file_path && (
              <Typography
                variant="caption"
                color="text.secondary"
                sx={{
                  fontFamily: 'monospace',
                  display: 'block',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  whiteSpace: 'nowrap',
                }}
              >
                {option.file_path}:{option.start_line}
              </Typography>
            )}
          </Box>
        </Box>
      )}
      renderInput={(params) => (
        <TextField
          {...params}
          placeholder={placeholder}
          size="small"
          InputProps={{
            ...params.InputProps,
            startAdornment: (
              <InputAdornment position="start">
                <SearchIcon sx={{ color: 'text.secondary' }} />
              </InputAdornment>
            ),
            endAdornment: (
              <>
                {loading ? <CircularProgress color="inherit" size={20} /> : null}
                {params.InputProps.endAdornment}
              </>
            ),
          }}
        />
      )}
      sx={{ width: '100%', maxWidth: 400 }}
    />
  )
}

export default SymbolSearch
