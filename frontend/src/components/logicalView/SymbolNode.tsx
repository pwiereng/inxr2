/**
 * Presentational tree node for a single symbol in LogicalView's outline mode.
 *
 * Renders the symbol row (expand chevron, kind icon, name, go-to-line button,
 * inheritance chips) and recurses into its loaded children. All data fetching,
 * navigation, and selection wiring is supplied by the parent via callbacks.
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
import Tooltip from '@mui/material/Tooltip'
import IconButton from '@mui/material/IconButton'
import CircularProgress from '@mui/material/CircularProgress'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
import ChevronRightIcon from '@mui/icons-material/ChevronRight'
import ArrowForwardIcon from '@mui/icons-material/ArrowForward'
import type { SymbolTreeSymbol, SymbolTreeInheritance } from '@/lib/api'
import { getKindLabel, type SymbolChildren } from '@/lib/logicalView'
import { getKindIcon } from './kindIcons'

export interface SymbolNodeProps {
  symbol: SymbolTreeSymbol
  level: number
  children: SymbolTreeSymbol[] | undefined
  expandedSymbols: Set<number>
  expandingSymbol: number | null
  symbolChildren: SymbolChildren
  highlightedSymbolIds: Set<number>
  onToggle: (symbolId: number) => void
  onClick: (symbol: SymbolTreeSymbol) => void
  onInheritanceClick: (inh: SymbolTreeInheritance, e: React.MouseEvent) => void
  onContextMenuAction: (symbol: SymbolTreeSymbol, e: React.MouseEvent) => void
}

export function SymbolNode({
  symbol,
  level,
  children,
  expandedSymbols,
  expandingSymbol,
  symbolChildren,
  highlightedSymbolIds,
  onToggle,
  onClick,
  onInheritanceClick,
  onContextMenuAction,
}: SymbolNodeProps): React.ReactElement {
  const isExpanded = expandedSymbols.has(symbol.id)
  const isExpanding = expandingSymbol === symbol.id
  const indent = level * 24
  const isHighlighted = highlightedSymbolIds.size > 0 && highlightedSymbolIds.has(symbol.id)

  const handleNavigate = (e: React.MouseEvent) => {
    e.stopPropagation()
    onClick(symbol)
  }

  const rowContent = (
    <>
      {symbol.has_children && (
        <ListItemIcon sx={{ minWidth: 20 }}>
          {isExpanding ? (
            <CircularProgress size={14} />
          ) : isExpanded ? (
            <ExpandMoreIcon sx={{ fontSize: 16 }} />
          ) : (
            <ChevronRightIcon sx={{ fontSize: 16 }} />
          )}
        </ListItemIcon>
      )}
      {!symbol.has_children && <Box sx={{ width: 20 }} />}

      <ListItemIcon sx={{ minWidth: 24 }}>{getKindIcon(symbol.kind)}</ListItemIcon>

      <ListItemText
        primary={
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, flexWrap: 'wrap' }}>
            <Typography
              variant="body2"
              component="span"
              sx={{
                fontFamily: 'monospace',
                fontWeight: symbol.has_children || isHighlighted ? 500 : 400,
                userSelect: 'text',
                ...(isHighlighted && {
                  color: '#61afef',
                }),
              }}
            >
              {symbol.name}
              {symbol.kind === 'function' ||
              symbol.kind === 'method' ||
              symbol.kind === 'constructor' ||
              symbol.kind === 'staticmethod' ||
              symbol.kind === 'classmethod'
                ? '()'
                : ''}
            </Typography>
            <Tooltip title={`Go to line ${symbol.start_line}`} arrow>
              <IconButton
                size="small"
                onClick={handleNavigate}
                sx={{ p: 0.25 }}
                aria-label={`Go to line ${symbol.start_line}`}
              >
                <ArrowForwardIcon sx={{ fontSize: 14 }} />
              </IconButton>
            </Tooltip>

            <Typography variant="caption" color="text.disabled" sx={{ fontFamily: 'monospace' }}>
              {getKindLabel(symbol.kind)}
            </Typography>

            {symbol.inheritance.map((inh, i) => (
              <Tooltip
                key={i}
                title={
                  inh.target_file_path
                    ? `Click: go to source | ${navigator.platform.includes('Mac') ? 'Cmd' : 'Ctrl'}+Click: locate in tree`
                    : ''
                }
                arrow
              >
                <Chip
                  label={`extends ${inh.reference_text}`}
                  size="small"
                  variant="outlined"
                  color="info"
                  sx={{
                    height: 18,
                    fontSize: '0.65rem',
                    cursor: inh.target_file_path ? 'pointer' : 'default',
                  }}
                  onClick={
                    inh.target_file_path
                      ? (e) => {
                          e.stopPropagation()
                          onInheritanceClick(inh, e)
                        }
                      : undefined
                  }
                />
              </Tooltip>
            ))}
          </Box>
        }
      />
    </>
  )

  const rowSx = {
    pl: `${indent + 16}px`,
    py: 0.25,
    ...(isHighlighted && {
      backgroundColor: 'rgba(97, 175, 239, 0.12)',
    }),
  }

  return (
    <>
      {symbol.has_children ? (
        <ListItemButton
          onClick={() => onToggle(symbol.id)}
          onContextMenu={(e) => onContextMenuAction(symbol, e)}
          sx={rowSx}
        >
          {rowContent}
        </ListItemButton>
      ) : (
        <Box
          onContextMenu={(e) => onContextMenuAction(symbol, e)}
          sx={{
            ...rowSx,
            display: 'flex',
            alignItems: 'center',
            pl: `${indent + 16}px`,
            '&:hover': { backgroundColor: 'action.hover' },
          }}
        >
          {rowContent}
        </Box>
      )}

      {symbol.has_children && (
        <Collapse in={isExpanded} timeout="auto">
          {children?.map((child) => (
            <SymbolNode
              key={child.id}
              symbol={child}
              level={level + 1}
              children={symbolChildren[child.id]}
              expandedSymbols={expandedSymbols}
              expandingSymbol={expandingSymbol}
              symbolChildren={symbolChildren}
              highlightedSymbolIds={highlightedSymbolIds}
              onToggle={onToggle}
              onClick={onClick}
              onInheritanceClick={onInheritanceClick}
              onContextMenuAction={onContextMenuAction}
            />
          ))}
        </Collapse>
      )}
    </>
  )
}
