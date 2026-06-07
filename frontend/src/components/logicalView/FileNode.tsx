/**
 * Presentational tree node for a file in LogicalView's outline mode.
 *
 * Renders the file row (expand chevron, folder icon, path, symbol-count chip,
 * optional per-kind count chips) and, when expanded, its top-level symbols via
 * SymbolNode. Data fetching and navigation are supplied by the parent.
 */
import {
  Box,
  Typography,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Collapse,
  Chip,
} from '@mui/material'
import CircularProgress from '@mui/material/CircularProgress'
import FolderIcon from '@mui/icons-material/Folder'
import FolderOpenIcon from '@mui/icons-material/FolderOpen'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
import ChevronRightIcon from '@mui/icons-material/ChevronRight'
import type { SymbolTreeFile, SymbolTreeSymbol, SymbolTreeInheritance } from '@/lib/api'
import {
  getKindColor,
  getKindLabel,
  fileName,
  fileDir,
  type SymbolChildren,
} from '@/lib/logicalView'
import { SymbolNode } from './SymbolNode'

export interface FileNodeProps {
  file: SymbolTreeFile
  isExpanded: boolean
  isExpanding: boolean
  symbols: SymbolTreeSymbol[] | undefined
  showKindCounts: boolean
  highlightedSymbolIds: Set<number>
  symbolChildren: SymbolChildren
  expandedSymbols: Set<number>
  expandingSymbol: number | null
  onToggle: (fileId: number) => void
  onToggleSymbol: (symbolId: number) => void
  onSymbolClick: (symbol: SymbolTreeSymbol) => void
  onInheritanceClick: (inh: SymbolTreeInheritance, e: React.MouseEvent) => void
  onSymbolContextMenu: (symbol: SymbolTreeSymbol, e: React.MouseEvent) => void
}

export function FileNode({
  file,
  isExpanded,
  isExpanding,
  symbols,
  showKindCounts,
  highlightedSymbolIds,
  symbolChildren,
  expandedSymbols,
  expandingSymbol,
  onToggle,
  onToggleSymbol,
  onSymbolClick,
  onInheritanceClick,
  onSymbolContextMenu,
}: FileNodeProps): React.ReactElement {
  const dir = fileDir(file.path)
  const name = fileName(file.path)

  return (
    <>
      <ListItemButton
        data-file-id={file.file_id}
        onClick={() => onToggle(file.file_id)}
        sx={{ py: 0.5 }}
      >
        <ListItemIcon sx={{ minWidth: 28 }}>
          {isExpanding ? (
            <CircularProgress size={16} />
          ) : isExpanded ? (
            <ExpandMoreIcon fontSize="small" />
          ) : (
            <ChevronRightIcon fontSize="small" />
          )}
        </ListItemIcon>
        <ListItemIcon sx={{ minWidth: 28 }}>
          {isExpanded ? (
            <FolderOpenIcon fontSize="small" color="primary" />
          ) : (
            <FolderIcon fontSize="small" color="primary" />
          )}
        </ListItemIcon>
        <ListItemText
          primary={
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
              <Typography variant="body2" component="span" sx={{ fontFamily: 'monospace' }}>
                <Typography
                  variant="body2"
                  component="span"
                  color="text.secondary"
                  sx={{ fontFamily: 'monospace' }}
                >
                  {dir}
                </Typography>
                {name}
              </Typography>
              <Chip
                label={file.symbol_count}
                size="small"
                variant="outlined"
                sx={{ height: 18, fontSize: '0.7rem' }}
              />
              {showKindCounts &&
                Object.entries(file.all_kind_counts)
                  .sort(([, a], [, b]) => b - a)
                  .map(([kind, count]) => (
                    <Chip
                      key={kind}
                      label={`${count} ${getKindLabel(kind, count !== 1)}`}
                      size="small"
                      sx={{
                        height: 18,
                        fontSize: '0.65rem',
                        backgroundColor: getKindColor(kind) + '22',
                        color: getKindColor(kind),
                        borderColor: getKindColor(kind) + '44',
                        border: '1px solid',
                      }}
                    />
                  ))}
            </Box>
          }
        />
      </ListItemButton>

      <Collapse in={isExpanded} timeout="auto">
        {symbols?.map((symbol) => (
          <SymbolNode
            key={symbol.id}
            symbol={symbol}
            level={1}
            children={symbolChildren[symbol.id]}
            expandedSymbols={expandedSymbols}
            expandingSymbol={expandingSymbol}
            symbolChildren={symbolChildren}
            highlightedSymbolIds={highlightedSymbolIds}
            onToggle={onToggleSymbol}
            onClick={onSymbolClick}
            onInheritanceClick={onInheritanceClick}
            onContextMenuAction={onSymbolContextMenu}
          />
        ))}
      </Collapse>
    </>
  )
}
