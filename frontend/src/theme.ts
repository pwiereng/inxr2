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
    code: {
      background: '#ffffff',
      text: '#24292e',
      lineNumber: '#959da5',
      lineNumberHighlight: '#d29922',
      lineNumberHover: '#24292e',
      lineBorder: '#e1e4e8',
      highlightBg: 'rgba(255, 223, 93, 0.2)',
      highlightHoverBg: 'rgba(255, 223, 93, 0.3)',
      hoverBg: 'rgba(0, 0, 0, 0.04)',
      symbolUnderline: '#0366d6',
      referenceUnderline: '#22863a',
      diffAddedBg: 'rgba(46, 160, 67, 0.12)',
      diffRemovedBg: 'rgba(248, 81, 73, 0.12)',
      diffModifiedBg: 'rgba(255, 166, 87, 0.12)',
      diffAddedIndicator: '#22863a',
      diffRemovedIndicator: '#cb2431',
    },
    symbolIcon: {
      class: '#267f99',
      function: '#795e26',
      interface: '#267f99',
      variable: '#0070c1',
      import: '#a31515',
      call: '#795e26',
      usage: '#0070c1',
    },
    fileTree: {
      folder: '#b08d57',
      defaultFile: '#6a737d',
    },
    blame: {
      hash: '#0366d6',
      author: '#24292e',
      date: '#959da5',
      border: '#e1e4e8',
      hoverBg: 'rgba(0, 0, 0, 0.04)',
    },
  },
})
