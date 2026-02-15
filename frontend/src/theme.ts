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
      default: '#e6e4e0',
      paper: '#e6e4e0',
    },
    text: {
      primary: '#2e3338',
      secondary: '#5c6168',
    },
    divider: '#ccc9c2',
    code: {
      background: '#e6e4e0',
      text: '#383a42',
      lineNumber: '#918f8b',
      lineNumberHighlight: '#986801',
      lineNumberHover: '#383a42',
      lineBorder: '#d5d3cd',
      highlightBg: 'rgba(228, 182, 57, 0.16)',
      highlightHoverBg: 'rgba(228, 182, 57, 0.26)',
      hoverBg: 'rgba(0, 0, 0, 0.04)',
      symbolUnderline: '#4078f2',
      referenceUnderline: '#50a14f',
      diffAddedBg: 'rgba(80, 161, 79, 0.12)',
      diffRemovedBg: 'rgba(228, 86, 73, 0.12)',
      diffModifiedBg: 'rgba(193, 132, 1, 0.12)',
      diffAddedIndicator: '#50a14f',
      diffRemovedIndicator: '#e45649',
    },
    symbolIcon: {
      class: '#50a14f',
      function: '#4078f2',
      interface: '#0184bc',
      variable: '#986801',
      import: '#a0522d',
      call: '#4078f2',
      usage: '#986801',
    },
    fileTree: {
      folder: '#986801',
      defaultFile: '#9d9b97',
    },
    blame: {
      hash: '#4078f2',
      author: '#2e3338',
      date: '#9d9b97',
      border: '#d5d3cd',
      hoverBg: 'rgba(0, 0, 0, 0.04)',
    },
  },
})
