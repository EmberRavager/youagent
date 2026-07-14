# YouAgent Guard macOS App

This SwiftUI menu-bar app wraps the current Python monitoring engine.

## Requirements

- macOS 13 or later
- Xcode Command Line Tools / Swift 5.9 or later
- The YouAgent Python package installed in an environment visible from the app:

```bash
cd /path/to/youagent
python3 -m pip install -e .
```

Confirm the engine is available:

```bash
which youagent-guard
youagent-guard --help
```

## Build the app

```bash
cd macos
chmod +x build_app.sh
./build_app.sh
open "dist/YouAgent Guard.app"
```

The shield icon appears in the macOS menu bar. The panel supports:

- Start and stop protection
- Switch between alert-only and emergency termination
- View recent risk events
- Open the local audit log

## Current boundary

The app starts and supervises the process-monitoring MVP. It is not code-signed, notarized, or distributed as a DMG. It does not install a privileged helper or Endpoint Security system extension, so it cannot guarantee pre-execution blocking or observe every file access.

A production version should move process/file authorization to a signed Endpoint Security system extension and use XPC for communication with this UI.
