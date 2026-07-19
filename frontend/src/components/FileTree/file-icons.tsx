import { ReactElement } from 'react'
import { Box } from '@mui/material'

/**
 * File icon configuration - defines the visual badge for each file type
 */
interface FileIconConfig {
  /** Short text label displayed on the badge (1-4 chars) */
  label: string
  /** Background color of the badge (use brand colors where possible) */
  color: string
  /** Text color (defaults to white) */
  textColor?: string
}

// ---------------------------------------------------------------------------
// Icon mappings
// ---------------------------------------------------------------------------

/**
 * Language-based icon lookup (language field from backend).
 * Keys are lowercase language identifiers returned by the language detector.
 */
const LANGUAGE_ICONS: Record<string, FileIconConfig> = {
  // Web frontend
  typescript: { label: 'TS', color: '#3178C6' },
  javascript: { label: 'JS', color: '#F0DB4F', textColor: '#323330' },
  tsx: { label: 'TX', color: '#3178C6' },
  jsx: { label: 'JX', color: '#61DAFB', textColor: '#282C34' },
  html: { label: '<>', color: '#E44D26' },
  css: { label: 'CSS', color: '#563D7C' },
  scss: { label: 'SC', color: '#CF649A' },
  sass: { label: 'SA', color: '#CF649A' },
  less: { label: 'LE', color: '#1D365D' },
  stylus: { label: 'ST', color: '#FF6347' },
  vue: { label: 'VU', color: '#42B883' },
  svelte: { label: 'SV', color: '#FF3E00' },

  // Systems & compiled
  python: { label: 'PY', color: '#3572A5' },
  java: { label: 'JV', color: '#B07219' },
  csharp: { label: 'C#', color: '#239120' },
  c: { label: 'C', color: '#555555' },
  cpp: { label: '++', color: '#00599C' },
  'c++': { label: '++', color: '#00599C' },
  'objective-c': { label: 'OC', color: '#438EFF' },
  objectivec: { label: 'OC', color: '#438EFF' },
  go: { label: 'GO', color: '#00ADD8' },
  rust: { label: 'RS', color: '#DEA584' },
  swift: { label: 'SW', color: '#FA7343' },
  kotlin: { label: 'KT', color: '#7F52FF' },
  dart: { label: 'DA', color: '#00B4AB' },
  scala: { label: 'SCA', color: '#DC322F' },

  // Scripting
  ruby: { label: 'RB', color: '#CC342D' },
  php: { label: 'PHP', color: '#777BB4' },
  perl: { label: 'PL', color: '#39457E' },
  lua: { label: 'LU', color: '#2C2D72' },
  r: { label: 'R', color: '#276DC3' },
  julia: { label: 'JL', color: '#9558B2' },
  elixir: { label: 'EX', color: '#6E4A7E' },
  erlang: { label: 'ER', color: '#B83998' },
  haskell: { label: 'HS', color: '#5E5086' },
  clojure: { label: 'CLJ', color: '#63B132' },
  fsharp: { label: 'F#', color: '#B845FC' },
  ocaml: { label: 'ML', color: '#EC6813' },

  // Shell & scripting
  shell: { label: '$_', color: '#4EAA25' },
  bash: { label: '$_', color: '#4EAA25' },
  zsh: { label: '$_', color: '#4EAA25' },
  fish: { label: '$_', color: '#4EAA25' },
  powershell: { label: 'PS', color: '#012456' },
  batch: { label: 'BA', color: '#C1F12E', textColor: '#1E3A10' },

  // Data & config
  json: { label: '{}', color: '#292929' },
  yaml: { label: 'YM', color: '#CB171E' },
  toml: { label: 'TM', color: '#9C4121' },
  xml: { label: '</', color: '#E8710A' },
  csv: { label: 'CSV', color: '#237346' },
  ini: { label: 'INI', color: '#6D8086' },

  // Documentation
  markdown: { label: 'MD', color: '#083FA1' },
  restructuredtext: { label: 'RST', color: '#141414' },
  latex: { label: 'TEX', color: '#008080' },
  tex: { label: 'TEX', color: '#008080' },

  // Database
  sql: { label: 'SQL', color: '#E38C00' },
  plpgsql: { label: 'PG', color: '#336791' },
  plsql: { label: 'ORA', color: '#F80000' },

  // Infrastructure & DevOps
  dockerfile: { label: 'DK', color: '#2496ED' },
  docker: { label: 'DK', color: '#2496ED' },
  terraform: { label: 'TF', color: '#7B42BC' },
  hcl: { label: 'HCL', color: '#7B42BC' },
  nix: { label: 'NIX', color: '#5277C3' },

  // API & schemas
  graphql: { label: 'GQ', color: '#E10098' },
  protobuf: { label: 'PB', color: '#4285F4' },

  // Assembly & low-level
  assembly: { label: 'ASM', color: '#6E4C13' },
  wasm: { label: 'WA', color: '#654FF0' },

  // Mobile
  'objective-cpp': { label: 'O+', color: '#438EFF' },

  // Other
  groovy: { label: 'GRV', color: '#4298B8' },
  pascal: { label: 'PA', color: '#E3F171', textColor: '#2C3E17' },
  fortran: { label: 'FN', color: '#4D41B1' },
  cobol: { label: 'CO', color: '#3D5A80' },
  lisp: { label: 'LI', color: '#3FB68B' },
  scheme: { label: 'SM', color: '#1E4AEC' },
  prolog: { label: 'PRO', color: '#74283C' },
  vhdl: { label: 'VH', color: '#ADB2CB' },
  verilog: { label: 'VL', color: '#B2B7F8' },
  zig: { label: 'ZG', color: '#F7A41D', textColor: '#1B1B1B' },
  nim: { label: 'NM', color: '#FFE953', textColor: '#1B1B1B' },
  crystal: { label: 'CR', color: '#000100' },
  v: { label: 'V', color: '#5D87BF' },
  d: { label: 'D', color: '#B03931' },
  ada: { label: 'ADA', color: '#02F88C', textColor: '#1B2B1B' },
}

/**
 * Extension-based icon lookup (for files without a language field,
 * or config/special files identified by extension or exact name).
 * Keys are lowercase, without the leading dot.
 */
const EXTENSION_ICONS: Record<string, FileIconConfig> = {
  // TypeScript / JavaScript variants (duplication from language for extension matching)
  ts: { label: 'TS', color: '#3178C6' },
  tsx: { label: 'TX', color: '#3178C6' },
  js: { label: 'JS', color: '#F0DB4F', textColor: '#323330' },
  jsx: { label: 'JX', color: '#61DAFB', textColor: '#282C34' },
  mjs: { label: 'MJ', color: '#F0DB4F', textColor: '#323330' },
  cjs: { label: 'CJS', color: '#F0DB4F', textColor: '#323330' },
  mts: { label: 'MT', color: '#3178C6' },
  cts: { label: 'CT', color: '#3178C6' },
  'd.ts': { label: 'DT', color: '#3178C6' },

  // Python
  py: { label: 'PY', color: '#3572A5' },
  pyi: { label: 'PI', color: '#3572A5' },
  pyx: { label: 'PX', color: '#3572A5' },
  pyw: { label: 'PW', color: '#3572A5' },
  ipynb: { label: 'NB', color: '#F37726' },

  // Web
  html: { label: '<>', color: '#E44D26' },
  htm: { label: '<>', color: '#E44D26' },
  css: { label: 'CSS', color: '#563D7C' },
  scss: { label: 'SC', color: '#CF649A' },
  sass: { label: 'SA', color: '#CF649A' },
  less: { label: 'LE', color: '#1D365D' },
  styl: { label: 'ST', color: '#FF6347' },
  vue: { label: 'VU', color: '#42B883' },
  svelte: { label: 'SV', color: '#FF3E00' },

  // Systems & compiled
  java: { label: 'JV', color: '#B07219' },
  cs: { label: 'C#', color: '#239120' },
  c: { label: 'C', color: '#555555' },
  h: { label: 'H', color: '#555555' },
  cpp: { label: '++', color: '#00599C' },
  cc: { label: '++', color: '#00599C' },
  cxx: { label: '++', color: '#00599C' },
  hpp: { label: 'H+', color: '#00599C' },
  hh: { label: 'H+', color: '#00599C' },
  m: { label: 'OC', color: '#438EFF' },
  mm: { label: 'O+', color: '#438EFF' },
  go: { label: 'GO', color: '#00ADD8' },
  rs: { label: 'RS', color: '#DEA584' },
  swift: { label: 'SW', color: '#FA7343' },
  kt: { label: 'KT', color: '#7F52FF' },
  kts: { label: 'KT', color: '#7F52FF' },
  dart: { label: 'DA', color: '#00B4AB' },
  scala: { label: 'SCA', color: '#DC322F' },
  sbt: { label: 'SB', color: '#DC322F' },

  // Scripting
  rb: { label: 'RB', color: '#CC342D' },
  php: { label: 'PHP', color: '#777BB4' },
  phtml: { label: 'PHP', color: '#777BB4' },
  pl: { label: 'PL', color: '#39457E' },
  pm: { label: 'PM', color: '#39457E' },
  lua: { label: 'LU', color: '#2C2D72' },
  r: { label: 'R', color: '#276DC3' },
  jl: { label: 'JL', color: '#9558B2' },
  ex: { label: 'EX', color: '#6E4A7E' },
  exs: { label: 'EX', color: '#6E4A7E' },
  erl: { label: 'ER', color: '#B83998' },
  hs: { label: 'HS', color: '#5E5086' },
  clj: { label: 'CLJ', color: '#63B132' },
  cljs: { label: 'CLJ', color: '#63B132' },
  fs: { label: 'F#', color: '#B845FC' },
  fsx: { label: 'F#', color: '#B845FC' },
  ml: { label: 'ML', color: '#EC6813' },
  mli: { label: 'ML', color: '#EC6813' },

  // Shell
  sh: { label: '$_', color: '#4EAA25' },
  bash: { label: '$_', color: '#4EAA25' },
  zsh: { label: '$_', color: '#4EAA25' },
  fish: { label: '$_', color: '#4EAA25' },
  ps1: { label: 'PS', color: '#012456' },
  psm1: { label: 'PS', color: '#012456' },
  bat: { label: 'BA', color: '#C1F12E', textColor: '#1E3A10' },
  cmd: { label: 'BA', color: '#C1F12E', textColor: '#1E3A10' },

  // Data & config
  json: { label: '{}', color: '#292929' },
  jsonc: { label: '{}', color: '#292929' },
  json5: { label: '{}', color: '#292929' },
  yaml: { label: 'YM', color: '#CB171E' },
  yml: { label: 'YM', color: '#CB171E' },
  toml: { label: 'TM', color: '#9C4121' },
  xml: { label: '</', color: '#E8710A' },
  xsl: { label: 'XS', color: '#E8710A' },
  xslt: { label: 'XS', color: '#E8710A' },
  csv: { label: 'CSV', color: '#237346' },
  tsv: { label: 'TSV', color: '#237346' },
  ini: { label: 'INI', color: '#6D8086' },
  cfg: { label: 'CFG', color: '#6D8086' },
  conf: { label: 'CNF', color: '#6D8086' },
  properties: { label: 'PRP', color: '#6D8086' },
  env: { label: 'ENV', color: '#ECD53F', textColor: '#2C3E17' },

  // Documentation
  md: { label: 'MD', color: '#083FA1' },
  mdx: { label: 'MDX', color: '#1B1F24' },
  rst: { label: 'RST', color: '#141414' },
  txt: { label: 'TXT', color: '#6D8086' },
  tex: { label: 'TEX', color: '#008080' },
  adoc: { label: 'ADC', color: '#E40046' },

  // Database
  sql: { label: 'SQL', color: '#E38C00' },

  // Infrastructure
  tf: { label: 'TF', color: '#7B42BC' },
  hcl: { label: 'HCL', color: '#7B42BC' },
  nix: { label: 'NIX', color: '#5277C3' },

  // API & schemas
  graphql: { label: 'GQ', color: '#E10098' },
  gql: { label: 'GQ', color: '#E10098' },
  proto: { label: 'PB', color: '#4285F4' },

  // Build & project files
  gradle: { label: 'GDL', color: '#02303A' },
  maven: { label: 'MV', color: '#C71A36' },
  cmake: { label: 'CM', color: '#064F8C' },

  // Assembly
  asm: { label: 'ASM', color: '#6E4C13' },
  s: { label: 'ASM', color: '#6E4C13' },
  wasm: { label: 'WA', color: '#654FF0' },
  wat: { label: 'WAT', color: '#654FF0' },

  // Other languages
  groovy: { label: 'GRV', color: '#4298B8' },
  pas: { label: 'PA', color: '#E3F171', textColor: '#2C3E17' },
  f90: { label: 'FN', color: '#4D41B1' },
  f95: { label: 'FN', color: '#4D41B1' },
  cob: { label: 'CO', color: '#3D5A80' },
  lisp: { label: 'LI', color: '#3FB68B' },
  el: { label: 'EL', color: '#7F5AB6' },
  scm: { label: 'SM', color: '#1E4AEC' },
  zig: { label: 'ZG', color: '#F7A41D', textColor: '#1B1B1B' },
  nim: { label: 'NM', color: '#FFE953', textColor: '#1B1B1B' },
  cr: { label: 'CR', color: '#000100' },
  v: { label: 'V', color: '#5D87BF' },
  d: { label: 'D', color: '#B03931' },
  ada: { label: 'ADA', color: '#02F88C', textColor: '#1B2B1B' },
  vhd: { label: 'VH', color: '#ADB2CB' },
  sv: { label: 'VL', color: '#B2B7F8' },

  // Images
  svg: { label: 'SVG', color: '#FFB13B', textColor: '#1B1B1B' },
  png: { label: 'PNG', color: '#A4C639', textColor: '#1B2B1B' },
  jpg: { label: 'JPG', color: '#E25D40' },
  jpeg: { label: 'JPG', color: '#E25D40' },
  gif: { label: 'GIF', color: '#00A98F' },
  webp: { label: 'WBP', color: '#4285F4' },
  ico: { label: 'ICO', color: '#1877F2' },
  bmp: { label: 'BMP', color: '#B07219' },

  // Fonts
  woff: { label: 'WF', color: '#EC6813' },
  woff2: { label: 'WF2', color: '#EC6813' },
  ttf: { label: 'TTF', color: '#EC6813' },
  otf: { label: 'OTF', color: '#EC6813' },
  eot: { label: 'EOT', color: '#EC6813' },

  // Audio & Video
  mp3: { label: 'MP3', color: '#8E44AD' },
  wav: { label: 'WAV', color: '#8E44AD' },
  ogg: { label: 'OGG', color: '#8E44AD' },
  mp4: { label: 'MP4', color: '#E74C3C' },
  webm: { label: 'WBM', color: '#E74C3C' },
  avi: { label: 'AVI', color: '#E74C3C' },

  // Archives
  zip: { label: 'ZIP', color: '#6D4C41' },
  tar: { label: 'TAR', color: '#6D4C41' },
  gz: { label: 'GZ', color: '#6D4C41' },
  bz2: { label: 'BZ2', color: '#6D4C41' },
  xz: { label: 'XZ', color: '#6D4C41' },
  '7z': { label: '7Z', color: '#6D4C41' },
  rar: { label: 'RAR', color: '#6D4C41' },

  // Documents
  pdf: { label: 'PDF', color: '#FF0000' },
  doc: { label: 'DOC', color: '#2B579A' },
  docx: { label: 'DOC', color: '#2B579A' },
  xls: { label: 'XLS', color: '#217346' },
  xlsx: { label: 'XLS', color: '#217346' },
  ppt: { label: 'PPT', color: '#B7472A' },
  pptx: { label: 'PPT', color: '#B7472A' },

  // Lock files
  lock: { label: 'LCK', color: '#6D8086' },

  // Log files
  log: { label: 'LOG', color: '#6D8086' },

  // Certificates & keys
  pem: { label: 'PEM', color: '#D4AF37' },
  crt: { label: 'CRT', color: '#D4AF37' },
  key: { label: 'KEY', color: '#D4AF37' },

  // Diff/Patch
  diff: { label: 'DIF', color: '#41B883' },
  patch: { label: 'PAT', color: '#41B883' },
}

/**
 * Exact filename to icon mapping (for special files like Dockerfile, Makefile, etc.)
 * Keys are lowercase.
 */
const FILENAME_ICONS: Record<string, FileIconConfig> = {
  dockerfile: { label: 'DK', color: '#2496ED' },
  'docker-compose.yml': { label: 'DC', color: '#2496ED' },
  'docker-compose.yaml': { label: 'DC', color: '#2496ED' },
  'compose.yml': { label: 'DC', color: '#2496ED' },
  'compose.yaml': { label: 'DC', color: '#2496ED' },
  makefile: { label: 'MK', color: '#427819' },
  cmakelists: { label: 'CM', color: '#064F8C' },
  'cmakelists.txt': { label: 'CM', color: '#064F8C' },
  rakefile: { label: 'RK', color: '#CC342D' },
  gemfile: { label: 'GM', color: '#CC342D' },
  procfile: { label: 'PC', color: '#6E4A7E' },
  vagrantfile: { label: 'VG', color: '#1868F2' },
  jenkinsfile: { label: 'JK', color: '#D24939' },
  '.gitignore': { label: 'GI', color: '#F05032' },
  '.gitattributes': { label: 'GA', color: '#F05032' },
  '.gitmodules': { label: 'GS', color: '#F05032' },
  '.editorconfig': { label: 'EC', color: '#FEFEFE', textColor: '#333333' },
  '.eslintrc': { label: 'ES', color: '#4B32C3' },
  '.eslintrc.js': { label: 'ES', color: '#4B32C3' },
  '.eslintrc.json': { label: 'ES', color: '#4B32C3' },
  'eslint.config.js': { label: 'ES', color: '#4B32C3' },
  'eslint.config.mjs': { label: 'ES', color: '#4B32C3' },
  '.prettierrc': { label: 'PR', color: '#56B3B4' },
  '.prettierrc.json': { label: 'PR', color: '#56B3B4' },
  'prettier.config.js': { label: 'PR', color: '#56B3B4' },
  '.babelrc': { label: 'BB', color: '#F9DC3E', textColor: '#323330' },
  'babel.config.js': { label: 'BB', color: '#F9DC3E', textColor: '#323330' },
  'tsconfig.json': { label: 'TS', color: '#3178C6' },
  'jsconfig.json': { label: 'JS', color: '#F0DB4F', textColor: '#323330' },
  'package.json': { label: 'NP', color: '#CB3837' },
  'package-lock.json': { label: 'NP', color: '#CB3837' },
  'yarn.lock': { label: 'YN', color: '#2C8EBB' },
  'pnpm-lock.yaml': { label: 'PN', color: '#F69220' },
  'bun.lockb': { label: 'BN', color: '#FBF0DF', textColor: '#1A1A1A' },
  'vite.config.ts': { label: 'VI', color: '#646CFF' },
  'vite.config.js': { label: 'VI', color: '#646CFF' },
  'webpack.config.js': { label: 'WP', color: '#8DD6F9', textColor: '#1A3A4A' },
  'rollup.config.js': { label: 'RL', color: '#EC4A3F' },
  'pyproject.toml': { label: 'PP', color: '#3572A5' },
  'setup.py': { label: 'SP', color: '#3572A5' },
  'setup.cfg': { label: 'SP', color: '#3572A5' },
  'requirements.txt': { label: 'RQ', color: '#3572A5' },
  pipfile: { label: 'PF', color: '#3572A5' },
  'poetry.lock': { label: 'PO', color: '#3572A5' },
  'cargo.toml': { label: 'CG', color: '#DEA584' },
  'cargo.lock': { label: 'CG', color: '#DEA584' },
  'go.mod': { label: 'GO', color: '#00ADD8' },
  'go.sum': { label: 'GO', color: '#00ADD8' },
  'composer.json': { label: 'CP', color: '#885630' },
  'composer.lock': { label: 'CP', color: '#885630' },
  'build.gradle': { label: 'GDL', color: '#02303A' },
  'pom.xml': { label: 'MV', color: '#C71A36' },
  license: { label: 'LIC', color: '#D4AF37' },
  'license.md': { label: 'LIC', color: '#D4AF37' },
  'license.txt': { label: 'LIC', color: '#D4AF37' },
  'readme.md': { label: 'RM', color: '#083FA1' },
  'readme.txt': { label: 'RM', color: '#083FA1' },
  'changelog.md': { label: 'CL', color: '#083FA1' },
  'contributing.md': { label: 'CT', color: '#083FA1' },
  '.dockerignore': { label: 'DI', color: '#2496ED' },
  '.npmignore': { label: 'NI', color: '#CB3837' },
  '.env': { label: 'ENV', color: '#ECD53F', textColor: '#2C3E17' },
  '.env.local': { label: 'ENV', color: '#ECD53F', textColor: '#2C3E17' },
  '.env.dev': { label: 'ENV', color: '#ECD53F', textColor: '#2C3E17' },
  '.env.prod': { label: 'ENV', color: '#ECD53F', textColor: '#2C3E17' },
  '.env.example': { label: 'ENV', color: '#ECD53F', textColor: '#2C3E17' },
  'nginx.conf': { label: 'NX', color: '#009639' },
  'alembic.ini': { label: 'AL', color: '#3572A5' },
  'pytest.ini': { label: 'PT', color: '#009FE3' },
  'conftest.py': { label: 'CF', color: '#009FE3' },
  'tox.ini': { label: 'TOX', color: '#009FE3' },
  '.flake8': { label: 'F8', color: '#3572A5' },
  'mypy.ini': { label: 'MY', color: '#2A6DB2' },
  'ruff.toml': { label: 'RF', color: '#D7FF64', textColor: '#1A2B0A' },
}

// ---------------------------------------------------------------------------
// Lookup logic
// ---------------------------------------------------------------------------

/**
 * Resolve icon config for a given filename and optional language.
 * Priority: exact filename match > language > extension > default.
 */
function getFileIconConfig(filename: string, language: string | null): FileIconConfig | null {
  const lowerName = filename.toLowerCase()

  // 1. Exact filename match
  const filenameConfig = FILENAME_ICONS[lowerName]
  if (filenameConfig) return filenameConfig

  // 2. Language match (from backend language detector)
  if (language) {
    const langConfig = LANGUAGE_ICONS[language.toLowerCase()]
    if (langConfig) return langConfig
  }

  // 3. Extension match (compound first, then simple)
  const dotIndex = lowerName.lastIndexOf('.')
  if (dotIndex !== -1) {
    // Try compound extension first (e.g., "d.ts") so it takes priority over "ts"
    const secondDot = lowerName.lastIndexOf('.', dotIndex - 1)
    if (secondDot !== -1) {
      const compoundExt = lowerName.slice(secondDot + 1)
      const compoundConfig = EXTENSION_ICONS[compoundExt]
      if (compoundConfig) return compoundConfig
    }

    // Fall back to simple extension (e.g., "ts")
    const ext = lowerName.slice(dotIndex + 1)
    const extConfig = EXTENSION_ICONS[ext]
    if (extConfig) return extConfig
  }

  // 4. No match — caller decides on fallback
  return null
}

/**
 * Renders a file type icon badge.
 * Shows a colored rounded rectangle with a short text label for known types.
 * Renders the fallback element for unknown file types.
 */
export function FileTypeIcon({
  filename,
  language,
  fallback,
  fontSize = 'small',
}: {
  filename: string
  language: string | null
  /** Element to render when the file type is not recognized */
  fallback?: ReactElement
  fontSize?: 'small' | 'inherit'
}): ReactElement {
  const config = getFileIconConfig(filename, language)

  if (!config) {
    return fallback ?? <></>
  }

  const size = fontSize === 'small' ? 18 : 20
  const textSize = fontSize === 'small' ? 8.5 : 9.5
  const labelLen = config.label.length

  return (
    <Box
      component="span"
      aria-hidden
      sx={{
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        width: labelLen > 2 ? size + 4 : size,
        height: size - 2,
        borderRadius: '3px',
        backgroundColor: config.color,
        color: config.textColor ?? '#FFFFFF',
        fontSize: labelLen > 2 ? textSize - 0.5 : textSize,
        fontWeight: 700,
        fontFamily: '"SF Mono", "Fira Code", "Cascadia Code", Consolas, monospace',
        lineHeight: 1,
        letterSpacing: '-0.02em',
        flexShrink: 0,
        userSelect: 'none',
      }}
    >
      {config.label}
    </Box>
  )
}
