import click
from pathlib import Path
from .scanner import DirectoryScanner
from .watcher import FileWatcher
from .config import Config
from .gitignore import ensure_gitignore_entry
from .defaults import (
    DEFAULT_SYNC_GITIGNORE, DEFAULT_FORMAT,
    DEFAULT_INDEXING_ENABLED, DEFAULT_INDEXING_INCLUDE, DEFAULT_INDEXING_EXCLUDE
)
from colorama import init, Fore, Style

init()

@click.group()
def main():
    """Twiggy - Generate real-time directory structure and codebase index for Cursor AI"""
    pass

@main.command()
@click.option('--defaults', is_flag=True, help='Use default settings without prompts')
def init(defaults):
    """Initialize Twiggy in the current directory"""
    current_dir = Path.cwd()

    click.echo(f"{Fore.GREEN}Welcome to Twiggy! Initializing in: {current_dir}{Style.RESET_ALL}")

    _setup_cursor_directory(current_dir)
    ensure_gitignore_entry(current_dir)

    config = Config(current_dir)

    if not config.exists() or click.confirm(f"{Fore.YELLOW}Config already exists. Reconfigure?{Style.RESET_ALL}"):
        if defaults:
            _create_default_config(config)
        else:
            _configure_settings(config)

    click.echo(f"{Fore.GREEN}Configuration saved! Run 'twiggy run' to start monitoring.{Style.RESET_ALL}")

@main.command()
def run():
    """Start Twiggy - generates structure & index, then watches for changes"""
    config = _get_validated_config()
    if not config:
        return

    _start_file_watcher(config)

@main.command()
def stats():
    """Show codebase indexing size and time estimate"""
    config = _get_validated_config()
    if not config:
        return

    from .indexer import CodebaseIndexer

    indexer = CodebaseIndexer(config)
    files = indexer.get_indexable_files()
    indexing_config = config.get_indexing_config()

    click.echo(f"Indexable files: {len(files)}")
    click.echo(f"Include patterns: {indexing_config.get('include') or []}")
    click.echo(f"Exclude patterns: {indexing_config.get('exclude') or []}")

    total_bytes = 0
    size_entries = []
    for file_path in files:
        try:
            size = file_path.stat().st_size
        except OSError:
            continue
        total_bytes += size
        size_entries.append((size, file_path))

    click.echo(f"Total size: {_format_bytes(total_bytes)}")

    estimate_bytes_per_sec = indexing_config.get("estimateBytesPerSec")
    if estimate_bytes_per_sec and estimate_bytes_per_sec > 0:
        estimate_seconds = total_bytes / estimate_bytes_per_sec
        click.echo(
            f"Estimated parse time: {estimate_seconds:.1f}s "
            f"(assumes {_format_bytes(estimate_bytes_per_sec)}/s)"
        )

    if size_entries:
        click.echo("Largest files:")
        for size, file_path in sorted(size_entries, reverse=True)[:10]:
            click.echo(
                f"  {_format_bytes(size)}  {_safe_relative_path(file_path, config.project_root)}"
            )


def _setup_cursor_directory(project_root):
    rules_dir = project_root / '.cursor' / 'rules'
    rules_dir.mkdir(parents=True, exist_ok=True)


def _get_validated_config():
    config = Config(Path.cwd())
    if not config.exists():
        click.echo(f"{Fore.RED}No config found. Run 'twiggy init' first.{Style.RESET_ALL}")
        return None
    return config


def _format_bytes(value: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(value)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(size)} {unit}"
            return f"{size:.2f} {unit}"
        size /= 1024


def _safe_relative_path(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _generate_initial_outputs(config):
    """Generate both file structure and codebase index"""
    scanner = DirectoryScanner(config)
    scanner.scan_and_generate()
    click.echo(f"{Fore.GREEN}Directory structure generated!{Style.RESET_ALL}")

    indexing_config = config.get_indexing_config()
    if indexing_config['enabled']:
        from .indexer import CodebaseIndexer
        indexer = CodebaseIndexer(config)
        indexer.index_and_generate()
        click.echo(f"{Fore.GREEN}Codebase index generated!{Style.RESET_ALL}")


def _configure_settings(config):
    """Configure all Twiggy settings including indexing"""
    click.echo(f"\n{Fore.YELLOW}Setting up Twiggy{Style.RESET_ALL}")

    structure_exclude = _collect_structure_excludes()
    sync_gitignore = _ask_gitignore_sync()
    format_type = _ask_output_format()

    # Indexing configuration
    indexing_enabled = _ask_indexing_enabled()
    indexing_include = []
    indexing_exclude = []

    if indexing_enabled:
        indexing_exclude = _ask_indexing_excludes()

    config.create_default_config(
        structure_exclude,
        sync_gitignore,
        format_type,
        indexing_enabled,
        indexing_include,
        indexing_exclude
    )

    click.echo(f"\n{Fore.GREEN}Created twiggy.yml - you can edit this file later!{Style.RESET_ALL}")
    if structure_exclude:
        _display_added_excludes(structure_exclude)


def _collect_structure_excludes():
    excludes = []

    click.echo(f"\n{Fore.CYAN}File Structure - Custom exclusions{Style.RESET_ALL}")
    click.echo(f"{Fore.GREEN}Exclude folders/files from the directory structure output.{Style.RESET_ALL}")
    click.echo(f"{Fore.YELLOW}Examples: 'temp', 'src/old-stuff', 'docs/legacy/backup'{Style.RESET_ALL}")
    click.echo(f"{Fore.GREEN}Note: Common defaults (node_modules, .git, etc.) are already excluded{Style.RESET_ALL}")
    click.echo(f"{Fore.YELLOW}Just press Enter when done{Style.RESET_ALL}")

    while True:
        folder = click.prompt(f"{Fore.MAGENTA}Folder/file to exclude", default="", show_default=False).strip()
        if not folder:
            break

        if folder not in excludes:
            excludes.append(folder)
            click.echo(f"  {Fore.GREEN}Added: {folder}{Style.RESET_ALL}")
        else:
            click.echo(f"  {Fore.YELLOW}Already added: {folder}{Style.RESET_ALL}")

    return excludes


def _ask_gitignore_sync():
    click.echo(f"\n{Fore.CYAN}Sync with .gitignore - automatically ignore anything in your .gitignore{Style.RESET_ALL}")
    click.echo(f"{Fore.GREEN}This keeps your ignore list in sync (you can change this later){Style.RESET_ALL}")
    return click.confirm(f"{Fore.CYAN}Enable .gitignore sync?{Style.RESET_ALL}", default=True)


def _ask_output_format():
    click.echo(f"\n{Fore.CYAN}Output format for directory structure:{Style.RESET_ALL}")
    click.echo(f"{Fore.YELLOW}xml: XML structure (better for LLMs){Style.RESET_ALL}")
    click.echo(f"{Fore.YELLOW}tree: Visual tree with special characters (human-readable){Style.RESET_ALL}")
    return click.prompt(f"{Fore.CYAN}Choose format", type=click.Choice(['xml', 'tree']), default='xml')


def _ask_indexing_enabled():
    """Ask user if they want indexing enabled"""
    click.echo(f"\n{Fore.CYAN}Codebase Indexing{Style.RESET_ALL}")
    click.echo(f"{Fore.GREEN}Extracts function signatures, types, interfaces, and exports from your code.{Style.RESET_ALL}")
    click.echo(f"{Fore.GREEN}This helps AI understand what utilities and types exist in your codebase.{Style.RESET_ALL}")
    return click.confirm(f"{Fore.CYAN}Enable codebase indexing?{Style.RESET_ALL}", default=True)


def _ask_indexing_excludes():
    """Ask user for additional indexing excludes"""
    click.echo(f"\n{Fore.GREEN}By default, test files, config files, and build outputs are excluded from indexing.{Style.RESET_ALL}")
    click.echo(f"{Fore.GREEN}You can add more exclusion patterns in twiggy.yml later.{Style.RESET_ALL}")
    return DEFAULT_INDEXING_EXCLUDE


def _create_default_config(config):
    config.create_default_config(
        [],  # structure_exclude - empty by default
        DEFAULT_SYNC_GITIGNORE,
        DEFAULT_FORMAT,
        DEFAULT_INDEXING_ENABLED,
        DEFAULT_INDEXING_INCLUDE,
        DEFAULT_INDEXING_EXCLUDE
    )
    click.echo(f"\n{Fore.GREEN}Created twiggy.yml with defaults - you can edit this file later!{Style.RESET_ALL}")


def _display_added_excludes(excludes):
    click.echo(f"{Fore.CYAN}Structure exclusions added:{Style.RESET_ALL}")
    for exclude in excludes:
        click.echo(f"  - {exclude}")


def _start_file_watcher(config):
    try:
        watcher = FileWatcher(config)
        click.echo(f"{Fore.GREEN}Watching for changes... (Press Ctrl+C to stop){Style.RESET_ALL}")
        watcher.start()
    except KeyboardInterrupt:
        click.echo(f"\n{Fore.YELLOW}Stopped watching{Style.RESET_ALL}")
    except Exception as e:
        click.echo(f"{Fore.RED}Error: {e}{Style.RESET_ALL}")

if __name__ == '__main__':
    main()
