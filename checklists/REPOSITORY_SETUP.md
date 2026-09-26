# Repository Setup

Completed for `joshuamyers22/griddy` on 2026-09-25. The template-repository
item is checked as not applicable, and the reviewer item uses the solo-owner
exception documented in [bootstrap evidence](../docs/REPOSITORY_BOOTSTRAP.md).

Complete this checklist for every new project or repository before the first
commit or push. Git author identity, GitHub authentication, and repository
ownership are separate controls; verify all three.

## Git author identity

- [x] Initialize Git when needed with `git init`.
- [x] Configure the author in this repository rather than relying only on global
      defaults:

  ```sh
  git config --local user.name "YOUR NAME"
  git config --local user.email "YOUR VERIFIED OR GITHUB NOREPLY EMAIL"
  ```

- [x] Verify both local values and their source:

  ```sh
  git config --local --get user.name
  git config --local --get user.email
  git config --show-origin --get user.name
  git config --show-origin --get user.email
  ```

  The `--show-origin` results must resolve to this repository's `.git/config`.
  Use an email associated with the intended GitHub account so GitHub can
  attribute commits correctly.

## GitHub account and repository

- [x] Confirm the intended account is authenticated. If more than one account is
      available, select the correct one before creating or connecting the
      repository:

  ```sh
  gh auth status
  gh auth switch --user GITHUB_ACCOUNT
  gh auth setup-git
  ```

- [x] Create the GitHub repository under that account or an explicitly approved
      organization, or connect the existing repository as `origin`. Choose
      visibility deliberately; private is the safe default for new work:

  ```sh
  gh repo create OWNER/REPOSITORY --source=. --remote=origin --private
  ```

  For an existing GitHub repository, add its SSH or HTTPS URL with
  `git remote add origin URL`. Do not replace an existing remote until its owner
  and purpose have been verified.

- [x] Verify that the authenticated account can access the same canonical
      repository named by `origin`:

  ```sh
  git remote get-url origin
  gh repo view OWNER/REPOSITORY --json nameWithOwner,url,viewerPermission
  ```

- [x] Use the same canonical `OWNER/REPOSITORY` in the project manifest and all
      repository, issue-tracker, changelog, and documentation URLs.
- [x] Confirm `.github/CODEOWNERS` names the intended account or team.
- [x] Keep tokens, keys, cookies, and credential-helper output out of the
      repository and its documentation.

## GitHub repository controls

Configure these controls in GitHub after the first CI and secret-scanning runs,
so the required check names can be selected. Repository files describe the
policy; a branch rule or ruleset is what enforces it.

- [x] If this repository is intended to be cloned through GitHub as a reusable
      template, enable **Template repository**. Do not enable it for an ordinary
      project merely because it was generated from a template.

  `griddy` is an ordinary project; this conditional control is not applicable.
- [x] Keep `main` as the default branch, automatically delete merged branches,
      and enable only the approved merge method. Squash merge is the default;
      preserve another method only when the project has a documented history
      requirement.
- [x] Create a branch ruleset for `main` that requires pull requests, successful
      `quality` and `gitleaks` checks (or the project's equivalent job names),
      resolved review conversations, and an up-to-date branch before merge.
- [x] Require at least one approval, dismiss stale approvals, and require
      CODEOWNERS review when an eligible reviewer other than the author exists.
      A solo repository must not install an impossible self-approval gate; record
      the exception and add the review requirement when another owner joins.

  The solo-owner exception is active: zero required approvals and no CODEOWNERS
  approval until an eligible reviewer joins.
- [x] Block force pushes and branch deletion. Restrict bypass permission and
      enforce the rule for administrators unless a documented emergency path
      requires a narrowly scoped exception.
- [x] Require signed commits on protected branches. Configure and verify a
      signing key before making this blocking; Git author email configuration is
      attribution and does not prove a signature.
- [x] Set the default Actions token to read-only and prevent Actions from
      approving pull requests. Grant additional permissions only on the job that
      needs them.
- [x] Allow only GitHub-owned and explicitly approved third-party Actions, and
      require full commit-SHA pins. Keep Dependabot enabled for Actions updates.
- [x] Enable dependency-graph vulnerability alerts and automated security fixes.
      Enable GitHub secret scanning, push protection, code scanning, and private
      vulnerability reporting where the repository visibility and account plan
      support them; retain the repository's history-aware secret-scanning job as
      a portable baseline.
- [x] Review the settings from a second authenticated session or with `gh api`.
      Save only the setting names and result in project evidence—never tokens,
      credential output, or unrestricted API responses.

If the account plan cannot enforce a required control, record the exact gap,
owner, compensating procedure, and re-review trigger. A documented manual rule
must not be described as branch protection.
