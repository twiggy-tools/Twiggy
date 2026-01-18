import yaml
import os
import fnmatch
from pathlib import Path
from typing import List, Set
from importlib import resources
from .defaults import DEFAULT_INDEXING_ESTIMATE_BYTES_PER_SEC

class Config:
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.config_file = project_root / 'twiggy.yml'
    
    def get_default_ignores(self) -> Set[str]:
        return {
            'node_modules', '.next', '.nuxt', 'dist', 'build', '.output', '.vercel', '.netlify', 'out', '.cache',
            '.parcel-cache', '.webpack', 'coverage', '.nyc_output', '.jest',
            '__pycache__', '.pytest_cache', '.mypy_cache', '.tox', 'venv', 'env', '.venv', '.env', 'site-packages',
            '.coverage', 'htmlcov', '*.egg-info', '.eggs',
            'target', 'Cargo.lock', 'vendor', '.gradle', '.idea', '.vs', 'cmake-build-debug', 'cmake-build-release',
            '.bundle', '.vscode', '.vscode-test', '.git', '.svn', '.hg', '.bzr', '.DS_Store', 'Thumbs.db', '.Trash',
            'logs', 'log', 'tmp', 'temp', '.tmp', '.temp', '_site', '.docusaurus', 'public', 'docs/_build',
            'ios/build', 'android/build', '.expo', '*.db', '*.sqlite', '*.sqlite3', '.docker', '.terraform',
            '.serverless', '.yarn', '.pnpm-store', '.rush', '.playwright', 'cypress/videos', 'cypress/screenshots',
            'test-results', '.sass-cache', '.postcssrc', '.eslintcache', '.stylelintcache', '.github', '.husky'
        }
    
    def exists(self) -> bool:
        return self.config_file.exists()
    
    def create_default_config(self, structure_exclude: List[str] = None, sync_gitignore: bool = True, format_type: str = 'xml',
                               indexing_enabled: bool = True, indexing_include: List[str] = None, indexing_exclude: List[str] = None):
        structure_exclude = structure_exclude or []
        indexing_include = indexing_include or []
        indexing_exclude = indexing_exclude or []

        try:
            template = resources.files('cursor_context').joinpath('templates/twiggy.yml.template').read_text(encoding='utf-8')
        except (FileNotFoundError, TypeError):
            template = (
                "# Twiggy Configuration\n"
                "# \n"
                "# Twiggy generates real-time directory structure and codebase index for Cursor AI\n"
                "# Your AI always knows your codebase's structure and API surface automatically\n"
                "# https://github.com/twiggy-tools/Twiggy\n\n"
                "syncWithGitignore: {sync_gitignore}\n\n"
                "structure:\n"
                "  format: {format}\n"
                "  exclude:\n{structure_exclude}\n\n"
                "# Codebase Indexing - extracts function signatures, types, and exports\n"
                "indexing:\n"
                "  enabled: {indexing_enabled}\n"
                "  include: {indexing_include}\n"
                "  exclude:\n{indexing_exclude}\n"
            )

        config_content = template.format(
            sync_gitignore=str(sync_gitignore).lower(),
            format=format_type,
            structure_exclude=self._format_exclude_list(structure_exclude),
            indexing_enabled=str(indexing_enabled).lower(),
            indexing_include=self._format_list_inline(indexing_include),
            indexing_exclude=self._format_exclude_list(indexing_exclude)
        )

        with open(self.config_file, 'w', encoding='utf-8') as f:
            f.write(config_content)
    
    def _format_list_inline(self, items: List[str]) -> str:
        """Format a list as inline YAML array"""
        if not items:
            return '[]'
        return '[' + ', '.join(f'"{item}"' for item in items) + ']'

    def _format_exclude_list(self, excludes: List[str]) -> str:
        """Format exclude list with proper indentation"""
        if not excludes:
            return '    # - "*.example.ts"'
        return '\n'.join(f'    - "{exclude}"' for exclude in excludes)
    
    def load(self) -> dict:
        if not self.exists():
            return {}

        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f) or {}

            structure = config.get('structure', {})
            indexing = config.get('indexing', {})

            return {
                'syncWithGitignore': config.get('syncWithGitignore', True),
                'structure': {
                    'format': structure.get('format', config.get('format', 'xml')),  # Fallback for old configs
                    'exclude': structure.get('exclude', config.get('ignore', [])) or [],  # Fallback for old configs
                },
                'indexing': {
                    'enabled': indexing.get('enabled', True),
                    'include': indexing.get('include', []) or [],
                    'exclude': indexing.get('exclude', []) or [],
                    'estimateBytesPerSec': indexing.get(
                        'estimateBytesPerSec', DEFAULT_INDEXING_ESTIMATE_BYTES_PER_SEC
                    ),
                }
            }
        except Exception:
            return {}
    
    def get_ignores(self) -> Set[str]:
        config = self.load()
        all_ignores = set(self.get_default_ignores())

        structure_exclude = config.get('structure', {}).get('exclude', []) or []
        all_ignores.update(structure_exclude)
        
        if config.get('syncWithGitignore', True):
            gitignore_patterns = self._load_gitignore()
            all_ignores.update(gitignore_patterns)
        
        all_ignores.add('.cursor/rules/file-structure.mdc')
        
        return all_ignores
    
    def _load_gitignore(self) -> Set[str]:
        gitignore_file = self.project_root / '.gitignore'
        if not gitignore_file.exists():
            return set()
        
        patterns = set()
        try:
            with open(gitignore_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        clean_pattern = line.strip('/*')
                        if clean_pattern:
                            patterns.add(clean_pattern)
        except Exception:
            pass
        
        return patterns
    
    def should_ignore(self, path: Path) -> bool:
        ignores = self.get_ignores()

        try:
            relative_path = path.relative_to(self.project_root)
            relative_path_str = str(relative_path).replace('\\', '/')
        except ValueError:
            relative_path_str = str(path).replace('\\', '/')

        for ignore in ignores:
            ignore = ignore.replace('\\', '/')

            if relative_path_str == ignore:
                return True

            if relative_path_str.startswith(ignore + '/'):
                return True

            if '/' not in ignore:
                path_parts = relative_path_str.split('/')
                if ignore in path_parts:
                    return True

        return False

    def get_indexing_default_ignores(self) -> Set[str]:
        """Default ignores specifically for the indexer"""
        return {
            # Test files
            '*.test.ts', '*.test.tsx', '*.test.js', '*.test.jsx',
            '*.spec.ts', '*.spec.tsx', '*.spec.js', '*.spec.jsx',
            '__tests__', '__mocks__', 'test', 'tests',
            '*.test.mjs', '*.test.cjs', '*.spec.mjs', '*.spec.cjs',

            # Build outputs and dependencies
            'node_modules', '.next', '.nuxt', 'dist', 'build', '.output',
            '.vercel', '.netlify', 'out', '.cache', '.parcel-cache',
            '.webpack', 'coverage', '.nyc_output', '.turbo',

            # Config files
            '*.config.ts', '*.config.js', '*.config.mjs', '*.config.cjs',
            'vite.config.*', 'next.config.*', 'nuxt.config.*',
            'tailwind.config.*', 'postcss.config.*', 'jest.config.*',
            'vitest.config.*', 'webpack.config.*', 'rollup.config.*',
            'babel.config.*', 'eslint.config.*', 'prettier.config.*',
            'tsconfig.json', 'jsconfig.json', 'package.json',

            # Declaration files (already type definitions)
            '*.d.ts',

            # Generated files
            '*.generated.ts', '*.generated.js',
            'generated', 'codegen', '.codegen',

            # Storybook
            '*.stories.ts', '*.stories.tsx', '*.stories.js', '*.stories.jsx',
            '.storybook',

            # E2E tests
            'e2e', 'cypress', 'playwright',

            # Scripts and tooling
            'scripts', 'tools', 'bin',

            # Migrations and seeds
            'migrations', 'seeds', 'fixtures',

            # Public assets
            'public', 'static', 'assets',

            # Version control and IDE
            '.git', '.svn', '.hg', '.idea', '.vscode',

            # Temporary files
            'tmp', 'temp', '.tmp', '.temp',
        }

    def get_indexing_config(self) -> dict:
        """Get indexing-specific configuration"""
        config = self.load()
        indexing = config.get('indexing', {})

        return {
            'enabled': indexing.get('enabled', True),
            'include': indexing.get('include', []),
            'exclude': indexing.get('exclude', []),
            'estimateBytesPerSec': indexing.get(
                'estimateBytesPerSec', DEFAULT_INDEXING_ESTIMATE_BYTES_PER_SEC
            ),
        }

    def should_index_file(self, path: Path) -> bool:
        """Determine if a file should be indexed"""
        indexing_config = self.get_indexing_config()

        if not indexing_config['enabled']:
            return False

        try:
            relative_path = path.relative_to(self.project_root)
            relative_path_str = str(relative_path).replace('\\', '/')
        except ValueError:
            relative_path_str = str(path).replace('\\', '/')

        filename = path.name

        # Check against structure ignores first
        if self.should_ignore(path):
            return False

        # Check against indexing-specific default ignores
        default_ignores = self.get_indexing_default_ignores()
        for ignore in default_ignores:
            if self._matches_pattern(relative_path_str, filename, ignore):
                return False

        # Check against custom excludes
        for exclude in indexing_config['exclude']:
            if self._matches_pattern(relative_path_str, filename, exclude):
                return False

        # Check includes (if specified, only include matching files)
        includes = indexing_config['include']
        if includes:
            return any(self._matches_pattern(relative_path_str, filename, inc) for inc in includes)

        return True

    def _matches_pattern(self, path: str, filename: str, pattern: str) -> bool:
        """Check if path or filename matches a glob-like pattern"""
        # Direct match
        if fnmatch.fnmatch(path, pattern):
            return True
        if fnmatch.fnmatch(filename, pattern):
            return True

        # Check if pattern matches any path component
        if '/' not in pattern and '*' not in pattern:
            path_parts = path.split('/')
            if pattern in path_parts:
                return True

        return False
