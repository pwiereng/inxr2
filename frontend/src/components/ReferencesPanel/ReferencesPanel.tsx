import { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  List,
  ListItemButton,
  ListItemText,
  Chip,
  CircularProgress,
  IconButton,
} from '@mui/material';
import CloseIcon from '@mui/icons-material/Close';
import CallMadeIcon from '@mui/icons-material/CallMade';

import { getSymbolReferences, type Reference, type Symbol } from '@/lib/api';

interface ReferencesPanelProps {
  symbol: Symbol | null;
  onReferenceClick?: (reference: Reference) => void;
  onClose?: () => void;
}

export function ReferencesPanel({
  symbol,
  onReferenceClick,
  onClose,
}: ReferencesPanelProps) {
  const [references, setReferences] = useState<Reference[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!symbol) {
      setReferences([]);
      return;
    }

    const fetchReferences = async () => {
      setLoading(true);
      setError(null);
      try {
        const result = await getSymbolReferences(symbol.id);
        setReferences(result.items);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load references');
        setReferences([]);
      } finally {
        setLoading(false);
      }
    };

    fetchReferences();
  }, [symbol]);

  if (!symbol) {
    return (
      <Box sx={{ p: 2 }}>
        <Typography variant="body2" color="text.secondary">
          Select a symbol to see its references
        </Typography>
      </Box>
    );
  }

  // Group references by file
  const referencesByFile = references.reduce(
    (acc, ref) => {
      const file = ref.source_file_path || `File ${ref.source_file_id}`;
      if (!acc[file]) {
        acc[file] = [];
      }
      acc[file].push(ref);
      return acc;
    },
    {} as Record<string, Reference[]>
  );

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Header */}
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          p: 1.5,
          borderBottom: 1,
          borderColor: 'divider',
        }}
      >
        <Box>
          <Typography variant="subtitle2" sx={{ fontFamily: 'monospace' }}>
            {symbol.name}
          </Typography>
          <Typography variant="caption" color="text.secondary">
            {references.length} reference{references.length !== 1 ? 's' : ''}
          </Typography>
        </Box>
        {onClose && (
          <IconButton size="small" onClick={onClose}>
            <CloseIcon fontSize="small" />
          </IconButton>
        )}
      </Box>

      {/* Content */}
      <Box sx={{ flex: 1, overflow: 'auto' }}>
        {loading ? (
          <Box sx={{ display: 'flex', justifyContent: 'center', p: 2 }}>
            <CircularProgress size={24} />
          </Box>
        ) : error ? (
          <Box sx={{ p: 2 }}>
            <Typography variant="body2" color="error">
              {error}
            </Typography>
          </Box>
        ) : references.length === 0 ? (
          <Box sx={{ p: 2 }}>
            <Typography variant="body2" color="text.secondary">
              No references found
            </Typography>
          </Box>
        ) : (
          <List dense disablePadding>
            {Object.entries(referencesByFile).map(([file, refs]) => (
              <Box key={file}>
                {/* File header */}
                <Box
                  sx={{
                    px: 1.5,
                    py: 0.5,
                    bgcolor: 'action.hover',
                    borderBottom: 1,
                    borderColor: 'divider',
                  }}
                >
                  <Typography
                    variant="caption"
                    sx={{
                      fontFamily: 'monospace',
                      fontWeight: 500,
                      display: 'block',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {file}
                  </Typography>
                </Box>

                {/* References in file */}
                {refs.map((ref) => (
                  <ListItemButton
                    key={ref.id}
                    onClick={() => onReferenceClick?.(ref)}
                    sx={{ py: 0.5, px: 1.5 }}
                  >
                    <ListItemText
                      primary={
                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                          <CallMadeIcon fontSize="small" sx={{ color: 'text.secondary' }} />
                          <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>
                            Line {ref.source_line}
                          </Typography>
                          <Chip
                            label={ref.reference_type}
                            size="small"
                            variant="outlined"
                            sx={{ height: 18, fontSize: '0.65rem' }}
                          />
                        </Box>
                      }
                    />
                  </ListItemButton>
                ))}
              </Box>
            ))}
          </List>
        )}
      </Box>
    </Box>
  );
}

export default ReferencesPanel;
