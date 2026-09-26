# Repository bootstrap evidence

M0 owner: Josh Myers. Verified 2026-09-25 with local Git, GitHub Actions, and
authenticated GitHub API calls. The repository was generated from the pinned
template as `signal-grid`, then renamed to `griddy` at the owner's request.
Repository files alone do not prove server-side settings.

| Control | Verified result |
|---|---|
| Template provenance | `python-data-quant` starter from `joshuamyers22/production-project-template` at `efd1e9cb0defeb3442d3a2d10ea874524664173d`. |
| Identity and signing | `main` uses repository-local author name and a verified primary email on `joshuamyers22`. The owner's SSH signing key is registered with GitHub. Commit `d051c8f` has GitHub verification `valid`. |
| Owner and visibility | Public `joshuamyers22/griddy`, default branch `main`, administrator access; `origin`, manifest URLs, and CODEOWNERS match. It is an ordinary project, not a reusable template. |
| Quality and packaging | `make check` passed Ruff, Pyright, and 34 tests; `make audit build` found no known vulnerabilities, passed the license policy, and built the `griddy` source distribution and wheel. |
| CI and portable secret scan | The renamed commit passed GitHub Actions jobs `quality` and `gitleaks` (runs `36207943521` and `36207943607`). The initial bootstrap commit also passed both jobs. |
| Branch ruleset | Active `Protect main` ruleset `24027427` requires pull requests, passing `quality` and `gitleaks`, up-to-date checks, resolved review threads, signed commits, and linear history; it blocks deletion and force pushes. No bypass actors are configured. |
| Merge and review | `main` is the default branch; squash is the only merge method and merged branches are deleted. The solo-owner exception is zero required approvals and no CODEOWNERS approval. Stale approvals are dismissed if a second reviewer later becomes available. |
| Actions permissions | Default token is read-only and cannot approve pull requests. Only GitHub-owned Actions and four explicitly approved third-party action SHAs are allowed; full SHA pins are required. |
| GitHub security | Dependency vulnerability alerts, automated security fixes, native secret scanning, push protection, and private vulnerability reporting are enabled. CodeQL default setup for Python and Actions is configured; its first validation run `36208440261` passed. The history-aware `gitleaks` job remains in CI. |

When an eligible reviewer other than the author joins, set the ruleset to require
at least one approval and CODEOWNERS review. Until then, the maintainer must
inspect every pull request's diff, `quality` and `gitleaks` results, and review
threads before squash merge. This is a manual review procedure; the ruleset
enforces the other listed conditions.
