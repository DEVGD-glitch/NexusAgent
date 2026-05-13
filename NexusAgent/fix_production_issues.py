#!/usr/bin/env python3
"""
Script de correction automatique des problèmes de production
- Supprime les imports inutilisés
- Remplace les "except ... pass" silencieux par du logging approprié
- Supprime les print() de production
"""

import ast
import re
from pathlib import Path
from typing import List, Tuple, Dict, Set


class ImportTracker(ast.NodeVisitor):
    """Track which imports are actually used in the code."""
    
    def __init__(self):
        self.imports: Dict[str, int] = {}  # name -> line number
        self.used_names: Set[str] = set()
        
    def visit_Import(self, node):
        for alias in node.names:
            name = alias.asname if alias.asname else alias.name.split('.')[0]
            self.imports[name] = node.lineno
        self.generic_visit(node)
    
    def visit_ImportFrom(self, node):
        for alias in node.names:
            name = alias.asname if alias.asname else alias.name
            if name != '*':
                self.imports[name] = node.lineno
        self.generic_visit(node)
    
    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Load):
            self.used_names.add(node.id)
        self.generic_visit(node)
    
    def visit_Attribute(self, node):
        parts = []
        current = node
        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value
        if isinstance(current, ast.Name):
            self.used_names.add(current.id)
        self.generic_visit(node)
    
    def get_unused_imports(self) -> List[Tuple[str, int]]:
        """Return list of (name, line_number) for unused imports."""
        unused = []
        for name, lineno in self.imports.items():
            if name not in self.used_names and not name.startswith('_'):
                unused.append((name, lineno))
        return sorted(unused, key=lambda x: x[1])


def fix_file(filepath: Path) -> Dict[str, int]:
    """Fix issues in a single file. Returns stats."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            original_content = f.read()
    except Exception as e:
        return {'error': 1}
    
    content = original_content
    fixes = {'unused_imports': 0, 'silent_exceptions': 0, 'print_statements': 0}
    
    # Step 1: Find and remove unused imports
    try:
        tree = ast.parse(content)
        tracker = ImportTracker()
        tracker.visit(tree)
        unused = tracker.get_unused_imports()
        
        # Remove unused imports line by line
        lines = content.split('\n')
        lines_to_remove = set()
        
        for name, lineno in unused:
            # Check if this line only contains this import
            line_idx = lineno - 1
            if line_idx < len(lines):
                line = lines[line_idx]
                # Simple pattern matching for import removal
                if f'import {name}' in line or f'import {name},' in line or f'{name},' in line:
                    # Check if removing this import would leave the line empty or with other imports
                    remaining = line.replace(f'import {name}', '').replace(f'{name},', '').replace(f', {name}', '').strip()
                    if not remaining or remaining == 'import' or remaining == 'from':
                        lines_to_remove.add(line_idx)
                    else:
                        # Just remove this specific import from the line
                        lines[line_idx] = re.sub(rf'\bimport\s+{name}\b(,\s*)?|,\s*{name}\b|{name}\s*,\s*', '', lines[line_idx])
                        fixes['unused_imports'] += 1
        
        # Remove entire lines that are now empty import lines
        new_lines = []
        for i, line in enumerate(lines):
            if i not in lines_to_remove:
                new_lines.append(line)
            elif line.strip() and not line.strip().startswith('#'):
                # Keep non-empty, non-comment lines
                new_lines.append(line)
        
        content = '\n'.join(new_lines)
        fixes['unused_imports'] += len(lines_to_remove)
        
    except Exception as e:
        print(f"⚠️  Error analyzing imports in {filepath}: {e}")
    
    # Step 2: Replace silent exception handlers with logging
    # Pattern: except Exception: pass or except: pass
    patterns = [
        (r'(\s+)except Exception:\s*pass\s*(?=\n|$)', r'\1except Exception as e:\n\1    logger.warning("Silent exception caught: %s", e)'),
        (r'(\s+)except:\s*pass\s*(?=\n|$)', r'\1except Exception as e:\n\1    logger.warning("Bare exception caught: %s", e)'),
    ]
    
    for pattern, replacement in patterns:
        matches = re.findall(pattern, content)
        if matches:
            content = re.sub(pattern, replacement, content)
            fixes['silent_exceptions'] += len(matches)
    
    # Step 3: Replace print() statements with logger (only in non-CLI files)
    if 'cli' not in str(filepath) and '__main__' not in str(filepath):
        print_pattern = r'(\s*)print\((.*?)\)'
        matches = re.findall(print_pattern, content)
        if matches:
            # Add logger import if not present
            if 'import logging' not in content and 'from logging' not in content:
                # Find a good place to add the import
                lines = content.split('\n')
                insert_idx = 0
                for i, line in enumerate(lines):
                    if line.startswith('import ') or line.startswith('from '):
                        insert_idx = i + 1
                lines.insert(insert_idx, 'import logging\n')
                content = '\n'.join(lines)
            
            # Replace print with logger.debug
            content = re.sub(r'(\s*)print\((.*?)\)', r'\1logger.debug(\2)', content)
            fixes['print_statements'] = len(matches)
    
    # Write back if changes were made
    if content != original_content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
    
    return fixes


def main():
    nexus_dir = Path('/workspace/NexusAgent/nexus')
    all_stats = {'total_files': 0, 'fixed_files': 0, **{k: 0 for k in ['unused_imports', 'silent_exceptions', 'print_statements', 'error']}}
    
    print("=" * 80)
    print("🔧 CORRECTION AUTOMATIQUE DES PROBLÈMES DE PRODUCTION")
    print("=" * 80)
    
    for py_file in nexus_dir.rglob('*.py'):
        if 'test' in str(py_file) or '__pycache__' in str(py_file):
            continue
        
        all_stats['total_files'] += 1
        stats = fix_file(py_file)
        
        if any(v > 0 for k, v in stats.items() if k != 'error'):
            all_stats['fixed_files'] += 1
            rel_path = py_file.relative_to(nexus_dir)
            print(f"\n✅ {rel_path}")
            for issue_type, count in stats.items():
                if count > 0:
                    print(f"   • {issue_type.replace('_', ' ').title()}: {count}")
        elif stats.get('error'):
            all_stats['error'] += 1
    
    print("\n" + "=" * 80)
    print("📊 RÉSUMÉ DES CORRECTIONS")
    print("=" * 80)
    print(f"Fichiers analysés: {all_stats['total_files']}")
    print(f"Fichiers corrigés: {all_stats['fixed_files']}")
    print(f"Imports inutilisés supprimés: {all_stats['unused_imports']}")
    print(f"Exceptions silencieuses corrigées: {all_stats['silent_exceptions']}")
    print(f"Print statements remplacés: {all_stats['print_statements']}")
    if all_stats['error']:
        print(f"Erreurs: {all_stats['error']}")
    print("=" * 80)


if __name__ == '__main__':
    main()
