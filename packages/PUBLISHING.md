# Publishing Guide

## Published / Live

### PyPI (pip)
**Status:** LIVE  
**Install:** `pip install prism32`  
**URL:** https://pypi.org/project/prism32/6.9.0/  

### Homebrew (macOS, Linux)
**Status:** TAP LIVE  
**Install:**
```bash
brew tap MegaDyneSystems/prism32
brew install prism32
```
**Tap Repo:** https://github.com/MegaDyneSystems/homebrew-prism32

### Scoop (Windows)
**Status:** BUCKET LIVE  
**Install:**
```powershell
scoop bucket add prism32 https://github.com/MegaDyneSystems/scoop-prism32
scoop install prism32
```
**Bucket Repo:** https://github.com/MegaDyneSystems/scoop-prism32

---

### npm (Node.js, bun, deno)
**Status:** LIVE  
**Install:** `npm install -g @megadynesystems/prism32` or `npx @megadynesystems/prism32` or `bunx @megadynesystems/prism32`
**Note:** Published as `@megadynesystems/prism32` because unscoped `prism32` conflicts with existing packages (`prisma`, `prismjs`).

---

## Automated Publishing (GitHub Actions)

The `.github/workflows/publish.yml` workflow automatically handles:
- PyPI (uses trusted publishing — no token needed in secrets)
- npm (requires `NPM_TOKEN` secret)
- Homebrew tap update (requires `GH_PAT` secret)
- Scoop bucket update (requires `GH_PAT` secret)

Trigger: Push any `v*` tag to the main repo.

Required secrets:
- `NPM_TOKEN` — npm automation token
- `GH_PAT` — GitHub personal access token with `repo` scope for writing to tap/bucket repos
