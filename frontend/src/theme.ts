import { createTheme } from '@mui/material/styles'

// Extend MUI palette with custom code-viewer and symbol-icon colors
declare module '@mui/material/styles' {
  interface Palette {
    code: {
      background: string
      text: string
      lineNumber: string
      lineNumberHighlight: string
      lineNumberHover: string
      lineBorder: string
      highlightBg: string
      highlightHoverBg: string
      hoverBg: string
      symbolUnderline: string
      referenceUnderline: string
      diffAddedBg: string
      diffRemovedBg: string
      diffModifiedBg: string
      diffAddedIndicator: string
      diffRemovedIndicator: string
    }
    symbolIcon: {
      class: string
      function: string
      interface: string
      variable: string
      import: string
      call: string
      usage: string
    }
    fileTree: {
      folder: string
      defaultFile: string
    }
    blame: {
      hash: string
      author: string
      date: string
      border: string
      hoverBg: string
    }
  }
  interface PaletteOptions {
    code?: {
      background?: string
      text?: string
      lineNumber?: string
      lineNumberHighlight?: string
      lineNumberHover?: string
      lineBorder?: string
      highlightBg?: string
      highlightHoverBg?: string
      hoverBg?: string
      symbolUnderline?: string
      referenceUnderline?: string
      diffAddedBg?: string
      diffRemovedBg?: string
      diffModifiedBg?: string
      diffAddedIndicator?: string
      diffRemovedIndicator?: string
    }
    symbolIcon?: {
      class?: string
      function?: string
      interface?: string
      variable?: string
      import?: string
      call?: string
      usage?: string
    }
    fileTree?: {
      folder?: string
      defaultFile?: string
    }
    blame?: {
      hash?: string
      author?: string
      date?: string
      border?: string
      hoverBg?: string
    }
  }
}

export const darkTheme = createTheme({
  palette: {
    mode: 'dark',
    code: {
      background: '#1e1e1e',
      text: '#d4d4d4',
      lineNumber: '#6e7681',
      lineNumberHighlight: '#ffeb3b',
      lineNumberHover: '#fff',
      lineBorder: '#333',
      highlightBg: 'rgba(255, 255, 0, 0.1)',
      highlightHoverBg: 'rgba(255, 255, 0, 0.15)',
      hoverBg: 'rgba(255, 255, 255, 0.05)',
      symbolUnderline: '#569cd6',
      referenceUnderline: '#4ec9b0',
      diffAddedBg: 'rgba(46, 160, 67, 0.15)',
      diffRemovedBg: 'rgba(248, 81, 73, 0.15)',
      diffModifiedBg: 'rgba(255, 166, 87, 0.15)',
      diffAddedIndicator: '#3fb950',
      diffRemovedIndicator: '#f85149',
    },
    symbolIcon: {
      class: '#4ec9b0',
      function: '#dcdcaa',
      interface: '#4fc1ff',
      variable: '#9cdcfe',
      import: '#ce9178',
      call: '#dcdcaa',
      usage: '#9cdcfe',
    },
    fileTree: {
      folder: '#dcb67a',
      defaultFile: '#6e7681',
    },
    blame: {
      hash: '#569cd6',
      author: '#9cdcfe',
      date: '#6e7681',
      border: '#333',
      hoverBg: 'rgba(255, 255, 255, 0.08)',
    },
  },
})

export const lightTheme = createTheme({
  palette: {
    mode: 'light',
    background: {
      default: '#d4d2ce',
      paper: '#d9d7d3',
    },
    text: {
      primary: '#1a1d21',
      secondary: '#484d54',
    },
    divider: '#bfbdb7',
    code: {
      background: '#d0ceca',
      text: '#141820',
      lineNumber: '#6b6965',
      lineNumberHighlight: '#8a5d00',
      lineNumberHover: '#282c34',
      lineBorder: '#c4c2bc',
      highlightBg: 'rgba(228, 182, 57, 0.20)',
      highlightHoverBg: 'rgba(228, 182, 57, 0.30)',
      hoverBg: 'rgba(0, 0, 0, 0.06)',
      symbolUnderline: '#3568d4',
      referenceUnderline: '#408a3f',
      diffAddedBg: 'rgba(80, 161, 79, 0.16)',
      diffRemovedBg: 'rgba(228, 86, 73, 0.16)',
      diffModifiedBg: 'rgba(193, 132, 1, 0.16)',
      diffAddedIndicator: '#408a3f',
      diffRemovedIndicator: '#d4392e',
    },
    symbolIcon: {
      class: '#408a3f',
      function: '#3568d4',
      interface: '#0174a8',
      variable: '#8a5d00',
      import: '#8e4624',
      call: '#3568d4',
      usage: '#8a5d00',
    },
    fileTree: {
      folder: '#8a5d00',
      defaultFile: '#87857f',
    },
    blame: {
      hash: '#3568d4',
      author: '#1a1d21',
      date: '#87857f',
      border: '#c4c2bc',
      hoverBg: 'rgba(0, 0, 0, 0.06)',
    },
  },
})
