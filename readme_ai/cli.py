"""CLI entry point for readme-ai."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Confirm

from readme_ai import __version__
from readme_ai.analyzer import ProjectAnalyzer
from readme_ai.builder import ReadmeBuilder
from readme_ai.llm import get_llm_client
from readme_ai.sampler import CodeSampler

app = typer.Typer(
    name="readme-ai",
    help="Generate beautiful READMEs from your actual code, not templates.",
    add_completion=False,
    rich_markup_mode="rich",
)
console = Console()


def version_callback(value: bool) -> None:
    if value:
        console.print(f"readme-ai version [bold cyan]{__version__}[/bold cyan]")
        raise typer.Exit()


@app.callback()
def main(
    version: Optional[bool] = typer.Option(
        None,
        "--version", "-v",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit",
    ),
) -> None:
    """readme-ai — Generate beautiful READMEs from your actual code, not templates."""
    pass


@app.command()
def analyze(
    repo: str = typer.Argument(
        ...,
        help="Path to local repo or GitHub URL (e.g. https://github.com/user/repo)",
    ),
    output: Path = typer.Option(
        Path("README.md"),
        "--output", "-o",
        help="Output file path",
    ),
    provider: str = typer.Option(
        "openai",
        "--provider", "-p",
        help="LLM provider: openai | anthropic | ollama",
    ),
    model: Optional[str] = typer.Option(
        None,
        "--model", "-m",
        help="Model name (defaults to provider's recommended model)",
    ),
    api_key: Optional[str] = typer.Option(
        None,
        "--api-key",
        envvar=["OPENAI_API_KEY", "ANTHROPIC_API_KEY"],
        help="API key (or set via environment variable)",
    ),
    ollama_host: str = typer.Option(
        "http://localhost:11434",
        "--ollama-host",
        help="Ollama host URL",
    ),
    overwrite: bool = typer.Option(
        False,
        "--overwrite", "-y",
        help="Overwrite existing README without asking",
    ),
) -> None:
    """
    [bold]Analyze a repository and generate a README.[/bold]

    Examples:

        readme-ai analyze ./my-project

        readme-ai analyze https://github.com/user/repo

        readme-ai analyze . --provider anthropic
    """
    console.print(
        Panel.fit(
            "[bold cyan]readme-ai[/bold cyan] — Generating your README from actual code",
            border_style="cyan",
        )
    )

    if output.exists() and not overwrite:
        if not Confirm.ask(f"[yellow]{output}[/yellow] already exists. Overwrite?"):
            console.print("Aborted.")
            raise typer.Exit()

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
            transient=False,
        ) as progress:

            task = progress.add_task("Analyzing project structure...", total=None)
            analyzer = ProjectAnalyzer(repo)
            project_info = analyzer.analyze()
            progress.update(task, description=f"[green]✓[/green] Found: {project_info.name} ({project_info.language})")
            progress.stop_task(task)

            task2 = progress.add_task("Sampling code for context...", total=None)
            sampler = CodeSampler(analyzer.repo_path)
            code_samples = sampler.sample()
            progress.update(task2, description=f"[green]✓[/green] Sampled {len(code_samples)} files")
            progress.stop_task(task2)

            task3 = progress.add_task(f"Generating README with {provider}...", total=None)
            llm = get_llm_client(
                provider=provider,
                model=model,
                api_key=api_key,
                ollama_host=ollama_host,
            )
            generated = llm.generate(project_info, code_samples)
            progress.update(task3, description="[green]✓[/green] Content generated")
            progress.stop_task(task3)

            task4 = progress.add_task("Building README...", total=None)
            builder = ReadmeBuilder(project_info)
            readme_content = builder.build(generated)
            progress.update(task4, description="[green]✓[/green] README built")
            progress.stop_task(task4)

        output.write_text(readme_content, encoding="utf-8")
        console.print(f"\n[bold green]✓ README saved to {output}[/bold green]")
        console.print("\n[dim]Tip: review and tweak the generated README before publishing.[/dim]\n")

    except KeyboardInterrupt:
        console.print("\n[yellow]Cancelled.[/yellow]")
        sys.exit(0)
    except Exception as e:
        console.print(f"\n[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1) from e


@app.command()
def preview(
    readme: Path = typer.Argument(Path("README.md"), help="README file to preview"),
) -> None:
    """Preview a README file in the terminal."""
    from rich.markdown import Markdown

    if not readme.exists():
        console.print(f"[red]File not found:[/red] {readme}")
        raise typer.Exit(1)

    content = readme.read_text(encoding="utf-8")
    console.print(Markdown(content))


if __name__ == "__main__":
    app()
