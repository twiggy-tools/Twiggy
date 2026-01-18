from pathlib import Path
from typing import Dict, List
from .config import Config
from importlib import resources

class DirectoryScanner:
    def __init__(self, config: Config):
        self.config = config
        self.project_root = config.project_root
        self.output_file = self.project_root / '.cursor' / 'rules' / 'file-structure.mdc'
    
    def scan_directory(self) -> Dict:
        structure = {'items': [], 'total_dirs': 0, 'total_files': 0}
        
        def scan_recursive(path: Path, level: int = 0) -> List[Dict]:
            items = []
            
            try:
                all_items = list(path.iterdir())
                directories = self._filter_directories(all_items)
                files = self._filter_files(all_items)
                
                items.extend(self._process_directories(directories, level, structure, scan_recursive))
                items.extend(self._process_files(files, level, structure))
                
            except PermissionError:
                pass
            
            return items
        
        structure['items'] = scan_recursive(self.project_root)
        return structure
    
    def _filter_directories(self, items):
        directories = [item for item in items if item.is_dir() and not self.config.should_ignore(item)]
        return sorted(directories, key=lambda x: x.name.lower())
    
    def _filter_files(self, items):
        files = [item for item in items if item.is_file() and not item.name.startswith('.')]
        return sorted(files, key=lambda x: x.name.lower())
    
    def _process_directories(self, directories, level, structure, scan_recursive):
        items = []
        for directory in directories:
            dir_info = {
                'type': 'directory',
                'name': directory.name,
                'path': str(directory.relative_to(self.project_root)),
                'level': level,
                'children': scan_recursive(directory, level + 1)
            }
            items.append(dir_info)
            structure['total_dirs'] += 1
        return items
    
    def _process_files(self, files, level, structure):
        items = []
        for file in files:
            file_info = {
                'type': 'file',
                'name': file.name,
                'path': str(file.relative_to(self.project_root)),
                'level': level,
                'extension': file.suffix.lower() if file.suffix else None
            }
            items.append(file_info)
            structure['total_files'] += 1
        return items
    
    def generate_tree_structure(self, items: List[Dict], level: int = 0) -> List[str]:
        lines = []
        
        for i, item in enumerate(items):
            is_last = i == len(items) - 1
            prefix = self._get_tree_prefix(level, is_last)
            
            if item['type'] == 'directory':
                lines.append(f"{prefix}{item['name']}/")
                if item.get('children'):
                    child_lines = self.generate_tree_structure(item['children'], level + 1)
                    lines.extend(child_lines)
            else:
                lines.append(f"{prefix}{item['name']}")
        
        return lines
    
    def _get_tree_prefix(self, level, is_last):
        if level == 0:
            return ""
        
        prefix = "  " * (level - 1)
        return prefix + ("└── " if is_last else "├── ")
    
    def generate_cursor_rule(self, structure: Dict) -> str:
        project_name = self.project_root.name
        
        config = self.config.load()
        format_type = config.get('structure', {}).get('format', 'xml')
        
        if format_type == 'xml':
            tree_content = self.generate_xml_structure(structure['items'])
        else:
            tree_lines = self.generate_tree_structure(structure['items'])
            tree_content = "\n".join(tree_lines)
        
        try:
            template = resources.files('cursor_context').joinpath('templates/file-structure.mdc.template').read_text(encoding='utf-8')
        except FileNotFoundError:
            template = (
                "---\nalwaysApply: true\n---\n\n"
                f"# {project_name} Structure\n\n"
                "```\n{project_name}/\n{tree_content}\n```\n"
            )
        
        return template.format(
            project_name=project_name,
            tree_content=tree_content
        )
    
    def generate_xml_structure(self, items: List[Dict], level: int = 0) -> str:
        lines = []
        indent = "  " * level
        
        for item in items:
            if item['type'] == 'directory':
                lines.append(f"{indent}<directory name=\"{item['name']}\">")
                if item.get('children'):
                    child_content = self.generate_xml_structure(item['children'], level + 1)
                    lines.append(child_content)
                lines.append(f"{indent}</directory>")
            else:
                lines.append(f"{indent}<file name=\"{item['name']}\"/>")
        
        return '\n'.join(lines)
    
    def scan_and_generate(self):
        self.output_file.parent.mkdir(parents=True, exist_ok=True)
        
        structure = self.scan_directory()
        rule_content = self.generate_cursor_rule(structure)
        
        with open(self.output_file, 'w', encoding='utf-8') as f:
            f.write(rule_content)
        
        return self.output_file
