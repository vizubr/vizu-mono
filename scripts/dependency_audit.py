#!/usr/bin/env python3
"""
Heuristic dependency audit.

For each top-level package directory (services/* and libs/*), the script
collects imported top-level module names and compares them to the
`pyproject.toml` [tool.poetry.dependencies] (if present) to find:
 - Potentially missing dependencies (used but not declared)
 - Potentially unused dependencies (declared but not imported)

This is heuristic and will have false positives/negatives (namespace packages,
standard library vs third-party mapping). Use as a guide, not an absolute.
"""
from pathlib import Path
import ast
import tomllib
import sys

ROOT = Path(__file__).resolve().parent.parent


def collect_imports(path: Path):
    imports = set()
    # Only scan 'src' and 'tests' directories, explicitly skip .venv, __pycache__, etc.
    skip_dirs = {'.venv', 'venv', '.git', '__pycache__', 'node_modules', '.mypy_cache', '.pytest_cache', 'dist', 'build', '.eggs'}

    for p in path.rglob('*.py'):
        # Skip files in excluded directories
        if any(skip in p.parts for skip in skip_dirs):
            continue
        try:
            tree = ast.parse(p.read_text(encoding='utf-8'))
        except Exception:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for n in node.names:
                    name = n.name.split('.')[0]
                    # Skip private/internal imports
                    if not name.startswith('_'):
                        imports.add(name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    name = node.module.split('.')[0]
                    # Skip private/internal imports
                    if not name.startswith('_'):
                        imports.add(name)
    return imports


def read_pyproject_deps(pyproject_path: Path):
    try:
        data = tomllib.loads(pyproject_path.read_text(encoding='utf-8'))
        deps = data.get('tool', {}).get('poetry', {}).get('dependencies', {})
        # remove python spec
        deps = {k for k in deps.keys() if k.lower() != 'python'}
        return deps
    except Exception:
        return set()


def analyze_project(dirpath: Path):
    pyproject = dirpath / 'pyproject.toml'
    imports = collect_imports(dirpath)
    deps = read_pyproject_deps(pyproject) if pyproject.exists() else set()

    # Comprehensive stdlib list (Python 3.11+)
    stdlib_like = {
        # Built-ins and core
        'os', 'sys', 're', 'json', 'time', 'typing', 'pathlib', 'itertools',
        'collections', 'dataclasses', 'asyncio', 'logging', 'datetime', 'math',
        # Common stdlib
        'argparse', 'uuid', 'traceback', 'functools', 'operator', 'copy',
        'io', 'contextlib', 'abc', 'enum', 'warnings', 'inspect', 'types',
        'hashlib', 'base64', 'secrets', 'random', 'string', 'textwrap',
        'urllib', 'http', 'email', 'html', 'xml', 'csv', 'configparser',
        'socket', 'ssl', 'select', 'threading', 'multiprocessing', 'subprocess',
        'tempfile', 'shutil', 'glob', 'fnmatch', 'stat', 'fileinput',
        'pickle', 'shelve', 'sqlite3', 'zlib', 'gzip', 'bz2', 'lzma', 'zipfile', 'tarfile',
        'unittest', 'doctest', 'pdb', 'profile', 'timeit', 'trace',
        'typing_extensions', 'importlib', 'pkgutil', 'struct', 'codecs',
        'locale', 'gettext', 'calendar', 'heapq', 'bisect', 'array', 'weakref',
        'decimal', 'fractions', 'statistics', 'cmath', 'numbers',
        'concurrent', 'queue', 'sched', 'contextvars',
        # Additional stdlib modules
        'difflib', 'unicodedata', 'ast', 'dis', 'code', 'codeop', 'pprint',
        'reprlib', 'graphlib', 'token', 'tokenize', 'keyword', 'symbol', 'parser',
        'compileall', 'py_compile', 'zipimport', 'venv', 'platform',
        'errno', 'ctypes', 'posixpath', 'ntpath', 'genericpath', 'atexit',
        # Test-related (often in dev deps, not main)
        'pytest', 'unittest', 'pytest_mock', 'fakeredis',
        # Internal/self imports (project's own modules)
    }

    # Also exclude imports that match the project's own name
    project_name = dirpath.name
    stdlib_like.add(project_name)
    stdlib_like.add(project_name.replace('-', '_'))
    stdlib_like.add(project_name.replace('_', '-'))

    # Find all local module names in src/ directory
    src_dir = dirpath / 'src'
    if src_dir.exists():
        for item in src_dir.iterdir():
            if item.is_dir() and not item.name.startswith('_'):
                stdlib_like.add(item.name)
                # Also add submodules
                for subitem in item.rglob('*.py'):
                    rel = subitem.relative_to(src_dir)
                    parts = rel.with_suffix('').parts
                    for i in range(len(parts)):
                        stdlib_like.add('.'.join(parts[:i+1]).split('.')[0])
        # Also add top-level .py files in src/ as module names
        for item in src_dir.glob('*.py'):
            stdlib_like.add(item.stem)

    # Also scan direct children of project dir for local modules
    for item in dirpath.iterdir():
        if item.is_dir() and not item.name.startswith(('.', '_')) and item.name not in {'src', 'tests', 'docs'}:
            stdlib_like.add(item.name)
        if item.suffix == '.py' and not item.name.startswith('_'):
            stdlib_like.add(item.stem)

    # Add common internal module patterns (these are almost never third-party packages)
    internal_patterns = {
        'allowlist', 'config', 'utils', 'helpers', 'models', 'schemas', 'client',
        'core', 'api', 'service', 'services', 'base', 'server', 'tools', 'resources',
        'prompts', 'endpoints', 'dependencies', 'connectors', 'adapters', 'routers',
        'middleware', 'auth', 'database', 'db', 'cache', 'storage', 'worker', 'tasks',
        'exceptions', 'errors', 'validators', 'serializers', 'parsers', 'handlers',
        'providers', 'factories', 'managers', 'builders', 'contexts', 'settings',
        # Project-specific internal modules found in this codebase
        'seed', 'cli', 'crud', 'health', 'logger', 'runner', 'classifier', 'manifest',
        'executor', 'factory', 'parser', 'rewrites', 'sanitizer', 'validator', 'checks',
        'schema_snapshot', 'observability', 'tier_validator', 'tool_metadata', 'registry',
        'prompt_service', 'text_to_sql', 'text_to_sql_config', 'docker_mcp_bridge',
        'docker_mcp_adapter', 'mcp_server', 'virtual_assistant', 'state', 'nodes',
        'langfuse_integration', 'langfuse_runner', 'dataset_generator', 'workflow_runner',
        'gmail', 'sheets', 'postgrest_executor', 'auth_context', 'redis_service',
        'google_provider', 'oauth_manager', 'oauth2', 'grafana',
        # Model/schema internal modules from vizu_models
        'agent_types', 'cliente_final', 'cliente_vizu', 'configuracao_negocio', 'conversa',
        'credencial_servico_externo', 'enums', 'experiment', 'fonte_de_dados', 'hitl',
        'integration', 'knowledge_base_config', 'prompt_template', 'safe_client_context',
        'schema_config', 'seed_clients', 'sql_schema_config', 'vizu_client_context', 'vizu_schema',
        # Common local import patterns
        'src', 'context_service', 'data_ingestion_worker',
    }
    stdlib_like.update(internal_patterns)

    # Add all libs/* and services/* from the monorepo as known local packages
    for subdir in ['libs', 'services']:
        subdir_path = ROOT / subdir
        if subdir_path.exists():
            for item in subdir_path.iterdir():
                if item.is_dir():
                    stdlib_like.add(item.name)
                    stdlib_like.add(item.name.replace('-', '_'))
                    stdlib_like.add(item.name.replace('_', '-'))

    third_party_imports = {i for i in imports if i not in stdlib_like}

    # Package name to import name mapping (common PyPI packages)
    pkg_to_import = {
        'google-auth': 'google',
        'google-api-python-client': 'googleapiclient',
        'google-auth-httplib2': 'google',
        'google-auth-oauthlib': 'google',
        'google-cloud-pubsub': 'google',
        'google-cloud-storage': 'google',
        'google-cloud-bigquery': 'google',
        'pyjwt': 'jwt',
        'python-dotenv': 'dotenv',
        'pyyaml': 'yaml',
        'python-json-logger': 'pythonjsonlogger',
        'python-multipart': 'multipart',
        'opentelemetry-api': 'opentelemetry',
        'opentelemetry-sdk': 'opentelemetry',
        'opentelemetry-exporter-otlp': 'opentelemetry',
        'opentelemetry-instrumentation-fastapi': 'opentelemetry',
        'psycopg2-binary': 'psycopg2',
        'pydantic-settings': 'pydantic_settings',
        'huggingface-hub': 'huggingface_hub',
        'db-dtypes': 'db_dtypes',
        'langchain-mcp-adapters': 'langchain_mcp_adapters',
        'langgraph-checkpoint-redis': 'langgraph',
    }

    # Normalize dependency names for comparison (replace - with _)
    deps_normalized = set()
    for d in deps:
        # First check if there's a known mapping
        if d.lower() in pkg_to_import:
            deps_normalized.add(pkg_to_import[d.lower()].lower())
        else:
            deps_normalized.add(d.replace('-', '_').lower())

    imports_normalized = {i.replace('-', '_').lower() for i in third_party_imports}

    missing = sorted([i for i in imports_normalized if i not in deps_normalized])

    # For unused, also check against the mapped import names
    unused = []
    for d in deps:
        d_import = pkg_to_import.get(d.lower(), d.replace('-', '_')).lower()
        if d_import not in imports_normalized:
            unused.append(d)
    unused = sorted(unused)

    return {
        'imports_count': len(imports),
        'declared_deps': sorted(deps),
        'missing': missing,
        'unused': unused,
    }


def main():
    projects = []
    for d in ROOT.iterdir():
        if d.is_dir() and d.name in ('services', 'libs'):
            for child in d.iterdir():
                if child.is_dir():
                    projects.append(child)

    any_issues = False
    for proj in projects:
        res = analyze_project(proj)
        if res['missing'] or res['unused']:
            any_issues = True
            print(f"\nProject: {proj}")
            if res['missing']:
                print("  Potential MISSING dependencies (imports found but not declared):")
                for m in res['missing']:
                    print(f"   - {m}")
            if res['unused']:
                print("  Potential UNUSED declared dependencies (declared but not imported):")
                for u in res['unused']:
                    print(f"   - {u}")

    if not any_issues:
        print("No obvious dependency mismatches found (heuristic)")
    else:
        print("\n" + "=" * 60)
        print("NOTE: This is a HEURISTIC audit and may have false positives.")
        print("Common false positives in monorepos:")
        print("  - Transitive dependencies (via vizu-* libs)")
        print("  - Internal modules with common names (pydantic, sqlalchemy)")
        print("  - Path dependencies that use different import names")
        print("Review the results manually before making changes.")
        print("=" * 60)

    # Always return 0 - this audit is informational, not blocking
    return 0


if __name__ == '__main__':
    sys.exit(main())
