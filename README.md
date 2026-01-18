# Twiggy 🌿

Real-time directory structure for Cursor AI. Your AI always knows your codebase's structure.

## Why This Exists

The AI in Cursor only gets a high-level overview of your project:

```
apps/
  web/
    src/
      app/
      hooks/
      constants/
```

The AI can't see individual files, subdirectories, or what's actually inside those folders. It knows you have a `hooks/` directory but not what hooks exist.

Twiggy fixes this by generating a detailed, real-time directory tree that shows every file and folder. Now the AI can see:

- All your individual hook files
- Nested directory structures
- Every component, utility, and config file
- The complete picture of your codebase

## Install

```bash
pip install -e .
```

## Use

```bash
twiggy init              # setup in any project (interactive)
twiggy init --defaults   # setup with defaults (no questions)
twiggy watch             # start watching for changes
twiggy stats             # show index size + estimate
```

Creates `.cursor/rules/file-structure.mdc` that auto-updates when you add/remove files.

Ignores the usual stuff: `node_modules`, `__pycache__`, `.git`, `dist`, etc.

## Design Decisions

**Why track `twiggy.yml` but not the generated rule file?**

**The Problem:** If we tracked the generated `.cursor/rules/file-structure.mdc` file, it would claim to be "updated in real-time" even when you're not running Twiggy. This creates a lying, stale file that misleads the AI about the current structure.

**The Solution:**

- Track `twiggy.yml` (config) - tells the team "this project uses Twiggy"
- Don't track `.cursor/rules/file-structure.mdc` (generated output) - only exists when you're actively running the watcher
- If you see the rule file, you know it's actually real-time and trustworthy for your session
- If you don't see it, you haven't set up Twiggy yet (and the AI won't get false promises)

This way the rule file is either accurate or doesn't exist - never stale.
