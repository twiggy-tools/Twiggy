import time
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from .config import Config
from .scanner import DirectoryScanner
from colorama import Fore, Style


class CursorContextHandler(FileSystemEventHandler):
    def __init__(self, config: Config):
        self.config = config
        self.scanner = DirectoryScanner(config)

        # Initialize indexer if enabled
        indexing_config = config.get_indexing_config()
        self.indexing_enabled = indexing_config['enabled']
        self.indexer = None
        if self.indexing_enabled:
            from .indexer import CodebaseIndexer
            self.indexer = CodebaseIndexer(config)

        # Separate debounce timers
        self.last_structure_update = 0
        self.last_index_update = 0
        self.update_delay = 1.0

        # File extensions that trigger index updates
        self.indexable_extensions = {'.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs'}

    def should_trigger_structure_update(self, event_path: str) -> bool:
        """Check if event should trigger file structure update"""
        path = Path(event_path)

        if self.config.should_ignore(path):
            return False

        if '.cursor' in path.parts:
            return False

        if self._is_temporary_file(path):
            return False

        return True

    def should_trigger_index_update(self, event_path: str) -> bool:
        """Check if event should trigger codebase index update"""
        if not self.indexing_enabled or not self.indexer:
            return False

        path = Path(event_path)

        # Only index supported file types
        if path.suffix.lower() not in self.indexable_extensions:
            return False

        # Check against indexing filters
        if not self.config.should_index_file(path):
            return False

        return True

    def _is_temporary_file(self, path):
        if path.name.startswith('.') and path.name not in ['.gitignore', '.env', '.env.local']:
            return True

        temp_patterns = ['.tmp', '.temp', '~', '.swp', '.swo']
        return any(path.name.endswith(pattern) for pattern in temp_patterns)

    def update_structure(self, event_type: str, path: str):
        """Update the file structure output"""
        current_time = time.time()

        if current_time - self.last_structure_update < self.update_delay:
            return

        self.last_structure_update = current_time

        try:
            self.scanner.scan_and_generate()
            print(f"{Fore.GREEN}Updated structure ({event_type}): {Path(path).name}{Style.RESET_ALL}")
        except Exception as e:
            print(f"{Fore.RED}Error updating structure: {e}{Style.RESET_ALL}")

    def update_index(self, event_type: str, path: str, src_path: str = None):
        """Update the codebase index output"""
        current_time = time.time()

        if current_time - self.last_index_update < self.update_delay:
            return

        self.last_index_update = current_time

        try:
            self.indexer.index_and_generate(
                changed_path=Path(path),
                event_type=event_type,
                src_path=Path(src_path) if src_path else None,
            )
            print(f"{Fore.BLUE}Updated index ({event_type}): {Path(path).name}{Style.RESET_ALL}")
        except Exception as e:
            print(f"{Fore.RED}Error updating index: {e}{Style.RESET_ALL}")

    def on_created(self, event):
        if event.is_directory:
            if self.should_trigger_structure_update(event.src_path):
                self.update_structure("created", event.src_path)
        else:
            if self.should_trigger_structure_update(event.src_path):
                self.update_structure("created", event.src_path)
            if self.should_trigger_index_update(event.src_path):
                self.update_index("created", event.src_path)

    def on_deleted(self, event):
        if event.is_directory:
            if self.should_trigger_structure_update(event.src_path):
                self.update_structure("deleted", event.src_path)
        else:
            if self.should_trigger_structure_update(event.src_path):
                self.update_structure("deleted", event.src_path)
            if self.should_trigger_index_update(event.src_path):
                self.update_index("deleted", event.src_path)

    def on_moved(self, event):
        should_update_structure = (
            self.should_trigger_structure_update(event.src_path) or
            self.should_trigger_structure_update(event.dest_path)
        )
        should_update_index = (
            self.should_trigger_index_update(event.src_path) or
            self.should_trigger_index_update(event.dest_path)
        )

        if should_update_structure:
            self.update_structure("moved", event.dest_path)
        if should_update_index:
            self.update_index("moved", event.dest_path, event.src_path)

    def on_modified(self, event):
        if event.is_directory:
            # Directory modified - only update structure
            if self.should_trigger_structure_update(event.src_path):
                self.update_structure("modified", event.src_path)
        else:
            # File content changed - update index (not structure, since file list didn't change)
            if self.should_trigger_index_update(event.src_path):
                self.update_index("modified", event.src_path)


class FileWatcher:
    def __init__(self, config: Config):
        self.config = config
        self.observer = Observer()
        self.handler = CursorContextHandler(config)

    def start(self):
        self._generate_initial_outputs()
        self._setup_observer()
        self._run_watcher()

    def _generate_initial_outputs(self):
        """Generate both structure and index on startup"""
        scanner = DirectoryScanner(self.config)
        scanner.scan_and_generate()
        print(f"{Fore.CYAN}Initial structure generated{Style.RESET_ALL}")

        indexing_config = self.config.get_indexing_config()
        if indexing_config['enabled']:
            from .indexer import CodebaseIndexer
            indexer = CodebaseIndexer(self.config)
            indexer.index_and_generate()
            print(f"{Fore.CYAN}Initial codebase index generated{Style.RESET_ALL}")

    def _setup_observer(self):
        self.observer.schedule(
            self.handler,
            str(self.config.project_root),
            recursive=True
        )
        self.observer.start()

    def _run_watcher(self):
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop()

    def stop(self):
        self.observer.stop()
        self.observer.join()
        print(f"{Fore.YELLOW}File watcher stopped{Style.RESET_ALL}")
