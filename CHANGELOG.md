# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed
- **CI: Backend tests silent failure** - Fixed pytest exit code handling in `.github/workflows/test.yml`
  - Previously used `|| echo` which swallowed test failures (exit code 0 regardless of test results)
  - Now properly handles pytest exit codes: 0=pass, 5=no tests (acceptable), other=fail CI
  - This ensures test regressions will correctly fail the CI pipeline

### Changed
- **Code Review**: Comprehensive code review of human-lncrna-atlas project
  - Reviewing Phase 8.2 and recent commits for code quality issues
  - Identifying potential bugs, security vulnerabilities, and improvements
