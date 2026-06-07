/**
 * Presentational tree node for a symbol shown in LogicalView's kind mode.
 *
 * Container kinds (class/interface/…) expand to reveal their children via
 * SymbolNode; callable kinds render a leaf row. The file path doubles as a
 * "view in outline" link. Navigation and fetching are supplied by the parent.
 */
import { useMemo } from 'react'
import {
  Box,
  Typography,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Collapse,
} from '@mui/material'
import Tooltip from '@mui/material/Tooltip'
import IconButton from '@mui/material/IconButton'
import CircularProgress from '@mui/material/CircularProgress'
import ExpandMoreIcon from '@mui/icons-material/ExpandMore'
import ChevronRightIcon from '@mui/icons-material/ChevronRight'
import ArrowForwardIcon from '@mui/icons-material/ArrowForward'
import type { Symbol as ApiSymbol, SymbolTreeSymbol, SymbolTreeInheritance } from '@/lib/api'
import { fileName, fileDir, type SymbolChildren } from '@/lib/logicalView'
import { getKindIcon } from './kindIcons'
import { SymbolNode } from './SymbolNode'

export interface KindSymbolNodeProps {
  symbol: ApiSymbol
  isExpanded: boolean
  isExpanding: boolean
  children: SymbolTreeSymbol[] | undefined
  symbolChildren: SymbolChildren
  expandedSymbols: Set<number>
  expandingSymbol: number | null
  onToggle: (symbolId: number) => void
  onSymbolClick: (symbol: SymbolTreeSymbol) => void
  onInheritanceClick: (inh: SymbolTreeInheritance, e: React.MouseEvent) => void
  onSymbolContextMenu: (symbol: SymbolTreeSymbol, e: React.MouseEvent) => void
  onSwitchToOutline: (filePath: string) => void
  indent?: number
}

export function KindSymbolNode({
  symbol,
  isExpanded,
  isExpanding,
  children,
  symbolChildren,
  expandedSymbols,
  expandingSymbol,
  onToggle,
  onSymbolClick,
  onInheritanceClick,
  onSymbolContextMenu,
  onSwitchToOutline,
  indent = 0,
}: KindSymbolNodeProps): React.ReactElement {
  const isCallable =
    symbol.kind === 'function' ||
    symbol.kind === 'method' ||
    symbol.kind === 'constructor' ||
    symbol.kind === 'staticmethod' ||
    symbol.kind === 'classmethod'

  const isContainer =
    symbol.kind === 'class' ||
    symbol.kind === 'interface' ||
    symbol.kind === 'struct' ||
    symbol.kind === 'record' ||
    symbol.kind === 'enum' ||
    symbol.kind === 'namespace'

  // Convert ApiSymbol to SymbolTreeSymbol shape for navigation
  const asTreeSymbol: SymbolTreeSymbol = useMemo(
    () => ({
      id: symbol.id,
      name: symbol.name,
      kind: symbol.kind,
      start_line: symbol.start_line,
      end_line: symbol.end_line,
      file_path: symbol.file_path,
      has_children: isContainer,
      signature: symbol.signature,
      inheritance: [],
    }),
    [symbol, isContainer]
  )

  const kindRowContent = (
    <>
      {isContainer && (
        <ListItemIcon sx={{ minWidth: 28 }}>
          {isExpanding ? (
            <CircularProgress size={16} />
          ) : isExpanded ? (
            <ExpandMoreIcon fontSize="small" />
          ) : (
            <ChevronRightIcon fontSize="small" />
          )}
        </ListItemIcon>
      )}
      {!isContainer && <Box sx={{ width: 28 }} />}
      <ListItemIcon sx={{ minWidth: 24 }}>{getKindIcon(symbol.kind)}</ListItemIcon>
      <ListItemText
        primary={
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, flexWrap: 'wrap' }}>
            <Typography
              variant="body2"
              component="span"
              sx={{
                fontFamily: 'monospace',
                fontWeight: 500,
                userSelect: 'text',
              }}
            >
              {symbol.name}
              {isCallable ? '()' : ''}
            </Typography>
            <Tooltip title={`Go to line ${symbol.start_line}`} arrow>
              <IconButton
                size="small"
                onClick={(e) => {
                  e.stopPropagation()
                  onSymbolClick(asTreeSymbol)
                }}
                sx={{ p: 0.25 }}
                aria-label={`Go to line ${symbol.start_line}`}
              >
                <ArrowForwardIcon sx={{ fontSize: 14 }} />
              </IconButton>
            </Tooltip>
            {symbol.file_path && (
              <Tooltip title="View in Outline mode" arrow>
                <Typography
                  variant="caption"
                  component="span"
                  sx={{
                    fontFamily: 'monospace',
                    color: 'text.secondary',
                    cursor: 'pointer',
                    '&:hover': { color: 'primary.main', textDecoration: 'underline' },
                  }}
                  onClick={(e) => {
                    e.stopPropagation()
                    onSwitchToOutline(symbol.file_path!)
                  }}
                >
                  {fileDir(symbol.file_path)}
                  <Typography
                    variant="caption"
                    component="span"
                    sx={{ fontFamily: 'monospace', color: 'text.primary' }}
                  >
                    {fileName(symbol.file_path)}
                  </Typography>
                </Typography>
              </Tooltip>
            )}
          </Box>
        }
      />
    </>
  )

  return (
    <>
      {isContainer ? (
        <ListItemButton
          onClick={() => onToggle(symbol.id)}
          onContextMenu={(e) => onSymbolContextMenu(asTreeSymbol, e)}
          sx={{ py: 0.5, pl: 2 + indent * 3 }}
        >
          {kindRowContent}
        </ListItemButton>
      ) : (
        <Box
          onContextMenu={(e) => onSymbolContextMenu(asTreeSymbol, e)}
          sx={{
            py: 0.5,
            pl: 2 + indent * 3,
            display: 'flex',
            alignItems: 'center',
            '&:hover': { backgroundColor: 'action.hover' },
          }}
        >
          {kindRowContent}
        </Box>
      )}

      {isContainer && (
        <Collapse in={isExpanded} timeout="auto">
          {children?.map((child) => (
            <SymbolNode
              key={child.id}
              symbol={child}
              level={1}
              children={symbolChildren[child.id]}
              expandedSymbols={expandedSymbols}
              expandingSymbol={expandingSymbol}
              symbolChildren={symbolChildren}
              highlightedSymbolIds={new Set()}
              onToggle={onToggle}
              onClick={onSymbolClick}
              onInheritanceClick={onInheritanceClick}
              onContextMenuAction={onSymbolContextMenu}
            />
          ))}
        </Collapse>
      )}
    </>
  )
}
