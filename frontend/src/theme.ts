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
      default: '#f7f6f2',
      paper: '#f7f6f2',
    },
    text: {
      primary: '#141820',
      secondary: '#3d424a',
    },
    divider: '#d0cec8',
    code: {
      background: '#f7f6f2',
      text: '#141820',
      lineNumber: '#7a7874',
      lineNumberHighlight: '#8a5d00',
      lineNumberHover: '#0d1117',
      lineBorder: '#d8d6d0',
      highlightBg: 'rgba(228, 182, 57, 0.18)',
      highlightHoverBg: 'rgba(228, 182, 57, 0.28)',
      hoverBg: 'rgba(0, 0, 0, 0.04)',
      symbolUnderline: '#2b5ec2',
      referenceUnderline: '#347a33',
      diffAddedBg: 'rgba(80, 161, 79, 0.14)',
      diffRemovedBg: 'rgba(228, 86, 73, 0.14)',
      diffModifiedBg: 'rgba(193, 132, 1, 0.14)',
      diffAddedIndicator: '#347a33',
      diffRemovedIndicator: '#c9301e',
    },
    symbolIcon: {
      class: '#347a33',
      function: '#2b5ec2',
      interface: '#0168a0',
      variable: '#7a5200',
      import: '#7e3c1e',
      call: '#2b5ec2',
      usage: '#7a5200',
    },
    fileTree: {
      folder: '#7a5200',
      defaultFile: '#7a7874',
    },
    blame: {
      hash: '#2b5ec2',
      author: '#141820',
      date: '#7a7874',
      border: '#d8d6d0',
      hoverBg: 'rgba(0, 0, 0, 0.04)',
    },
  },
})
