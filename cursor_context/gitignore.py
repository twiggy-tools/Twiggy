from pathlib import Path


def ensure_gitignore_entry(project_root):
    """Add Twiggy rule files to .gitignore if not already present"""
    gitignore_path = project_root / '.gitignore'
    entries = [
        '.cursor/rules/file-structure.mdc',
        '.cursor/rules/codebase-index.mdc',
    ]

    if gitignore_path.exists():
        for entry in entries:
            if not _entry_exists(gitignore_path, entry):
                _append_entry(gitignore_path, entry)
    else:
        _create_gitignore_with_entries(gitignore_path, entries)


def _entry_exists(gitignore_path, entry):
    with open(gitignore_path, 'r', encoding='utf-8') as f:
        return entry in f.read()


def _append_entry(gitignore_path, entry):
    with open(gitignore_path, 'a', encoding='utf-8') as f:
        f.write(f'\n# Twiggy\n{entry}\n')


def _create_gitignore_with_entries(gitignore_path, entries):
    with open(gitignore_path, 'w', encoding='utf-8') as f:
        f.write('# Twiggy\n')
        for entry in entries:
            f.write(f'{entry}\n')
