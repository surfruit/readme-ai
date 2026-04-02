"""Standalone test runner — no pytest needed."""
import sys, json, tempfile, shutil, types
from pathlib import Path

sys.path.insert(0, '/home/claude/readme-ai')

# ── Patch missing third-party deps ──────────────────────────────────────────
def _mock(name):
    m = types.ModuleType(name)
    sys.modules[name] = m
    return m

for name in ['typer', 'httpx', 'gitpython', 'git', 'toml', 'jinja2', 'pathspec']:
    if name not in sys.modules:
        _mock(name)

# rich
rich = _mock('rich')
for sub in ['console', 'panel', 'progress', 'prompt', 'markdown', 'text']:
    mod = _mock(f'rich.{sub}')
    for cls in ['Console', 'Panel', 'Progress', 'SpinnerColumn', 'TextColumn',
                'Confirm', 'Markdown', 'Prompt', 'Text']:
        setattr(mod, cls, type(cls, (), {'__init__': lambda s, *a, **k: None,
                                          '__enter__': lambda s: s,
                                          '__exit__': lambda s, *a: None}))

class pytest_like_raises:
    def __init__(self, exc): self.exc = exc
    def __enter__(self): return self
    def __exit__(self, et, ev, tb):
        if et is None: raise AssertionError(f"Expected {self.exc.__name__} not raised")
        if issubclass(et, self.exc): return True

from readme_ai.analyzer import ProjectAnalyzer, ProjectInfo
from readme_ai.sampler import CodeSampler
from readme_ai.builder import ReadmeBuilder
from readme_ai.badges import generate_badges
from readme_ai.llm.base import GeneratedContent, BaseLLMClient, build_user_prompt

PASS = "\033[32mPASS\033[0m"
FAIL = "\033[31mFAIL\033[0m"
failed = []

def ok(msg): print(f"  {PASS}  {msg}")
def fail(msg, err):
    print(f"  {FAIL}  {msg}: {err}")
    failed.append(msg)

# ── Build a fake repo ────────────────────────────────────────────────────────
tmp = Path(tempfile.mkdtemp())
(tmp / 'myapp').mkdir()
(tmp / 'myapp' / 'cli.py').write_text(
    '"""CLI entry point."""\nimport typer\napp = typer.Typer()\n\n'
    '@app.command()\ndef run(verbose: bool = False):\n    """Run the app."""\n    pass\n'
)
(tmp / 'myapp' / '__init__.py').write_text('__version__ = "0.1.0"\n')
(tmp / 'pyproject.toml').write_bytes(
    b'[project]\nname="myapp"\ndescription="A cool app"\n'
    b'requires-python=">=3.10"\ndependencies=["httpx>=0.25","typer>=0.9"]\n\n'
    b'[project.scripts]\nmyapp="myapp.cli:app"\n'
)
(tmp / 'tests').mkdir()
(tmp / 'tests' / 'test_cli.py').write_text('def test_placeholder(): assert True\n')
(tmp / 'Dockerfile').write_text('FROM python:3.11-slim\n')
(tmp / '.env.example').write_text('DATABASE_URL=postgres://localhost\nSECRET_KEY=changeme\n')
(tmp / 'LICENSE').write_text('MIT License\nCopyright (c) 2024\n')

# ── TEST 1: Analyzer ─────────────────────────────────────────────────────────
print("\n── Analyzer ──")
try:
    analyzer = ProjectAnalyzer(str(tmp))
    info = analyzer.analyze()
    assert info.language == 'Python', f'language={info.language}'
    ok('detected language: Python')
except Exception as e: fail('language detection', e)

try:
    assert 'httpx' in info.dependencies, f'deps={info.dependencies}'
    assert 'typer' in info.dependencies
    ok(f'parsed dependencies: {info.dependencies}')
except Exception as e: fail('dependency parsing', e)

try:
    assert info.has_tests and info.has_docker
    ok('detected tests and Docker')
except Exception as e: fail('feature detection', e)

try:
    assert info.license_type == 'MIT', f'license={info.license_type}'
    ok('detected license: MIT')
except Exception as e: fail('license detection', e)

try:
    assert 'DATABASE_URL' in info.env_vars and 'SECRET_KEY' in info.env_vars
    ok(f'parsed env vars: {info.env_vars}')
except Exception as e: fail('env var parsing', e)

try:
    assert info.description == 'A cool app', f'desc={info.description}'
    ok('parsed description from pyproject.toml')
except Exception as e: fail('description', e)

try:
    assert 'myapp' in info.entry_points
    ok(f'detected entry points: {info.entry_points}')
except Exception as e: fail('entry points', e)

try:
    assert len(info.file_tree) > 20
    ok('built file tree')
except Exception as e: fail('file tree', e)

try:
    with pytest_like_raises(FileNotFoundError):
        ProjectAnalyzer('/nonexistent/xyz').analyze()
    ok('raises FileNotFoundError for missing path')
except Exception as e: fail('invalid path handling', e)

# ── TEST 2: Sampler ──────────────────────────────────────────────────────────
print("\n── CodeSampler ──")
try:
    sampler = CodeSampler(tmp)
    samples = sampler.sample()
    assert len(samples) > 0
    paths = [s.path for s in samples]
    assert any('cli.py' in p for p in paths), f'paths={paths}'
    ok(f'sampled {len(samples)} files, includes cli.py')
except Exception as e: fail('basic sampling', e)

try:
    assert not any('.git' in s.path for s in samples)
    ok('skips .git directory')
except Exception as e: fail('skip .git', e)

try:
    total = sum(len(s.content.encode()) for s in samples)
    assert total <= 44_000, f'total={total}'
    ok(f'within budget: {total:,} bytes')
except Exception as e: fail('budget limit', e)

try:
    paths = [s.path for s in samples]
    cli_idx = next((i for i, p in enumerate(paths) if 'cli.py' in p), 999)
    test_idx = next((i for i, p in enumerate(paths) if 'test_' in p), 999)
    assert cli_idx < test_idx, f'cli at {cli_idx}, test at {test_idx}'
    ok('cli.py ranked higher than test files')
except Exception as e: fail('priority ordering', e)

# ── TEST 3: ReadmeBuilder ────────────────────────────────────────────────────
print("\n── ReadmeBuilder ──")
generated = GeneratedContent(
    tagline='A blazing CLI tool for developers',
    description='myapp is a CLI that does amazing things for developers.',
    features=['Fast', 'Reliable', 'Zero config', 'Multi-provider'],
    installation='```bash\npip install myapp\n```',
    quick_start='```bash\nmyapp run\n```',
    usage_examples='```bash\nmyapp run --verbose\n```',
    api_overview='| Command | Description |\n|---|---|\n| `run` | Run the app |',
    configuration='Set DATABASE_URL in your environment.',
    roadmap=['Plugin system', 'Web UI', 'Notion export'],
)

try:
    builder = ReadmeBuilder(info)
    readme = builder.build(generated)
    assert isinstance(readme, str) and len(readme) > 200
    ok(f'built README: {len(readme):,} chars')
except Exception as e: fail('build', e)

try:
    assert 'myapp' in readme
    assert 'A blazing CLI tool for developers' in readme
    ok('contains name and tagline')
except Exception as e: fail('name/tagline', e)

try:
    for f in generated.features:
        assert f in readme, f'missing feature: {f}'
    ok('all features present')
except Exception as e: fail('features', e)

try:
    assert 'DATABASE_URL' in readme and 'SECRET_KEY' in readme
    ok('env vars table present')
except Exception as e: fail('env vars in README', e)

try:
    assert '- [ ] Plugin system' in readme
    assert '- [ ] Web UI' in readme
    ok('roadmap checkboxes present')
except Exception as e: fail('roadmap', e)

try:
    assert 'Table of Contents' in readme
    ok('table of contents present')
except Exception as e: fail('TOC', e)

try:
    assert 'readme-ai' in readme
    ok('watermark present')
except Exception as e: fail('watermark', e)

# ── TEST 4: Badges ───────────────────────────────────────────────────────────
print("\n── Badges ──")
try:
    badges = generate_badges(info)
    assert 'Python' in badges and 'img.shields.io' in badges
    ok('language badge generated')
except Exception as e: fail('language badge', e)

try:
    assert 'MIT' in badges
    ok('license badge generated')
except Exception as e: fail('license badge', e)

try:
    assert 'PRs' in badges
    ok('PRs welcome badge generated')
except Exception as e: fail('PRs badge', e)

# ── TEST 5: LLM base ─────────────────────────────────────────────────────────
print("\n── LLM Base ──")
class DummyLLM(BaseLLMClient):
    def generate(self, *a): pass

llm = DummyLLM()

try:
    raw = json.dumps({'tagline':'Cool','description':'d','features':['A','B'],
                      'installation':'pip','quick_start':'run',
                      'usage_examples':'','api_overview':'',
                      'configuration':'','roadmap':['f1']})
    r = llm._parse_response(raw)
    assert r.tagline == 'Cool' and r.features == ['A','B'] and r.roadmap == ['f1']
    ok('parses valid JSON')
except Exception as e: fail('parse JSON', e)

try:
    fenced = '```json\n' + raw + '\n```'
    r2 = llm._parse_response(fenced)
    assert r2.tagline == 'Cool'
    ok('strips markdown code fences')
except Exception as e: fail('strip fences', e)

try:
    raised = False
    try:
        llm._parse_response('not json {{{')
    except ValueError:
        raised = True
    assert raised
    ok('raises ValueError on invalid JSON')
except Exception as e: fail('invalid JSON handling', e)

# ── TEST 6: Prompt builder ───────────────────────────────────────────────────
print("\n── Prompt Builder ──")
try:
    prompt = build_user_prompt(info, samples)
    assert 'Python' in prompt and 'myapp' in prompt
    assert 'DATABASE_URL' in prompt
    ok('prompt contains project name, language, env vars')
except Exception as e: fail('prompt content', e)

# ── Summary ──────────────────────────────────────────────────────────────────
shutil.rmtree(tmp)
print()
if failed:
    print(f"\033[31m{len(failed)} test(s) failed:\033[0m {', '.join(failed)}")
    sys.exit(1)
else:
    print(f"\033[32mAll tests passed.\033[0m")



