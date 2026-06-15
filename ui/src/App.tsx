import { ThemeProvider, CssBaseline } from '@mui/material'
import { defaultTheme } from './theme'
import { PixelRingPage } from './PixelRingPage'
import { createPixelRingApi } from './lib/api'

// Standalone: in dev hit the daemon on :9700; in prod the daemon serves this
// SPA same-origin, so apiBase is ''.
const apiBase = import.meta.env.DEV ? 'http://127.0.0.1:9700' : ''
const api = createPixelRingApi({ apiBase })

export default function App() {
  return (
    <ThemeProvider theme={defaultTheme}>
      <CssBaseline />
      <PixelRingPage api={api} capabilities={{ apiBase }} />
    </ThemeProvider>
  )
}
