# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [3.0.1] - 2026-07-01

### Added

- `timeout` parameter to `listen()`, allowing callers to bound how long TJBot will listen for speech.
- Support for the `silly` logging level, to match parity with `node-tjbotlib`.

### Changed

- `TJBot.speak()` internally replaces "tjbot" with "t j bot" so TTS backends pronounce it correctly.

## [3.0.0] - 2026-06-11

### Added

- Initial release of `tjbot-ce`, the Python library for writing TJBot recipes.

[Unreleased]: https://github.com/tjbot-ce/python-tjbotlib/compare/v3.0.1...HEAD
[3.0.1]: https://github.com/tjbot-ce/python-tjbotlib/compare/v3.0.0...v3.0.1
[3.0.0]: https://github.com/tjbot-ce/python-tjbotlib/releases/tag/v3.0.0
