"""Read-only source inventory, not a Mongo data export or migration tool."""
import ast
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def collection(node):
    if isinstance(node, ast.Attribute) and ast.unparse(node.value) in ('db', 'self.db'):
        return node.attr
    if isinstance(node, ast.Subscript) and ast.unparse(node.value) in ('db', 'self.db'):
        if isinstance(node.slice, ast.Constant):
            return node.slice.value
    return None


def inventory():
    rows = defaultdict(lambda: {'calls': [], 'fields': set(), 'indexes': [], 'transactions': []})
    dynamic = []
    for path in sorted(ROOT.rglob('*.py')):
        if any(p in ('tests', 'db', 'scripts', '__pycache__') for p in path.relative_to(ROOT).parts):
            continue
        if path.name == 'server_partial.py':
            continue
        tree = ast.parse(path.read_text(encoding='utf-8-sig'))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                continue
            name = collection(node.func.value)
            location = f'{path.relative_to(ROOT).as_posix()}:{node.lineno}'
            if name is None:
                if isinstance(node.func.value, ast.Subscript) and ast.unparse(node.func.value.value) in ('db', 'self.db'):
                    dynamic.append({'location': location, 'expression': ast.unparse(node)})
                continue
            row = rows[name]
            row['calls'].append({'location': location, 'operation': node.func.attr})
            for arg in node.args:
                if isinstance(arg, ast.Dict):
                    for child in ast.walk(arg):
                        if isinstance(child, ast.Dict):
                            row['fields'].update(k.value for k in child.keys if isinstance(k, ast.Constant) and isinstance(k.value, str) and not k.value.startswith('$'))
            if any(k.arg == 'session' for k in node.keywords):
                row['transactions'].append(location)
            if node.func.attr == 'create_index':
                row['indexes'].append(ast.unparse(node))
    return {'collections': {k: {**v, 'fields': sorted(v['fields'])} for k,v in sorted(rows.items())},
            'dynamic_calls_to_resolve': dynamic,
            'gridfs': 'edital_inputs.files + edital_inputs.chunks (edital_jobs.py)',
            'legacy_candidate': 'server_partial.py (verify no imports before removal)'}


if __name__ == '__main__':
    target = ROOT.parent / 'docs' / 'database-inventory.json'
    target.write_text(json.dumps(inventory(), ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'Written {target.name}; no database connection was opened.')
