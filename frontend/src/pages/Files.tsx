import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import {
  Container,
  Typography,
  Box,
  Paper,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  MenuItem,
  Select,
  FormControl,
  InputLabel,
  Chip,
  CircularProgress,
  Alert,
  Button,
} from '@mui/material'
import ArrowBackIcon from '@mui/icons-material/ArrowBack'
import InsertDriveFileIcon from '@mui/icons-material/InsertDriveFile'

interface File {
  id: number
  repository_id: number
  commit_id: number
  path: string
  language: string | null
  size_bytes: number
  line_count: number | null
}

export default function Files(): React.ReactElement {
  const { repositoryId } = useParams<{ repositoryId: string }>()
  const [files, setFiles] = useState<File[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [searchTerm, setSearchTerm] = useState('')
  const [filterLanguage, setFilterLanguage] = useState<string>('')

  useEffect(() => {
    const fetchFiles = async () => {
      try {
        const response = await fetch(`http://localhost:8000/api/repositories/${repositoryId}/files`)
        if (!response.ok) {
          throw new Error('Failed to fetch files')
        }
        const data = await response.json()
        setFiles(data)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error')
      } finally {
        setLoading(false)
      }
    }

    if (repositoryId) {
      fetchFiles()
    }
  }, [repositoryId])

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }

  const getLanguageColor = (language: string | null): 'primary' | 'secondary' | 'default' => {
    if (!language) return 'default'
    const colors: Record<string, 'primary' | 'secondary'> = {
      python: 'primary',
      javascript: 'secondary',
      typescript: 'primary',
      java: 'secondary',
      go: 'primary',
      rust: 'secondary',
    }
    return colors[language.toLowerCase()] || 'default'
  }

  // Get unique languages for filter
  const languages = Array.from(new Set(files.map((f) => f.language).filter(Boolean))).sort()

  // Filter files
  const filteredFiles = files.filter((file) => {
    const matchesSearch = file.path.toLowerCase().includes(searchTerm.toLowerCase())
    const matchesLanguage = !filterLanguage || file.language === filterLanguage
    return matchesSearch && matchesLanguage
  })

  if (loading) {
    return (
      <Container maxWidth="lg" sx={{ mt: 4 }}>
        <Box sx={{ display: 'flex', justifyContent: 'center', mt: 8 }}>
          <CircularProgress />
        </Box>
      </Container>
    )
  }

  if (error) {
    return (
      <Container maxWidth="lg" sx={{ mt: 4 }}>
        <Alert severity="error">Error: {error}</Alert>
      </Container>
    )
  }

  return (
    <Container maxWidth="lg" sx={{ mt: 4, mb: 4 }}>
      <Box sx={{ mb: 4 }}>
        <Button component={Link} to="/repositories" startIcon={<ArrowBackIcon />} sx={{ mb: 2 }}>
          Back to Repositories
        </Button>
        <Typography variant="h4" component="h1" gutterBottom>
          Files
        </Typography>
        <Typography variant="body1" color="text.secondary">
          {filteredFiles.length} {filteredFiles.length === 1 ? 'file' : 'files'}
          {searchTerm && ` matching "${searchTerm}"`}
        </Typography>
      </Box>

      {/* Filters */}
      <Paper sx={{ p: 2, mb: 3 }}>
        <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
          <TextField
            label="Search files"
            variant="outlined"
            size="small"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            sx={{ flex: 1, minWidth: 200 }}
          />
          <FormControl size="small" sx={{ minWidth: 200 }}>
            <InputLabel>Language</InputLabel>
            <Select
              value={filterLanguage}
              label="Language"
              onChange={(e) => setFilterLanguage(e.target.value)}
            >
              <MenuItem value="">All Languages</MenuItem>
              {languages.map((lang) => (
                <MenuItem key={lang} value={lang || ''}>
                  {lang || 'Unknown'}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
        </Box>
      </Paper>

      {/* Files Table */}
      {filteredFiles.length === 0 ? (
        <Paper sx={{ p: 4, textAlign: 'center' }}>
          <Typography variant="body1" color="text.secondary">
            {searchTerm || filterLanguage ? 'No files match your filters' : 'No files found'}
          </Typography>
        </Paper>
      ) : (
        <TableContainer component={Paper}>
          <Table>
            <TableHead>
              <TableRow>
                <TableCell>Path</TableCell>
                <TableCell>Language</TableCell>
                <TableCell align="right">Size</TableCell>
                <TableCell align="right">Lines</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {filteredFiles.map((file) => (
                <TableRow
                  key={file.id}
                  hover
                  sx={{ '&:last-child td, &:last-child th': { border: 0 } }}
                >
                  <TableCell>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                      <InsertDriveFileIcon fontSize="small" color="action" />
                      <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
                        {file.path}
                      </Typography>
                    </Box>
                  </TableCell>
                  <TableCell>
                    {file.language ? (
                      <Chip
                        label={file.language}
                        size="small"
                        color={getLanguageColor(file.language)}
                      />
                    ) : (
                      <Typography variant="body2" color="text.secondary">
                        -
                      </Typography>
                    )}
                  </TableCell>
                  <TableCell align="right">
                    <Typography variant="body2">{formatFileSize(file.size_bytes)}</Typography>
                  </TableCell>
                  <TableCell align="right">
                    <Typography variant="body2">
                      {file.line_count ? file.line_count.toLocaleString() : '-'}
                    </Typography>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}
    </Container>
  )
}
