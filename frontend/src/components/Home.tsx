import { Container, Typography, Box, Paper, Button } from '@mui/material'
import CodeIcon from '@mui/icons-material/Code'
import FolderIcon from '@mui/icons-material/Folder'
import { Link } from 'react-router-dom'

/**
 * Home page component
 * Placeholder for Phase 1.2, will be replaced with actual repository browser in Phase 5
 */
export function Home() {
  return (
    <Container maxWidth="md">
      <Box sx={{ mt: 8, mb: 4, textAlign: 'center' }}>
        <CodeIcon sx={{ fontSize: 80, color: 'primary.main', mb: 2 }} />
        <Typography variant="h2" component="h1" gutterBottom>
          INXR2
        </Typography>
        <Typography variant="h5" component="h2" color="text.secondary" gutterBottom>
          Cross-Reference Code Browser
        </Typography>
      </Box>

      <Paper elevation={2} sx={{ p: 4, mt: 4 }}>
        <Typography variant="h6" gutterBottom>
          Phase 1.2 - Project Setup Complete
        </Typography>
        <Typography variant="body1" paragraph>
          The React frontend foundation is now in place with:
        </Typography>
        <Box component="ul" sx={{ pl: 2 }}>
          <Typography component="li" variant="body2">
            TypeScript with strict mode
          </Typography>
          <Typography component="li" variant="body2">
            React Router for navigation
          </Typography>
          <Typography component="li" variant="body2">
            Material-UI component library
          </Typography>
          <Typography component="li" variant="body2">
            API client with dependency injection
          </Typography>
          <Typography component="li" variant="body2">
            Context API for app-wide state
          </Typography>
          <Typography component="li" variant="body2">
            Vitest + React Testing Library
          </Typography>
          <Typography component="li" variant="body2">
            Vite proxy to FastAPI backend
          </Typography>
        </Box>
        <Typography variant="body2" sx={{ mt: 2, fontStyle: 'italic' }}>
          Phase 5 will implement the full UI with repository browser, code viewer, and search.
        </Typography>
      </Paper>

      <Box sx={{ mt: 4, textAlign: 'center' }}>
        <Button
          component={Link}
          to="/repositories"
          variant="contained"
          size="large"
          startIcon={<FolderIcon />}
        >
          Browse Repositories
        </Button>
      </Box>
    </Container>
  )
}
