import { Component, type ErrorInfo, type ReactNode } from 'react'
import { Box, Typography, Button, Collapse } from '@mui/material'
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
import ExpandLessIcon from '@mui/icons-material/ExpandLess'
import RefreshIcon from '@mui/icons-material/Refresh'

interface ErrorBoundaryProps {
  children: ReactNode
}

interface ErrorBoundaryState {
  hasError: boolean
  error: Error | null
  showDetails: boolean
}

/**
 * Error boundary component that catches rendering errors in its child tree
 * and displays a fallback UI with optional error details instead of crashing
 * the entire React component tree.
 */
export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props)
    this.state = { hasError: false, error: null, showDetails: false }
  }

  static getDerivedStateFromError(error: Error): Partial<ErrorBoundaryState> {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo): void {
    console.error('ErrorBoundary caught an error:', error, errorInfo)
  }

  handleReset = (): void => {
    this.setState({ hasError: false, error: null, showDetails: false })
  }

  handleToggleDetails = (): void => {
    this.setState((prev) => ({ showDetails: !prev.showDetails }))
  }

  render(): ReactNode {
    if (this.state.hasError) {
      return (
        <Box
          role="alert"
          sx={{
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            minHeight: 200,
            p: 4,
            textAlign: 'center',
          }}
        >
          <ErrorOutlineIcon sx={{ fontSize: 48, color: 'error.main', mb: 2 }} />
          <Typography variant="h6" gutterBottom>
            Something went wrong
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
            An unexpected error occurred while rendering this section.
          </Typography>
          <Button
            variant="contained"
            startIcon={<RefreshIcon />}
            onClick={this.handleReset}
            sx={{ mb: 2 }}
          >
            Try Again
          </Button>
          {import.meta.env.DEV && this.state.error && (
            <>
              <Button
                size="small"
                onClick={this.handleToggleDetails}
                endIcon={this.state.showDetails ? <ExpandLessIcon /> : <ExpandMoreIcon />}
                sx={{ color: 'text.secondary' }}
                aria-expanded={this.state.showDetails}
                aria-controls="error-details"
              >
                {this.state.showDetails ? 'Hide Details' : 'Show Details'}
              </Button>
              <Collapse in={this.state.showDetails}>
                <Box
                  id="error-details"
                  sx={{
                    mt: 2,
                    p: 2,
                    maxWidth: 600,
                    bgcolor: 'action.hover',
                    borderRadius: 1,
                    textAlign: 'left',
                    overflow: 'auto',
                  }}
                >
                  <Typography
                    variant="body2"
                    component="pre"
                    sx={{
                      fontFamily: 'monospace',
                      fontSize: '0.75rem',
                      whiteSpace: 'pre-wrap',
                      wordBreak: 'break-word',
                      m: 0,
                    }}
                  >
                    {this.state.error.message}
                    {this.state.error.stack && `\n\n${this.state.error.stack}`}
                  </Typography>
                </Box>
              </Collapse>
            </>
          )}
        </Box>
      )
    }

    return this.props.children
  }
}
