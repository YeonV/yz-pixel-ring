import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Two builds from one codebase:
//   default ("pages")  -> standalone SPA in dist/        (served by the daemon)
//   --mode lib         -> IIFE in dist-lib/              (embeddable in JarvYZ)
export default defineConfig(({ mode }) => {
  if (mode === 'lib') {
    return {
      plugins: [react()],
      define: { 'process.env.NODE_ENV': '"production"', __YZPR_EMBEDDED__: 'true' },
      build: {
        outDir: 'dist-lib',
        emptyOutDir: true,
        lib: {
          entry: 'src/index.ts',
          name: 'YzPixelRing',
          formats: ['iife'],
          fileName: () => 'yz-pixel-ring.iife.js',
        },
        rollupOptions: {
          // React/react-dom are provided by the host (JarvYZ) as globals.
          external: ['react', 'react-dom', 'react-dom/client'],
          output: {
            extend: true,
            exports: 'named',
            globals: {
              react: 'React',
              'react-dom': 'ReactDOM',
              'react-dom/client': 'ReactDOM',
            },
            // The IIFE has no module system; shim the CJS require() that some
            // deps emit for the externalized react packages.
            banner:
              'var require=function(id){if(id==="react")return window.React;' +
              'if(id==="react-dom"||id==="react-dom/client")return window.ReactDOM;' +
              'throw new Error("require not handled: "+id)};',
          },
        },
      },
    }
  }

  // Standalone SPA — built INTO the Python package (yz_pixel_ring/_ui) so the
  // daemon serves it from there in every form: source run, wheel, frozen exe.
  return {
    plugins: [react()],
    define: { __YZPR_EMBEDDED__: 'false' },
    server: { port: 9701 },
    build: { outDir: '../yz_pixel_ring/_ui', emptyOutDir: true },
  }
})
