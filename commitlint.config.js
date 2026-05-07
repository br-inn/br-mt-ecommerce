// =============================================================================
// commitlint configuration — Conventional Commits 1.0.0
// =============================================================================
// Used by:
//   - .github/workflows/pr-checks.yml (PR commit validation)
//   - .pre-commit-config.yaml (local commit-msg hook via commitizen)
// Reference: https://www.conventionalcommits.org/
// =============================================================================

/** @type {import('@commitlint/types').UserConfig} */
module.exports = {
  extends: ["@commitlint/config-conventional"],
  rules: {
    // Allowed types — keep aligned with pr-checks.yml semantic-pull-request job.
    "type-enum": [
      2,
      "always",
      [
        "feat",
        "fix",
        "docs",
        "style",
        "refactor",
        "perf",
        "test",
        "build",
        "ci",
        "chore",
        "revert",
      ],
    ],
    // Subject must not be empty and must not end with a period.
    "subject-empty": [2, "never"],
    "subject-full-stop": [2, "never", "."],
    // Header (type+scope+subject) length cap.
    "header-max-length": [2, "always", 100],
    // Body and footer wrap at 100 chars (warning only, not blocking).
    "body-max-line-length": [1, "always", 100],
    "footer-max-line-length": [1, "always", 100],
    // Scope is optional but lowercase if present.
    "scope-case": [2, "always", "lower-case"],
    "subject-case": [
      2,
      "never",
      ["sentence-case", "start-case", "pascal-case", "upper-case"],
    ],
  },
};
