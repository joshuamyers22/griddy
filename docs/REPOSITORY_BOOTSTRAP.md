# Repository bootstrap evidence

This record tracks the M0 setup checklist without treating repository files as
proof of GitHub settings. Owner: Josh Myers. Started 2026-09-25.

| Control | Evidence or next check | Status |
|---|---|---|
| Template provenance | Generated from `joshuamyers22/production-project-template` at `efd1e9cb0defeb3442d3a2d10ea874524664173d`, `python-data-quant`. | Verified locally |
| Git identity | `main` initialized; author name and email come from this repository's `.git/config`. GitHub's email API reports the configured address is verified and primary on `joshuamyers22`. | Verified |
| Commit signing | SSH signing is configured to use the owner's existing local key. Verify the signed initial commit and GitHub's verification status. | Local configured |
| Repository owner, visibility, and origin | GitHub reports private `joshuamyers22/griddy` with administrator access; `origin` uses that canonical HTTPS URL. | Verified |
| Project metadata and CODEOWNERS | `.github/CODEOWNERS` names `@joshuamyers22`; project URLs point to the canonical repository. | Verified locally |
| Local quality gate | `make check`: Ruff, Pyright strict, and 34 unit tests passed. `make audit build`: vulnerability query, license policy, source distribution, and wheel passed. | Passed locally |
| First CI and secret scan | Push the signed initial commit, then inspect `quality` and `gitleaks` jobs. | Pending first push |
| Branch, merge, Actions, and security controls | Configure after first CI names exist; verify settings with authenticated `gh api`. Record any unavailable controls and solo-owner exception here. | Pending first CI |
