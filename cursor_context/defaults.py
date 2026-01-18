"""Default configuration values for Twiggy"""

DEFAULT_SYNC_GITIGNORE = True
DEFAULT_FORMAT = 'xml'

# Indexing defaults
DEFAULT_INDEXING_ENABLED = True
DEFAULT_INDEXING_INCLUDE = []  # Empty = index everything
DEFAULT_INDEXING_EXCLUDE = []  # Default excludes are handled in config.py
DEFAULT_INDEXING_ESTIMATE_BYTES_PER_SEC = 3_000_000