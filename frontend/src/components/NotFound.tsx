import { Container, Typography, Box, Button } from '@mui/material'
import { Link as RouterLink } from 'react-router-dom'
import ErrorOutlineIcon from '@mui/icons-material/ErrorOutline'

/**
 * 404 Not Found page component
 */
export function NotFound(): React.ReactElement {
  return (
    <Container maxWidth="sm">
      <Box
        sx={{
          mt: 8,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          textAlign: 'center',
        }}
      >
        <ErrorOutlineIcon sx={{ fontSize: 80, color: 'error.main', mb: 2 }} />
        <Typography variant="h2" component="h1" gutterBottom>
          404
        </Typography>
        <Typography variant="h5" component="h2" color="text.secondary" gutterBottom>
          Page Not Found
        </Typography>
        <Typography variant="body1" color="text.secondary" paragraph>
          The page you are looking for does not exist.
        </Typography>
        <Button component={RouterLink} to="/" variant="contained" size="large" sx={{ mt: 2 }}>
          Go Home
        </Button>
      </Box>
    </Container>
  )
}
