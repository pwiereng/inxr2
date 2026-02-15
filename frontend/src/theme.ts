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
      default: '#f0f2f5',
      paper: '#f8f9fb',
    },
    text: {
      primary: '#1f2328',
      secondary: '#59636e',
    },
    divider: '#d1d9e0',
    code: {
      background: '#f6f8fa',
      text: '#1f2328',
      lineNumber: '#7d8590',
      lineNumberHighlight: '#bf8700',
      lineNumberHover: '#1f2328',
      lineBorder: '#d1d9e0',
      highlightBg: 'rgba(255, 212, 59, 0.2)',
      highlightHoverBg: 'rgba(255, 212, 59, 0.3)',
      hoverBg: 'rgba(208, 215, 222, 0.32)',
      symbolUnderline: '#0969da',
      referenceUnderline: '#1a7f37',
      diffAddedBg: 'rgba(46, 160, 67, 0.15)',
      diffRemovedBg: 'rgba(255, 129, 130, 0.15)',
      diffModifiedBg: 'rgba(210, 153, 34, 0.15)',
      diffAddedIndicator: '#1a7f37',
      diffRemovedIndicator: '#cf222e',
    },
    symbolIcon: {
      class: '#1a7f37',
      function: '#8250df',
      interface: '#0969da',
      variable: '#0550ae',
      import: '#953800',
      call: '#8250df',
      usage: '#0550ae',
    },
    fileTree: {
      folder: '#9a6700',
      defaultFile: '#7d8590',
    },
    blame: {
      hash: '#0969da',
      author: '#1f2328',
      date: '#7d8590',
      border: '#d1d9e0',
      hoverBg: 'rgba(208, 215, 222, 0.32)',
    },
  },
})
