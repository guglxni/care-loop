# Care Loop web

Patient app shell. The chart in `src/data/demo.ts` is synthetic demo data. It is not medical advice and it is not a clinical recommendation.

## Run

From this directory:

```bash
npm install
npm run dev
```

Vite prints a local URL, usually http://localhost:5173.

`src/data/demo.ts` is the only mock source. Its clock is fixed at 15 November 2026 (`todayIso`), so the screens do not follow the computer's date. `AppShell` mounts the page modules under `src/pages` and redirects unknown paths to `/`. The shell already pads the page region.
