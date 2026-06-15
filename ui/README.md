# yz-pixel-ring — Web UI

[![creator](https://img.shields.io/badge/CREATOR-Yeon-blue.svg?logo=github&logoColor=white)](https://github.com/YeonV) [![creator](https://img.shields.io/badge/A.K.A-Blade-darkred.svg?logo=github&logoColor=white)](https://github.com/YeonV)

[![React](https://img.shields.io/badge/React-blue.svg?logo=react&logoColor=white)](https://react.dev/)
[![MUI](https://img.shields.io/badge/MUI-blue.svg?logo=mui&logoColor=white)](https://mui.com/)
[![TypeScript](https://img.shields.io/badge/TypeScript-blue.svg?logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![Vite](https://img.shields.io/badge/Vite-blue.svg?logo=vite&logoColor=white)](https://vite.dev/)
[![License](https://img.shields.io/badge/License-MIT-green.svg?logo=opensourceinitiative&logoColor=white)](../LICENSE)

Control UI for the [pixel-ring daemon](../README.md). A Vite + React + MUI app that
talks to the daemon's REST + WebSocket API.

## Build modes

One codebase, two outputs:

- **Standalone SPA** — `npm run build:pages` → `dist/`. The daemon serves it at
  `http://127.0.0.1:9700`.
- **IIFE** — `npm run build:lib` → `dist-lib/yz-pixel-ring.iife.js`. Embeddable in a host
  frontend; attaches `window.YzPixelRing` exposing `PixelRingPage` + `createPixelRingApi`,
  with React externalized.

## Dev

```bash
npm install
npm run dev          # Vite on :9701, talks to the daemon on :9700 via CORS
npm run typecheck    # tsc --noEmit
npm run build        # typecheck + both builds
```

In dev, `App.tsx` points the API at `http://127.0.0.1:9700`; in the daemon-served SPA the
API base is same-origin (`''`).

## How it talks to the daemon

- `lib/api.ts` — `createPixelRingApi({ apiBase })`, the REST client.
- `lib/useRingStream.ts` — WebSocket `/ws` client → live ~20 fps frame + state (drives the
  ring preview, DOA needle, and live readouts without polling).
- The component takes `theme` / `wsApi` / `capabilities` props so it works both standalone
  and embedded in a host frontend.

## Structure

```
src/
  PixelRingPage.tsx     root component (Live radar + Mode animations)
  App.tsx               standalone wrapper
  index.ts              IIFE entry (window.YzPixelRing)
  lib/                  api client, ws stream, colour utils
  components/           RingPreview, SpecEditor, control panels, TuningPanel
  types.ts, theme.ts
```
