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

## Packaged / Ready (Needs Credentials)

### AUR (Arch Linux)
**Status:** PKGBUILD ready, NOT published  
**Install after publish:** `yay -S prism32`  
**Package Dir:** `packages/aur/`  
**To publish:**
1. Register at https://aur.archlinux.org/
2. Add SSH key `~/.ssh/aur_prism32.pub` to your AUR account
3. ```bash
   cd packages/aur
   git init
   git remote add origin ssh://aur@aur.archlinux.org/prism32.git
   git add .
   git commit -m "prism32 6.9.0"
   git push origin main
   ```

### Chocolatey (Windows)
**Status:** .nuspec ready, NOT published  
**Install after publish:** `choco install prism32`  
**Package Dir:** `packages/chocolatey/`  
**To publish:**
```powershell
cd packages/chocolatey
choco pack
choco push prism32.6.9.0.nupkg --source https://push.chocolatey.org/ --api-key YOUR_KEY
```

### Snap (Ubuntu, Linux)
**Status:** snapcraft.yaml ready, NOT published  
**Install after publish:** `sudo snap install prism32`  
**Package Dir:** `packages/snap/`  
**To publish:**
```bash
cd packages/snap
snapcraft          # builds .snap
snapcraft login    # Ubuntu One account
snapcraft upload --release=stable prism32_6.9.0_amd64.snap
```

### pkgsrc (NetBSD, DragonFly, Illumos, etc.)
**Status:** Makefile ready, NOT submitted  
**Package Dir:** `packages/pkgsrc/`  
**To publish:** Submit to pkgsrc-wip or create a private pkgsrc tree.
**Note:** Tag `v6.9.0` exists on GitHub, so the tarball source URL works.

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
