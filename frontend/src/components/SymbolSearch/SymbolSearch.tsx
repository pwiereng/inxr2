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
import { useTheme } from '@mui/material/styles'
import SearchIcon from '@mui/icons-material/Search'
import FunctionsIcon from '@mui/icons-material/Functions'
import ClassIcon from '@mui/icons-material/Class'
import CodeIcon from '@mui/icons-material/Code'

import { searchSymbols, type Symbol } from '@/lib/api'

interface SymbolSearchProps {
  repositoryId?: number
  branch?: string
  commit?: string
  onSymbolSelect?: (symbol: Symbol) => void
  placeholder?: string
  value?: string
  onValueChange?: (value: string) => void
}

// Get icon for symbol kind
function getSymbolIcon(
  kind: string,
  palette: { class: string; function: string; interface: string; variable: string }
) {
  switch (kind.toLowerCase()) {
    case 'class':
      return <ClassIcon fontSize="small" sx={{ color: palette.class }} />
    case 'function':
    case 'method':
    case 'delegate':
      return <FunctionsIcon fontSize="small" sx={{ color: palette.function }} />
    case 'interface':
    case 'type':
      return <CodeIcon fontSize="small" sx={{ color: palette.interface }} />
    case 'event':
    case 'indexer':
    default:
      return <CodeIcon fontSize="small" sx={{ color: palette.variable }} />
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
    case 'delegate':
      return 'primary'
    case 'method':
      return 'info'
    case 'interface':
    case 'type':
      return 'secondary'
    case 'event':
      return 'warning'
    default:
      return 'default'
  }
}

export function SymbolSearch({
  repositoryId,
  branch,
  commit,
  onSymbolSelect,
  placeholder = 'Search symbols...',
  value,
  onValueChange,
}: SymbolSearchProps): React.ReactElement {
  const [internalValue, setInternalValue] = useState('')
  const [options, setOptions] = useState<Symbol[]>([])
  const [loading, setLoading] = useState(false)
  const theme = useTheme()

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
        const searchParams: Parameters<typeof searchSymbols>[0] = {
          q: query,
          limit: 20,
        }

        if (repositoryId !== undefined) {
          searchParams.repository_id = repositoryId
          if (branch) {
            searchParams.branch = branch
          }
          if (commit) {
            searchParams.commit = commit
          }
        }

        const result = await searchSymbols(searchParams)
        setOptions(result.items)
      } catch (error) {
        console.error('Search failed:', error)
        setOptions([])
      } finally {
        setLoading(false)
      }
    },
    [repositoryId, branch, commit]
  )

  // Debounce effect
  useEffect(() => {
    const timer = setTimeout(() => {
      searchDebounced(inputValue)
    }, 300)

    return () => clearTimeout(timer)
  }, [inputValue, searchDebounced])

  const iconPalette = theme.palette.symbolIcon

  return (
    <Autocomplete
      freeSolo
      options={options}
      loading={loading}
      inputValue={inputValue}
      onInputChange={(_, value, reason) => {
        // Only update for user input, not for option selection (which uses 'reset')
        // This prevents the race condition where selecting a symbol would trigger
        // setSearchQuery via onValueChange, which would call setSearchParams and
        // overwrite the navigate() call from onSymbolSelect
        if (reason === 'input') {
          setInputValue(value)
        }
      }}
      onChange={(_, value) => {
        if (value && typeof value !== 'string') {
          onSymbolSelect?.(value)
          // Clear the search box after selection - the search box is just for input,
          // not for displaying current state
          setInputValue('')
          setOptions([])
        }
      }}
      getOptionLabel={(option) => (typeof option === 'string' ? option : option.name)}
      isOptionEqualToValue={(option, value) => option.id === value.id}
      filterOptions={(x) => x} // Disable client-side filtering
      renderOption={({ key, ...props }, option) => (
        <Box
          key={option.id ?? key}
          component="li"
          {...props}
          sx={{ display: 'flex', alignItems: 'center', gap: 1, py: 1 }}
        >
          {getSymbolIcon(option.kind, iconPalette)}
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
