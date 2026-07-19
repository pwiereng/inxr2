/**
 * Symbol-kind icon mapping for the LogicalView tree.
 *
 * Lives alongside the LogicalView node components (not in lib/logicalView.ts)
 * because it returns JSX — keeping the pure helper module free of React/MUI.
 */
import type { ReactNode } from 'react'
import ClassIcon from '@mui/icons-material/Category'
import FunctionIcon from '@mui/icons-material/Functions'
import FieldIcon from '@mui/icons-material/DataObject'

export const KIND_ICONS: Record<string, ReactNode> = {
  class: <ClassIcon fontSize="small" sx={{ color: '#e5c07b' }} />,
  interface: <ClassIcon fontSize="small" sx={{ color: '#56b6c2' }} />,
  struct: <ClassIcon fontSize="small" sx={{ color: '#d19a66' }} />,
  record: <ClassIcon fontSize="small" sx={{ color: '#d19a66' }} />,
  enum: <ClassIcon fontSize="small" sx={{ color: '#c678dd' }} />,
  trait: <ClassIcon fontSize="small" sx={{ color: '#98c379' }} />,
  function: <FunctionIcon fontSize="small" sx={{ color: '#61afef' }} />,
  method: <FunctionIcon fontSize="small" sx={{ color: '#61afef' }} />,
  staticmethod: <FunctionIcon fontSize="small" sx={{ color: '#61afef' }} />,
  classmethod: <FunctionIcon fontSize="small" sx={{ color: '#61afef' }} />,
  constructor: <FunctionIcon fontSize="small" sx={{ color: '#61afef' }} />,
  getter: <FunctionIcon fontSize="small" sx={{ color: '#61afef' }} />,
  setter: <FunctionIcon fontSize="small" sx={{ color: '#61afef' }} />,
  variable: <FieldIcon fontSize="small" sx={{ color: '#abb2bf' }} />,
  class_variable: <FieldIcon fontSize="small" sx={{ color: '#d19a66' }} />,
  instance_variable: <FieldIcon fontSize="small" sx={{ color: '#abb2bf' }} />,
  constant: <FieldIcon fontSize="small" sx={{ color: '#d19a66' }} />,
}

/** Icon for a symbol kind; unknown kinds fall back to the neutral field icon. */
export function getKindIcon(kind: string): ReactNode {
  return KIND_ICONS[kind] ?? <FieldIcon fontSize="small" sx={{ color: '#abb2bf' }} />
}
