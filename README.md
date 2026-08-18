# CuriousMD

CuriousMD is a local Markdown viewer and editor. It runs a small HTTP server on your machine and opens the interface in your browser. The application uses Python’s standard library and does not require a package install.

## Quick start

```sh
python3 mdview.py                # browse from the current directory
python3 mdview.py README.md      # open one file
python3 mdview.py docs/          # open Markdown files under a directory
```

The launch directory is the root of the built-in file browser. Stop the server with Ctrl+C in the terminal where it is running.

## Installation

### Linux

```sh
bash scripts/linux/install.sh
source ~/.bashrc
```

This adds an `md` shell alias, creates a desktop entry, and associates Markdown files when the required desktop tools are available. Run `bash scripts/linux/uninstall.sh` to remove it.

### macOS

```sh
bash scripts/macos/install.sh
```

This creates `~/Applications/CuriousMD.app` and adds the `md` alias to Bash and Zsh. Run `bash scripts/macos/uninstall.sh` to remove it.

### Windows

Run `scripts\windows\install.bat` from the project directory. `scripts\windows\uninstall.bat` removes the installed command and shortcuts. To create a standalone archive with embedded Python, run `scripts\windows\build-standalone.bat` first. The installer scripts are placed at the archive root in standalone builds.

Installers store the current project path. Re-run the installer after moving the project directory.

## Using the editor

- Select **Edit** to open the Markdown source and live preview side by side.
- Save with **Save** or Ctrl+S.
- Select **View** or press Escape to leave edit mode. Unsaved changes require confirmation.
- Search with Ctrl+F. In edit mode, results include both the Markdown source and the preview. Use Enter, Shift+Enter, F3, or the arrow buttons to move through matches.
- Ctrl+right-click text in the preview and choose **Navigate** to select its source location in the Markdown editor.
- Use the **Dark** or **Light** toolbar button to switch themes. The selection is stored in the browser; the first visit follows the operating-system preference.
- Select **Shortcuts** or press `?` outside an input to see the complete shortcut list.

## Markdown support

The renderer supports:

- ATX and Setext headings
- bold, italic, strikethrough, and inline code
- fenced code blocks
- links, autolinks, and images
- blockquotes
- ordered and unordered lists
- tables and cell alignment
- horizontal rules
- a limited set of safe HTML formatting tags

The layout adapts to narrow windows at 820 px.

## Project layout

```text
mdview.py                  HTTP routes and application entry point
domains/
  auth/session.py          Bootstrap token and session cookie
  docs/store.py            In-memory document store
  filesystem/browser.py    Restricted filesystem browser
  markdown/renderer.py     Markdown parser and HTML renderer
  ui/template.py           Page assembly
  ui/template.html         HTML shell
  ui/styles.css            Light and dark themes
  ui/app_logic.js          Search and source-navigation calculations
  ui/app.js                Browser, editor, search, and preview behavior
scripts/
  linux/                    Linux install and file-association scripts
  macos/                    macOS install and file-association scripts
  windows/                  Windows install and standalone-build scripts
  tests/                    Linux/macOS and Windows test runners
```

The page returned by `/` contains the UI CSS and JavaScript. Markdown documents may still load HTTP or HTTPS images referenced by their content.

## HTTP API

| Method | Path | Purpose |
|---|---|---|
| GET | `/` | Load the application using the startup token |
| GET | `/api/docs` | List open documents |
| GET | `/api/docs/<id>/html` | Render a document |
| GET | `/api/docs/<id>/raw` | Read source Markdown |
| PUT | `/api/docs/<id>/content` | Save an open document |
| DELETE | `/api/docs/<id>` | Close a document |
| GET | `/api/fs` | List a directory under the browser root |
| GET | `/api/open` | Open a Markdown file |
| POST | `/api/preview` | Render the live preview |

API requests require the session cookie issued when the startup URL is opened.

## Local access and content handling

CuriousMD binds to `127.0.0.1` by default. The startup URL contains a random token; after the page loads, API calls use an HttpOnly, SameSite=Strict session cookie. Keep the startup URL private. If you bind to another interface with `--host`, traffic is not encrypted and the server does not provide rate limiting.

The file browser resolves paths under its launch directory, rejects hidden path components and symlinks that lead outside that directory, accepts common Markdown extensions, and rejects files larger than 5 MB. Saving revalidates the same boundary and writes using the permissions of the running process.

Rendered content is handled in two stages:

- The Python renderer escapes text, restricts URL schemes, and filters attributes on supported passthrough HTML tags.
- The browser applies a tag and attribute allowlist before inserting preview HTML.

The main page also sets a nonce-based Content Security Policy. Local asset requests require the session cookie and serve only supported image formats. Remote Markdown images are limited to HTTP and HTTPS; scripts, frames, objects, and forms are blocked.

## Tests

```sh
bash scripts/tests/run.sh
npm test
```

The Python suite covers authentication, document storage, filesystem boundaries, Markdown rendering, HTML filtering, and page generation. The npm command uses Node’s built-in test runner and has no third-party dependencies.
