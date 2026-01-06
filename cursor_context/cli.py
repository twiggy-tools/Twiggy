import click
from pathlib import Path
from .scanner import DirectoryScanner
from .watcher import FileWatcher
from .config import Config
from .gitignore import ensure_gitignore_entry
from .defaults import (
    DEFAULT_SYNC_GITIGNORE, DEFAULT_FORMAT, DEFAULT_CUSTOM_IGNORES,
    DEFAULT_INDEXING_ENABLED, DEFAULT_INDEXING_INCLUDE, DEFAULT_INDEXING_EXCLUDE
)
from colorama import init, Fore, Style

init()

@click.group()
def main():
    """Twiggy - Generate real-time directory structure and codebase index for Cursor AI"""
    pass

@main.command()
@click.option('--config-only', is_flag=True, help='Only create config without scanning')
@click.option('--defaults', is_flag=True, help='Use default settings without prompts')
def init(config_only, defaults):
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

    if config_only:
        click.echo(f"{Fore.GREEN}Configuration saved! Run 'twiggy run' to start monitoring.{Style.RESET_ALL}")
        return

    _generate_initial_outputs(config)

    if click.confirm(f"{Fore.CYAN}Start watching for changes?{Style.RESET_ALL}"):
        _start_file_watcher(config)

@main.command()
def run():
    """Start Twiggy - generates structure & index, then watches for changes"""
    config = _get_validated_config()
    if not config:
        return

    _start_file_watcher(config)


def _setup_cursor_directory(project_root):
    rules_dir = project_root / '.cursor' / 'rules'
    rules_dir.mkdir(parents=True, exist_ok=True)


def _get_validated_config():
    config = Config(Path.cwd())
    if not config.exists():
        click.echo(f"{Fore.RED}No config found. Run 'twiggy init' first.{Style.RESET_ALL}")
        return None
    return config


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

    custom_ignores = _collect_custom_ignores()
    sync_gitignore = _ask_gitignore_sync()
    format_type = _ask_output_format()

    # Indexing configuration
    indexing_enabled = _ask_indexing_enabled()
    indexing_include = []
    indexing_exclude = []

    if indexing_enabled:
        indexing_exclude = _ask_indexing_excludes()

    config.create_default_config(
        custom_ignores,
        sync_gitignore,
        format_type,
        indexing_enabled,
        indexing_include,
        indexing_exclude
    )

    click.echo(f"\n{Fore.GREEN}Created twiggy.yml - you can edit this file later!{Style.RESET_ALL}")
    if custom_ignores:
        _display_added_ignores(custom_ignores)


def _collect_custom_ignores():
    custom_ignores = []

    click.echo(f"\n{Fore.CYAN}Add custom folders to ignore (beyond the common defaults):{Style.RESET_ALL}")
    click.echo(f"{Fore.YELLOW}Examples: 'temp', 'src/old-stuff', 'docs/legacy/backup'{Style.RESET_ALL}")
    click.echo(f"{Fore.GREEN}Note: We'll ask about .gitignore sync next, so don't add those manually{Style.RESET_ALL}")
    click.echo(f"{Fore.GREEN}You can skip this and edit twiggy.yml later{Style.RESET_ALL}")
    click.echo(f"{Fore.YELLOW}Just press Enter when done{Style.RESET_ALL}")

    while True:
        folder = click.prompt(f"{Fore.MAGENTA}Folder name", default="", show_default=False).strip()
        if not folder:
            break

        if folder not in custom_ignores:
            custom_ignores.append(folder)
            click.echo(f"  {Fore.GREEN}Added: {folder}{Style.RESET_ALL}")
        else:
            click.echo(f"  {Fore.YELLOW}Already added: {folder}{Style.RESET_ALL}")

    return custom_ignores


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
        DEFAULT_CUSTOM_IGNORES,
        DEFAULT_SYNC_GITIGNORE,
        DEFAULT_FORMAT,
        DEFAULT_INDEXING_ENABLED,
        DEFAULT_INDEXING_INCLUDE,
        DEFAULT_INDEXING_EXCLUDE
    )
    click.echo(f"\n{Fore.GREEN}Created twiggy.yml with defaults - you can edit this file later!{Style.RESET_ALL}")


def _display_added_ignores(custom_ignores):
    click.echo(f"{Fore.CYAN}Custom ignores added:{Style.RESET_ALL}")
    for ignore in custom_ignores:
        click.echo(f"  - {ignore}")


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
