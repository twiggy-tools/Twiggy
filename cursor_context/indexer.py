"""
Codebase Indexer - Extracts function signatures, types, classes, and exports from code files.
Uses tree-sitter for AST-based parsing.
"""

from pathlib import Path
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field
from importlib import resources

import tree_sitter
import tree_sitter_typescript as ts_typescript
import tree_sitter_javascript as ts_javascript


@dataclass
class ExportedItem:
    """Represents an exported item from a source file"""
    kind: str  # 'function', 'type', 'interface', 'class', 'const', 'variable', 'enum'
    name: str
    signature: str
    methods: List[str] = field(default_factory=list)


@dataclass
class FileIndex:
    """Represents the indexed contents of a single file"""
    path: str
    exports: List[ExportedItem]


class TreeSitterParser:
    """Handles tree-sitter parsing for different languages"""

    def __init__(self):
        self._parsers: Dict[str, tree_sitter.Parser] = {}
        self._languages: Dict[str, tree_sitter.Language] = {}
        self._init_languages()

    def _init_languages(self):
        """Initialize supported languages"""
        self._languages['typescript'] = tree_sitter.Language(ts_typescript.language_typescript())
        self._languages['tsx'] = tree_sitter.Language(ts_typescript.language_tsx())
        self._languages['javascript'] = tree_sitter.Language(ts_javascript.language())
        self._languages['jsx'] = self._languages['javascript']

    def get_parser(self, language: str) -> Optional[tree_sitter.Parser]:
        """Get or create a parser for the given language"""
        if language not in self._languages:
            return None

        if language not in self._parsers:
            parser = tree_sitter.Parser(self._languages[language])
            self._parsers[language] = parser

        return self._parsers[language]

    def get_language_for_file(self, file_path: Path) -> Optional[str]:
        """Determine language from file extension"""
        ext_map = {
            '.ts': 'typescript',
            '.tsx': 'tsx',
            '.js': 'javascript',
            '.jsx': 'jsx',
            '.mjs': 'javascript',
            '.cjs': 'javascript',
        }
        return ext_map.get(file_path.suffix.lower())


class TypeScriptExtractor:
    """Extracts exports from TypeScript/JavaScript AST"""

    def extract_exports(self, tree: tree_sitter.Tree, source: bytes) -> List[ExportedItem]:
        """Extract all exported items from the AST"""
        exports = []
        root = tree.root_node

        for child in root.children:
            if child.type == 'export_statement':
                exports.extend(self._process_export_statement(child, source))

        return exports

    def _process_export_statement(self, node, source: bytes) -> List[ExportedItem]:
        """Process an export statement node"""
        exports = []

        # Check for default export
        is_default = any(c.type == 'default' for c in node.children)

        for child in node.children:
            if child.type == 'function_declaration':
                item = self._extract_function(child, source, is_default)
                if item:
                    exports.append(item)
            elif child.type == 'class_declaration':
                item = self._extract_class(child, source, is_default)
                if item:
                    exports.append(item)
            elif child.type == 'type_alias_declaration':
                item = self._extract_type_alias(child, source)
                if item:
                    exports.append(item)
            elif child.type == 'interface_declaration':
                item = self._extract_interface(child, source)
                if item:
                    exports.append(item)
            elif child.type == 'lexical_declaration':
                exports.extend(self._extract_lexical_declaration(child, source))
            elif child.type == 'enum_declaration':
                item = self._extract_enum(child, source)
                if item:
                    exports.append(item)
            elif child.type == 'function_signature':
                item = self._extract_function_signature(child, source)
                if item:
                    exports.append(item)

        return exports

    def _get_text(self, node, source: bytes) -> str:
        """Get text content of a node"""
        return source[node.start_byte:node.end_byte].decode('utf-8')

    def _find_child(self, node, type_name: str):
        """Find first child of given type"""
        for child in node.children:
            if child.type == type_name:
                return child
        return None

    def _find_children(self, node, type_name: str):
        """Find all children of given type"""
        return [c for c in node.children if c.type == type_name]

    def _extract_function(self, node, source: bytes, is_default: bool = False) -> Optional[ExportedItem]:
        """Extract function declaration"""
        name_node = self._find_child(node, 'identifier')
        if not name_node:
            return None

        name = self._get_text(name_node, source)
        params_node = self._find_child(node, 'formal_parameters')
        return_type_node = self._find_child(node, 'type_annotation')

        params = self._get_text(params_node, source) if params_node else '()'
        return_type = self._get_text(return_type_node, source) if return_type_node else ''

        prefix = 'export default ' if is_default else 'export '
        signature = f"{prefix}function {name}{params}{return_type}"

        return ExportedItem(kind='function', name=name, signature=signature)

    def _extract_function_signature(self, node, source: bytes) -> Optional[ExportedItem]:
        """Extract function signature (for .d.ts files or ambient declarations)"""
        name_node = self._find_child(node, 'identifier')
        if not name_node:
            return None

        name = self._get_text(name_node, source)
        params_node = self._find_child(node, 'formal_parameters')
        return_type_node = self._find_child(node, 'type_annotation')

        params = self._get_text(params_node, source) if params_node else '()'
        return_type = self._get_text(return_type_node, source) if return_type_node else ''

        signature = f"export function {name}{params}{return_type}"

        return ExportedItem(kind='function', name=name, signature=signature)

    def _extract_class(self, node, source: bytes, is_default: bool = False) -> Optional[ExportedItem]:
        """Extract class declaration with public methods"""
        name_node = self._find_child(node, 'identifier') or self._find_child(node, 'type_identifier')
        if not name_node:
            return None

        name = self._get_text(name_node, source)

        # Get heritage (extends/implements)
        heritage = ''
        heritage_node = self._find_child(node, 'class_heritage')
        if heritage_node:
            heritage = ' ' + self._get_text(heritage_node, source)

        # Extract public methods
        methods = []
        class_body = self._find_child(node, 'class_body')
        if class_body:
            for member in class_body.children:
                if member.type == 'method_definition':
                    method_sig = self._extract_method_signature(member, source)
                    if method_sig:
                        methods.append(method_sig)
                elif member.type == 'public_field_definition':
                    field_sig = self._extract_field_signature(member, source)
                    if field_sig:
                        methods.append(field_sig)

        prefix = 'export default ' if is_default else 'export '
        signature = f"{prefix}class {name}{heritage}"

        return ExportedItem(kind='class', name=name, signature=signature, methods=methods)

    def _extract_method_signature(self, node, source: bytes) -> Optional[str]:
        """Extract method signature from class"""
        # Skip private methods
        for child in node.children:
            if child.type == 'private' or child.type == 'accessibility_modifier':
                text = self._get_text(child, source)
                if text == 'private':
                    return None

        name_node = self._find_child(node, 'property_identifier')
        if not name_node:
            return None

        name = self._get_text(name_node, source)
        params_node = self._find_child(node, 'formal_parameters')
        return_type_node = self._find_child(node, 'type_annotation')

        params = self._get_text(params_node, source) if params_node else '()'
        return_type = self._get_text(return_type_node, source) if return_type_node else ''

        # Check for async/static
        modifiers = []
        for child in node.children:
            if child.type == 'async':
                modifiers.append('async')
            elif child.type == 'static':
                modifiers.append('static')

        prefix = ' '.join(modifiers) + ' ' if modifiers else ''
        return f"{prefix}{name}{params}{return_type}"

    def _extract_field_signature(self, node, source: bytes) -> Optional[str]:
        """Extract public field signature from class"""
        name_node = self._find_child(node, 'property_identifier')
        if not name_node:
            return None

        name = self._get_text(name_node, source)
        type_node = self._find_child(node, 'type_annotation')
        type_str = self._get_text(type_node, source) if type_node else ''

        return f"{name}{type_str}"

    def _extract_type_alias(self, node, source: bytes) -> Optional[ExportedItem]:
        """Extract type alias declaration"""
        name_node = self._find_child(node, 'type_identifier')
        if not name_node:
            return None

        name = self._get_text(name_node, source)

        # Get the full type definition (simplified)
        type_params = self._find_child(node, 'type_parameters')
        type_params_str = self._get_text(type_params, source) if type_params else ''

        # Get the type value
        type_node = None
        for child in node.children:
            if child.type not in ['export', 'type', 'type_identifier', 'type_parameters', '=']:
                type_node = child
                break

        type_value = self._get_text(type_node, source) if type_node else ''

        # Truncate very long type definitions
        if len(type_value) > 100:
            type_value = type_value[:97] + '...'

        signature = f"export type {name}{type_params_str} = {type_value}"

        return ExportedItem(kind='type', name=name, signature=signature)

    def _extract_interface(self, node, source: bytes) -> Optional[ExportedItem]:
        """Extract interface declaration"""
        name_node = self._find_child(node, 'type_identifier')
        if not name_node:
            return None

        name = self._get_text(name_node, source)

        # Get type parameters
        type_params = self._find_child(node, 'type_parameters')
        type_params_str = self._get_text(type_params, source) if type_params else ''

        # Get extends clause
        extends = ''
        extends_node = self._find_child(node, 'extends_type_clause')
        if extends_node:
            extends = ' ' + self._get_text(extends_node, source)

        # Get interface body (properties)
        properties = []
        body = self._find_child(node, 'interface_body') or self._find_child(node, 'object_type')
        if body:
            for member in body.children:
                if member.type == 'property_signature':
                    prop_sig = self._extract_property_signature(member, source)
                    if prop_sig:
                        properties.append(prop_sig)
                elif member.type == 'method_signature':
                    method_sig = self._extract_interface_method_signature(member, source)
                    if method_sig:
                        properties.append(method_sig)

        signature = f"export interface {name}{type_params_str}{extends}"

        return ExportedItem(kind='interface', name=name, signature=signature, methods=properties)

    def _extract_property_signature(self, node, source: bytes) -> Optional[str]:
        """Extract property signature from interface"""
        name_node = self._find_child(node, 'property_identifier')
        if not name_node:
            return None

        name = self._get_text(name_node, source)

        # Check for optional
        optional = '?' if self._find_child(node, '?') else ''

        type_node = self._find_child(node, 'type_annotation')
        type_str = self._get_text(type_node, source) if type_node else ''

        return f"{name}{optional}{type_str}"

    def _extract_interface_method_signature(self, node, source: bytes) -> Optional[str]:
        """Extract method signature from interface"""
        name_node = self._find_child(node, 'property_identifier')
        if not name_node:
            return None

        name = self._get_text(name_node, source)
        params_node = self._find_child(node, 'formal_parameters')
        return_type_node = self._find_child(node, 'type_annotation')

        params = self._get_text(params_node, source) if params_node else '()'
        return_type = self._get_text(return_type_node, source) if return_type_node else ''

        return f"{name}{params}{return_type}"

    def _extract_lexical_declaration(self, node, source: bytes) -> List[ExportedItem]:
        """Extract const/let declarations"""
        exports = []

        # Get const/let keyword
        keyword = 'const'
        for child in node.children:
            if child.type in ['const', 'let', 'var']:
                keyword = child.type
                break

        # Get variable declarators
        for child in node.children:
            if child.type == 'variable_declarator':
                item = self._extract_variable_declarator(child, source, keyword)
                if item:
                    exports.append(item)

        return exports

    def _extract_variable_declarator(self, node, source: bytes, keyword: str) -> Optional[ExportedItem]:
        """Extract a single variable declaration"""
        name_node = self._find_child(node, 'identifier')
        if not name_node:
            # Could be destructuring pattern
            return None

        name = self._get_text(name_node, source)
        type_node = self._find_child(node, 'type_annotation')
        type_str = self._get_text(type_node, source) if type_node else ''

        # Check if it's a function (arrow function or function expression)
        value_node = None
        for child in node.children:
            if child.type in ['arrow_function', 'function_expression', 'function']:
                value_node = child
                break

        if value_node:
            # It's a function
            if value_node.type == 'arrow_function':
                params_node = self._find_child(value_node, 'formal_parameters')
                if not params_node:
                    # Single param without parens
                    param_node = self._find_child(value_node, 'identifier')
                    params = f"({self._get_text(param_node, source)})" if param_node else '()'
                else:
                    params = self._get_text(params_node, source)

                return_type_node = self._find_child(value_node, 'type_annotation')
                return_type = self._get_text(return_type_node, source) if return_type_node else ''

                signature = f"export {keyword} {name} = {params}{return_type} => ..."
            else:
                params_node = self._find_child(value_node, 'formal_parameters')
                params = self._get_text(params_node, source) if params_node else '()'
                return_type_node = self._find_child(value_node, 'type_annotation')
                return_type = self._get_text(return_type_node, source) if return_type_node else ''
                signature = f"export {keyword} {name} = function{params}{return_type}"

            return ExportedItem(kind='function', name=name, signature=signature)

        # Regular variable
        signature = f"export {keyword} {name}{type_str}"
        return ExportedItem(kind='const' if keyword == 'const' else 'variable', name=name, signature=signature)

    def _extract_enum(self, node, source: bytes) -> Optional[ExportedItem]:
        """Extract enum declaration"""
        name_node = self._find_child(node, 'identifier')
        if not name_node:
            return None

        name = self._get_text(name_node, source)

        # Get enum members
        members = []
        body = self._find_child(node, 'enum_body')
        if body:
            for child in body.children:
                if child.type == 'enum_member':
                    member_name = self._find_child(child, 'property_identifier')
                    if member_name:
                        members.append(self._get_text(member_name, source))

        signature = f"export enum {name}"
        return ExportedItem(kind='enum', name=name, signature=signature, methods=members)


class SkeletonGenerator:
    """Generates the codebase-index.mdc file from indexed data"""

    def __init__(self, config):
        self.config = config
        self.project_root = config.project_root
        self.output_file = self.project_root / '.cursor' / 'rules' / 'codebase-index.mdc'

    def generate(self, file_indices: List[FileIndex]) -> Path:
        """Generate the skeleton output file"""
        self.output_file.parent.mkdir(parents=True, exist_ok=True)

        content = self._build_content(file_indices)

        with open(self.output_file, 'w', encoding='utf-8') as f:
            f.write(content)

        return self.output_file

    def _build_content(self, file_indices: List[FileIndex]) -> str:
        """Build the full content for the output file"""
        project_name = self.project_root.name

        try:
            template = resources.files('cursor_context').joinpath(
                'templates/codebase-index.mdc.template'
            ).read_text(encoding='utf-8')
        except (FileNotFoundError, TypeError):
            template = self._get_fallback_template()

        index_content = self._format_indices(file_indices)

        return template.format(
            project_name=project_name,
            index_content=index_content
        )

    def _format_indices(self, file_indices: List[FileIndex]) -> str:
        """Format all file indices into the output format"""
        lines = []

        for file_index in sorted(file_indices, key=lambda x: x.path):
            if not file_index.exports:
                continue

            lines.append(f"// {file_index.path}")

            for export in file_index.exports:
                lines.append(self._format_export(export))

            lines.append("")

        return "\n".join(lines)

    def _format_export(self, export: ExportedItem) -> str:
        """Format a single export item"""
        if export.kind in ['class', 'interface', 'enum'] and export.methods:
            method_lines = "\n".join(f"  {m}" for m in export.methods[:10])  # Limit methods shown
            if len(export.methods) > 10:
                method_lines += f"\n  // ... and {len(export.methods) - 10} more"
            return f"{export.signature} {{\n{method_lines}\n}}"

        return export.signature

    def _get_fallback_template(self) -> str:
        return (
            "---\n"
            "alwaysApply: true\n"
            "---\n\n"
            "# {project_name} Codebase Index\n\n"
            "This file provides an index of exported functions, types, interfaces, "
            "classes, and constants in your codebase. Updated in real-time by Twiggy.\n\n"
            "Use this index to discover existing utilities and avoid duplicating code.\n\n"
            "```typescript\n{index_content}\n```\n"
        )


class CodebaseIndexer:
    """Main class that orchestrates the indexing process"""

    def __init__(self, config):
        self.config = config
        self.project_root = config.project_root
        self.parser = TreeSitterParser()
        self.generator = SkeletonGenerator(config)

        self.extractors = {
            'typescript': TypeScriptExtractor(),
            'tsx': TypeScriptExtractor(),
            'javascript': TypeScriptExtractor(),
            'jsx': TypeScriptExtractor(),
        }

    def index_and_generate(self) -> Path:
        """Index the codebase and generate output file"""
        file_indices = self._index_all_files()
        return self.generator.generate(file_indices)

    def _index_all_files(self) -> List[FileIndex]:
        """Index all eligible files in the project"""
        indices = []

        for file_path in self._find_indexable_files():
            index = self._index_file(file_path)
            if index and index.exports:
                indices.append(index)

        return indices

    def _find_indexable_files(self) -> List[Path]:
        """Find all files that should be indexed"""
        indexable = []
        extensions = ['.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs']

        for ext in extensions:
            for file_path in self.project_root.rglob(f'*{ext}'):
                if self.config.should_index_file(file_path):
                    indexable.append(file_path)

        return indexable

    def _index_file(self, file_path: Path) -> Optional[FileIndex]:
        """Index a single file"""
        language = self.parser.get_language_for_file(file_path)
        if not language:
            return None

        parser = self.parser.get_parser(language)
        if not parser:
            return None

        try:
            with open(file_path, 'rb') as f:
                source = f.read()

            tree = parser.parse(source)
            extractor = self.extractors.get(language)

            if not extractor:
                return None

            exports = extractor.extract_exports(tree, source)
            relative_path = str(file_path.relative_to(self.project_root)).replace('\\', '/')

            return FileIndex(path=relative_path, exports=exports)

        except Exception:
            return None
