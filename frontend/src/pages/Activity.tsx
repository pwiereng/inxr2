import { useState, useEffect, useRef, useCallback } from 'react'
import {
  Box,
  Container,
  Typography,
  Paper,
  CircularProgress,
  Alert,
  Chip,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Switch,
  FormControlLabel,
  Tooltip,
  IconButton,
  Collapse,
} from '@mui/material'
import RefreshIcon from '@mui/icons-material/Refresh'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
import ExpandLessIcon from '@mui/icons-material/ExpandLess'
import { getActivityLog, getRepositories, type ActivityEntry } from '@/lib/api'

const AUTO_REFRESH_INTERVAL_MS = 5000

function formatTime(iso: string): string {
  const d = new Date(iso)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}:${pad(d.getUTCSeconds())}`
}

function SourceChip({ source }: { source: string }) {
  const isMcp = source === 'mcp'
  return (
    <Chip
      label={source}
      size="small"
      sx={{
        height: 20,
        fontSize: '0.7rem',
        fontWeight: 600,
        bgcolor: isMcp ? 'primary.main' : 'action.selected',
        color: isMcp ? 'primary.contrastText' : 'text.secondary',
        fontFamily: 'monospace',
      }}
    />
  )
}

function StatusChip({ status }: { status: number | null }) {
  if (status === null) return null
  const isError = status >= 400
  return (
    <Chip
      label={status}
      size="small"
      sx={{
        height: 20,
        fontSize: '0.7rem',
        fontFamily: 'monospace',
        bgcolor: isError ? 'error.main' : 'success.main',
        color: '#fff',
      }}
    />
  )
}

function ParamsRow({ params }: { params: Record<string, unknown> | null }) {
  const [open, setOpen] = useState(false)
  if (!params || Object.keys(params).length === 0) return null
  return (
    <Box>
      <IconButton
        size="small"
        onClick={() => setOpen((v) => !v)}
        aria-label={open ? 'Collapse params' : 'Expand params'}
        aria-expanded={open}
        sx={{ p: 0.25 }}
      >
        {open ? <ExpandLessIcon fontSize="small" /> : <ExpandMoreIcon fontSize="small" />}
      </IconButton>
      <Collapse in={open}>
        <Box
          component="pre"
          sx={{
            mt: 0.5,
            p: 1,
            bgcolor: 'action.hover',
            borderRadius: 1,
            fontSize: '0.7rem',
            fontFamily: 'monospace',
            overflowX: 'auto',
            m: 0,
          }}
        >
          {JSON.stringify(params, null, 2)}
        </Box>
      </Collapse>
    </Box>
  )
}

function EntryRow({ entry }: { entry: ActivityEntry }) {
  return (
    <Box
      sx={{
        display: 'grid',
        gridTemplateColumns: '60px 70px 1fr 90px 44px 60px 50px',
        alignItems: 'start',
        gap: 1,
        py: 0.75,
        px: 2,
        borderBottom: 1,
        borderColor: 'divider',
        '&:hover': { bgcolor: 'action.hover' },
        fontSize: '0.8rem',
      }}
    >
      {/* Time */}
      <Typography
        variant="caption"
        sx={{ fontFamily: 'monospace', color: 'text.disabled', lineHeight: '20px' }}
      >
        {formatTime(entry.logged_at)}
      </Typography>

      {/* Source */}
      <Box sx={{ lineHeight: '20px' }}>
        <SourceChip source={entry.source} />
      </Box>

      {/* Path/tool + params */}
      <Box sx={{ minWidth: 0 }}>
        <Typography
          variant="caption"
          sx={{
            fontFamily: 'monospace',
            color: 'text.primary',
            wordBreak: 'break-all',
            display: 'block',
            lineHeight: '20px',
          }}
        >
          {entry.tool_or_path}
        </Typography>
        <ParamsRow params={entry.params} />
      </Box>

      {/* Repository */}
      <Typography
        variant="caption"
        sx={{
          color: 'text.secondary',
          fontFamily: 'monospace',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
          lineHeight: '20px',
        }}
      >
        {entry.repository ?? '—'}
      </Typography>

      {/* Status */}
      <Box sx={{ lineHeight: '20px' }}>
        <StatusChip status={entry.status_code} />
      </Box>

      {/* Duration */}
      <Typography
        variant="caption"
        sx={{ fontFamily: 'monospace', color: 'text.secondary', lineHeight: '20px' }}
      >
        {entry.duration_ms !== null ? `${entry.duration_ms}ms` : '—'}
      </Typography>

      {/* Result count */}
      <Typography
        variant="caption"
        sx={{ fontFamily: 'monospace', color: 'text.secondary', lineHeight: '20px' }}
      >
        {entry.result_count !== null ? entry.result_count : '—'}
      </Typography>
    </Box>
  )
}

function ActivityContent() {
  const [entries, setEntries] = useState<ActivityEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [autoRefresh, setAutoRefresh] = useState(true)
  const [sourceFilter, setSourceFilter] = useState<string>('')
  const [repoFilter, setRepoFilter] = useState<string>('')
  const [repos, setRepos] = useState<string[]>([])
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)

  // Load the actual repository list once for the filter dropdown
  useEffect(() => {
    getRepositories()
      .then((rs) => setRepos(rs.map((r) => r.name).sort()))
      .catch(() => {}) // non-fatal — filter just stays empty
  }, [])

  const load = useCallback(async () => {
    try {
      const resp = await getActivityLog({
        source: sourceFilter || undefined,
        repository: repoFilter || undefined,
        limit: 200,
      })
      setEntries(resp.entries)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load activity log')
    } finally {
      setLoading(false)
    }
  }, [sourceFilter, repoFilter])

  // Initial load + filter changes
  useEffect(() => {
    setLoading(true)
    void load()
  }, [load])

  // Auto-refresh
  useEffect(() => {
    if (!autoRefresh) {
      if (intervalRef.current) clearInterval(intervalRef.current)
      return
    }
    intervalRef.current = setInterval(() => void load(), AUTO_REFRESH_INTERVAL_MS)
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current)
    }
  }, [autoRefresh, load])

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100vh' }}>
      {/* Header bar */}
      <Box
        sx={{
          px: 3,
          py: 1.5,
          display: 'flex',
          alignItems: 'center',
          gap: 2,
          borderBottom: 1,
          borderColor: 'divider',
          bgcolor: 'background.paper',
          flexShrink: 0,
        }}
      >
        <Typography variant="h6" sx={{ fontWeight: 600, mr: 1 }}>
          Activity Log
        </Typography>

        {/* Source filter */}
        <FormControl size="small" sx={{ minWidth: 110 }}>
          <InputLabel>Source</InputLabel>
          <Select
            label="Source"
            value={sourceFilter}
            onChange={(e) => setSourceFilter(e.target.value)}
          >
            <MenuItem value="">All</MenuItem>
            <MenuItem value="http">HTTP</MenuItem>
            <MenuItem value="mcp">MCP</MenuItem>
          </Select>
        </FormControl>

        {/* Repository filter */}
        <FormControl size="small" sx={{ minWidth: 130 }}>
          <InputLabel>Repository</InputLabel>
          <Select
            label="Repository"
            value={repoFilter}
            onChange={(e) => setRepoFilter(e.target.value)}
          >
            <MenuItem value="">All</MenuItem>
            {repos.map((r) => (
              <MenuItem key={r} value={r}>
                {r}
              </MenuItem>
            ))}
          </Select>
        </FormControl>

        <Box sx={{ flex: 1 }} />

        {/* Entry count */}
        <Typography variant="caption" sx={{ color: 'text.disabled' }}>
          {entries.length} entries
        </Typography>

        {/* Manual refresh */}
        <Tooltip title="Refresh now">
          <span>
            <IconButton size="small" onClick={() => void load()} disabled={loading}>
              <RefreshIcon fontSize="small" />
            </IconButton>
          </span>
        </Tooltip>

        {/* Auto-refresh toggle */}
        <FormControlLabel
          control={
            <Switch
              size="small"
              checked={autoRefresh}
              onChange={(e) => setAutoRefresh(e.target.checked)}
            />
          }
          label={
            <Typography variant="caption" sx={{ color: 'text.secondary' }}>
              Auto ({AUTO_REFRESH_INTERVAL_MS / 1000}s)
            </Typography>
          }
          sx={{ mr: 0 }}
        />
      </Box>

      {/* Column headers */}
      <Box
        sx={{
          display: 'grid',
          gridTemplateColumns: '60px 70px 1fr 90px 44px 60px 50px',
          gap: 1,
          px: 2,
          py: 0.5,
          bgcolor: 'background.paper',
          borderBottom: 1,
          borderColor: 'divider',
          flexShrink: 0,
        }}
      >
        {['Time', 'Source', 'Path / Tool', 'Repository', 'Status', 'Duration', 'Results'].map(
          (h) => (
            <Typography key={h} variant="caption" sx={{ color: 'text.disabled', fontWeight: 600 }}>
              {h}
            </Typography>
          )
        )}
      </Box>

      {/* Content */}
      <Box sx={{ flex: 1, overflow: 'auto' }}>
        {loading && entries.length === 0 ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
            <CircularProgress />
          </Box>
        ) : error ? (
          <Container maxWidth="md" sx={{ py: 4 }}>
            <Alert severity="error">{error}</Alert>
          </Container>
        ) : entries.length === 0 ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', py: 6 }}>
            <Typography variant="body2" color="text.disabled">
              No activity recorded yet.
            </Typography>
          </Box>
        ) : (
          <Paper elevation={0} sx={{ borderRadius: 0 }}>
            {entries.map((entry) => (
              <EntryRow key={entry.id} entry={entry} />
            ))}
          </Paper>
        )}
      </Box>
    </Box>
  )
}

export default function Activity(): React.ReactElement {
  return <ActivityContent />
}
