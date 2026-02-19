# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [2.1.1] - 2026-02-18

### Added

- Hardware connectivity test to validate laser discovery, connect, and disconnect workflows.

### Fixed

- Resolve connection issues that occurred when an Arduino device was plugged in simultaneously with the IPS laser.
- Ensure VISA/serial resources opened during `find_ips_laser()` probing are always closed, even when a probe fails.
- Prevent serial ports from remaining locked or appearing "busy" after failed or partial discovery attempts.

### Changed

- Improve `find_ips_laser()` logging to provide clearer diagnostics when probing multiple serial devices.
- Speed up laser discovery by narrowing candidate ports using stable device identifiers under `/dev/serial/by-id`, avoiding probes of unrelated serial devices.
