# LLMind for Mac — Design Spec

**Date:** 2026-04-13  
**Status:** Approved  
**Project:** `/Users/dzmitrytryhubenka/APP DEV/LLMind`  
**Target directory:** `llmind-mac/`

---

## Overview

A native macOS app that provides Raycast-style semantic image search over LLMind-enriched files. A global hotkey summons a floating popup window where the user types a query, sees ranked results with thumbnails, and opens or reveals files — all without leaving the keyboard.

The app is backed by the existing `llmind-app` FastAPI companion server and `llmind-cli` search engine. The Swift layer handles only UI, hotkey, server lifecycle, and file watching.

---

## Design Decisions

| Decision | Choice | Rationale |
|---|---|---|
| App style | Raycast popup (NSPanel) | Instant, keyboard-driven, no persistent window chrome |
| Stack | SwiftUI + AppKit | Native performance, proper NSPanel/hotkey/blur support |
| Backend | FastAPI companion server | Fast after startup; reuses `llmind-app` already scaffolded |
| Search scope | `~/` recursive | Finds all `.llmind.*` files across Desktop, Photos, Documents, etc. |
| File watching | FSEventStream | Live index updates without polling |
| Badge style | Colored dot + abbreviation | Compact, readable, color-coded by type |
| Model selection | Clickable badge → dropdown | In-popup, no settings pane required for common case |

---

## UI

### Search Bar

Single-line input with four elements right-aligned:

```
⌕  [query text…]          ⚡ hybrid   • nomic   ESC
```

- **⌕** — static search icon, grey
- **Query input** — full-width, 17px, placeholder "Search images…"
- **Mode badge** — colored dot + label; click cycles through modes
  - `⚡ hybrid` — green dot
  - `〈v〉 vector` — blue dot  
  - `Aa keyword` — red dot (no Ollama needed)
- **Model badge** — colored dot + short provider/model name; click opens picker
  - `🦙 nomic` — indigo dot (Ollama)
  - `◆ 3-small` — blue dot (OpenAI)
  - `◈ voyage` — pink dot (Voyage AI)
- **ESC** — dim hint, dismisses popup

### Result Row

```
[44×44 thumb]  filename.llmind.png          0.385
               Description up to 80 chars…
```

- Thumbnail: 44×44, rounded 7px, lazy-loaded from `/api/thumbnail`
- Filename: 13px, truncated with ellipsis
- Description: 11px, dim, truncated
- Score: 12px, color-coded (cyan >0.35, grey >0.2, dim <0.2)
- Selected row: slightly lighter background + action hints appear on the right
  - `↵ Open`  `⌘↵ Reveal`  `⌘C Copy path`

### Footer

```
↑↓ navigate   ↵ open   ⌘↵ reveal   ⌘C copy       8 results · ~/ · hybrid
```

Dim keyboard hint bar. Right side shows result count, scope, and current mode.

### Model Picker Dropdown

Opens below the model badge on click. Grouped by provider:

```
OLLAMA (LOCAL)
  ● nomic-embed-text          ✓
OPENAI
  ● text-embedding-3-small    API key required
  ● text-embedding-3-large    API key required
VOYAGE AI
  ● voyage-3.5                API key required

⌘, to manage API keys
```

ESC or click outside closes the picker.

---

## Architecture

```
┌─────────────────────────────────┐
│       llmind-mac (Swift)        │
│                                 │
│  HotkeyManager  (CGEventTap)    │
│  MenuBarController (NSStatusItem│
│  SearchWindowController (NSPanel│
│  SearchViewModel (ObservableObj)│
│  ServerManager  (NSTask)        │
│  FileIndexManager (FSEventStream│
└──────────────┬──────────────────┘
               │ HTTP localhost:58421
┌──────────────▼──────────────────┐
│     llmind-app (FastAPI)        │
│                                 │
│  GET  /api/search               │
│  GET  /api/thumbnail            │
│  POST /api/reveal               │
│  GET  /api/scan                 │
└──────────────┬──────────────────┘
               │ imports
┌──────────────▼──────────────────┐
│     llmind-cli (Python)         │
│                                 │
│  embedder.py  (vectors)         │
│  reader.py    (XMP)             │
│  search_service.py              │
└─────────────────────────────────┘
```

### Swift Components

| Component | Responsibility |
|---|---|
| `HotkeyManager` | Register `⌘⇧Space` via `CGEventTap`; toggle window visibility |
| `MenuBarController` | `NSStatusItem` with ⬡ icon; menu: Show, Settings, Quit |
| `SearchWindowController` | `NSPanel` (non-activating, always on top, vibrancy blur); show/hide |
| `SearchViewModel` | Query state, 300ms debounce, REST search, result list, selection index |
| `ServerManager` | `NSTask` to start/stop FastAPI; health-check polling; restart on crash |
| `FileIndexManager` | `FSEventStream` on `~/`; maintains sorted list of `.llmind.*` paths |
| `SettingsView` | SwiftUI form: hotkey, API keys (Keychain), default provider/model |

### FastAPI Endpoints Used

| Endpoint | Purpose |
|---|---|
| `GET /api/search?q=…&dir=~&recursive=true&mode=…&provider=…&model=…&top=20` | Main search |
| `GET /api/thumbnail?path=…` | Lazy thumbnail load (JPEG, cached 1h) |
| `POST /api/reveal` `{"path": "…"}` | Reveal in Finder |
| `GET /api/scan?dir=~&recursive=true` | Initial file count on startup |

Port `58421` is fixed and reserved for LLMind.

### Server Startup

`ServerManager` locates the FastAPI server using a fixed relative path from the app bundle's resource directory. For v1 (development), it resolves the path as:

```
<repo-root>/llmind-app/.venv/bin/uvicorn  app.main:app  --port 58421  --no-access-log
```

The repo root is stored in `UserDefaults` on first launch (user picks it via folder picker if not found). In a future packaged release, the Python runtime and `llmind-app` would be bundled inside the `.app`.

---

## User Flow

1. **Launch** — App starts, menu bar icon ⬡ appears. `ServerManager` starts FastAPI on port 58421. `FileIndexManager` scans `~/` recursively (background thread). Index ready in 1–3s.
2. **Summon** — `⌘⇧Space` → `SearchWindowController` shows `NSPanel`, focuses text input.
3. **Type** — Keystroke triggers 300ms debounce timer. On fire: `SearchViewModel` calls `/api/search`.
4. **Results** — List renders. Thumbnails load lazily. First result auto-selected.
5. **Navigate** — `↑↓` moves selection. Selected row shows action hints.
6. **Act** — `↵` opens file in default app. `⌘↵` reveals folder in Finder. `⌘C` copies absolute path to clipboard.
7. **Dismiss** — `ESC` or click outside hides the panel. Server stays running.

---

## Search Behaviour

- **Default mode:** hybrid (vector + keyword, weight 0.6/0.4)
- **Ollama unavailable:** auto-fallback to keyword-only; mode badge turns red `Aa keyword`; no error shown
- **No results:** show "No matches" message with current scope and mode
- **Empty query:** show recent files (last 10 modified `.llmind.*` files) as suggestions
- **Debounce:** 300ms after last keystroke

---

## Settings (`⌘,`)

Minimal SwiftUI form accessible from menu bar:

- **Hotkey** — default `⌘⇧Space`, customizable via key recorder
- **Default provider/model** — persisted to `UserDefaults`
- **API keys** — OpenAI key, Voyage key; stored in Keychain
- **Search scope** — default `~/`, override with folder picker

---

## File Structure

```
llmind-mac/
├── LLMindMac.xcodeproj
└── LLMindMac/
    ├── App/
    │   ├── LLMindMacApp.swift       # @main, app lifecycle
    │   └── AppDelegate.swift        # NSApplication setup
    ├── Features/
    │   ├── Search/
    │   │   ├── SearchWindowController.swift
    │   │   ├── SearchView.swift
    │   │   ├── SearchViewModel.swift
    │   │   ├── ResultRow.swift
    │   │   └── ModelPickerView.swift
    │   └── Settings/
    │       └── SettingsView.swift
    ├── Services/
    │   ├── HotkeyManager.swift
    │   ├── MenuBarController.swift
    │   ├── ServerManager.swift
    │   └── FileIndexManager.swift
    ├── Network/
    │   └── LLMindAPI.swift          # URLSession wrappers
    └── Resources/
        └── Assets.xcassets
```

---

## Out of Scope (v1)

- Enriching new files from within the app (use CLI for that)
- Multi-window or full-window mode
- iOS / iPadOS version
- iCloud sync
- Spotlight plugin

---

## Success Criteria

- [ ] `⌘⇧Space` summons popup in < 50ms
- [ ] Search results appear within 500ms of last keystroke (Ollama running)
- [ ] Keyword fallback works instantly when Ollama is offline
- [ ] Thumbnails load for JPEG and PNG files
- [ ] `↵` opens file, `⌘↵` reveals in Finder, `⌘C` copies path
- [ ] Model picker shows all configured providers; selection persists across launches
- [ ] App survives FastAPI server crash (ServerManager auto-restarts)
- [ ] FSEventStream picks up newly enriched files without app restart
