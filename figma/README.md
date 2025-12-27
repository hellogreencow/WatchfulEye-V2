# WatchfulEye — Figma Handoff

This folder exists so you can pull the **frontend look** into Figma quickly, without needing a running backend.

## Option A (best): Import from a URL (HTML → Figma)

1. Build the static preview into `/docs`:

```bash
./scripts/export_figma_preview.sh
```

2. Push to GitHub and enable GitHub Pages from the `docs/` folder.
3. Use your preferred “HTML to Figma” plugin to import from the GitHub Pages URL.

## Option B: Import design tokens (Tokens Studio)

- Import:
  - `figma/tokens.light.json`
  - `figma/tokens.dark.json`

These are exported from the CSS variables in `frontend/src/index.css` (Shadcn-style HSL tokens).


