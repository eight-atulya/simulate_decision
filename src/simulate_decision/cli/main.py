from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any

import requests
import typer
from anyio import run as anyio_run
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.syntax import Syntax
from rich.table import Table
from rich.tree import Tree

from simulate_decision.core import (
    EngineConfig,
    PipelineTemplates,
    SimulateDecision,
    Storage,
    get_config,
)
from simulate_decision.core.story_templates import StoryPipelineTemplates

try:
    from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, TextBlock, query
    from claude_agent_sdk._errors import CLINotFoundError
    CLAUDE_SDK_AVAILABLE = True
except ImportError:
    CLAUDE_SDK_AVAILABLE = False

app = typer.Typer(
    name="simulatedecision",
    help="Decision Simulator - AI-Powered Decision Analysis Engine",
    add_completion=False,
)
console = Console()


@app.command()
def analyze(
    concept: Annotated[str, typer.Argument(help="The concept to analyze")],
    iterations: Annotated[
        int,
        typer.Option("--iterations", "-i", help="Maximum optimization iterations"),
    ] = 3,
    lm_url: Annotated[
        str,
        typer.Option("--lm-url", help="LM Studio URL"),
    ] = "",
    model: Annotated[
        str,
        typer.Option("--model", "-m", help="Model name"),
    ] = "",
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Enable verbose output"),
    ] = False,
    no_save: Annotated[
        bool,
        typer.Option("--no-save", help="Don't save result to history"),
    ] = False,
    html: Annotated[
        str | None,
        typer.Option("--html", help="Export result to HTML file"),
    ] = None,
    pipeline: Annotated[
        str,
        typer.Option("-p", "--pipeline", help="Pipeline template (basic, standard, full, synthesis, iterative, user_story, business_analysis, technical_story, problem_decomposition, decision_framework)"),
    ] = "standard",
) -> None:
    """Analyze a concept using the SimulateDecision policy-driven engine."""
    config = get_config()

    if lm_url:
        config.lm_studio_url = lm_url
    if model:
        config.model_name = model

    config.configure_dspy()

    console.print(Panel.fit(f"[bold cyan]SimulateDecision Analysis[/bold cyan]\n{concept}"))
    console.print(f"[dim]Pipeline: {pipeline}[/dim]")

    try:
        template = PipelineTemplates.get(pipeline)
        if template:
            pipeline_config = PipelineTemplates.create_config(pipeline, max_iterations=iterations)
        else:
            template = StoryPipelineTemplates.get(pipeline)
            if template:
                pipeline_config = StoryPipelineTemplates.create_config(pipeline, max_iterations=iterations)
            else:
                console.print(f"[red]Unknown template: {pipeline}[/red]")
                available = [t["name"] for t in PipelineTemplates.list_templates()] + [t["name"] for t in StoryPipelineTemplates.list_templates()]
                console.print(f"[yellow]Available: {', '.join(available)}[/yellow]")
                raise typer.Exit(code=1)

        engine = SimulateDecision(config=config, pipeline_config=pipeline_config)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Processing concept...", total=None)
            result = engine(concept, save_result=not no_save)
            progress.update(task, completed=True)

        if result["status"] == "SUCCESS":
            _display_success(result, verbose)
            if html:
                _export_html(result, Path(html))
        else:
            _display_failure(result)
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1) from e


@app.command()
def ai(
    prompt: Annotated[str, typer.Argument(help="Ask AI anything")],
    model: Annotated[
        str,
        typer.Option("--model", "-m", help="Model name (for LM Studio)"),
    ] = "",
    local: Annotated[
        bool,
        typer.Option("--local", "-l", help="Use local model via LM Studio"),
    ] = False,
) -> None:
    """Ask AI for help - uses cloud Claude or local LM Studio!"""

    config = get_config()

    if local:
        url = f"{config.lm_studio_url}/chat/completions"
        model_name = model if model else config.model_name.replace("lmstudio/", "")
        headers = {"Content-Type": "application/json"}
        data = {
            "model": model_name,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 2048,
            "stream": False
        }

        console.print(f"[dim]Using LM Studio: {model_name}[/dim]")

        try:
            response = requests.post(url, json=data, headers=headers, timeout=120)
            response.raise_for_status()
            result = response.json()
            content = result["choices"][0]["message"]["content"]
            console.print(Panel.fit(content, title="Response"))
        except requests.exceptions.RequestException as e:
            console.print(f"[bold red]Error:[/bold red] {e}")
            raise typer.Exit(code=1)

    elif not CLAUDE_SDK_AVAILABLE:
        console.print("[bold red]Claude Agent SDK not installed.[/bold red]")
        console.print("Using local mode instead: SimulateDecision ai 'prompt' --local")
        raise typer.Exit(code=1)

    else:
        model = model or "sonnet"
        console.print(Panel.fit(f"[bold cyan]🤖 AI Assistant[/bold cyan]\n{prompt}"))

        options = ClaudeAgentOptions(
            model=model,
            max_turns=10,
        )

        async def run_query():
            accumulated = ""
            async for message in query(prompt=prompt, options=options):
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            accumulated += block.text
                elif isinstance(message, str):
                    print(message, end="")
            return accumulated

        try:
            result = anyio_run(run_query)
            if result:
                console.print(Panel.fit(result, title="Response"))
        except CLINotFoundError:
            console.print("[bold red]Claude Code not found.[/bold red]")
            console.print("Using local mode: SimulateDecision ai 'prompt' --local")
            raise typer.Exit(code=1)
        except Exception as e:
            console.print(f"[bold red]Error:[/bold red] {e}")
            raise typer.Exit(code=1)


@app.command()
def history(
    limit: Annotated[
        int,
        typer.Option("--limit", "-n", help="Number of history entries to show"),
    ] = 10,
    concept: Annotated[
        str | None,
        typer.Option("--concept", "-c", help="Filter by concept"),
    ] = None,
    show_meta: Annotated[
        bool,
        typer.Option("--meta", "-m", help="Show metadata (tokens, model)"),
    ] = False,
) -> None:
    """Show the history of analysis results."""
    storage = Storage()
    records = storage.get_all()

    if concept:
        records = [r for r in records if concept.lower() in r.get("concept", "").lower()]

    records = records[-limit:] if limit > 0 else records

    if not records:
        console.print("[yellow]No history found.[/yellow]")
        return

    table = Table(title=f"Analysis History ({len(records)} entries)")
    table.add_column("Time", style="cyan", no_wrap=True)
    table.add_column("Concept", style="green")
    table.add_column("Status", style="yellow")
    table.add_column("Iter", justify="right")
    if show_meta:
        table.add_column("Tokens", justify="right", style="dim")
        table.add_column("Model", style="dim")

    for record in reversed(records):
        timestamp = record.get("timestamp", "unknown")
        if "T" in timestamp:
            timestamp = timestamp.split("T")[1].split(".")[0]

        meta = record.get("metadata", {})
        table.add_row(
            timestamp,
            record.get("concept", ""),
            record.get("status", ""),
            str(record.get("iterations", "-")),
        )
        if show_meta:
            table.add_row(
                "",
                "",
                "",
                str(meta.get("total_tokens_used", "-")),
                meta.get("model_name", "-")[:20] if meta.get("model_name") else "-",
            )

    console.print(table)
    console.print(f"\n[dim]Full history: {storage.storage_path}[/dim]")


@app.command()
def view(
    concept: Annotated[
        str,
        typer.Argument(help="Concept to view from history"),
    ],
    details: Annotated[
        bool,
        typer.Option("--details", "-d", help="Show full details with reasoning"),
    ] = False,
    html: Annotated[
        str | None,
        typer.Option("--html", help="Export to HTML file"),
    ] = None,
) -> None:
    """View detailed analysis result from history."""
    storage = Storage()
    records = storage.get_all()

    matching = [r for r in records if concept.lower() in r.get("concept", "").lower()]

    if not matching:
        console.print(f"[yellow]No records found for: {concept}[/yellow]")
        raise typer.Exit(code=1)

    record = matching[-1]

    if html:
        _export_html(record, Path(html))
        return

    _display_record(record, details)


@app.command()
def export(
    output: Annotated[
        Path,
        typer.Argument(help="Output file path (JSON, .md, or .html)"),
    ],
    concept: Annotated[
        str | None,
        typer.Option("--concept", "-c", help="Export specific concept"),
    ] = None,
    format: Annotated[
        str,
        typer.Option("--format", "-f", help="Output format: json, markdown, or html"),
    ] = "auto",
) -> None:
    """Export history to a file."""
    storage = Storage()
    records = storage.get_all()

    if concept:
        records = [r for r in records if concept.lower() in r.get("concept", "").lower()]

    if not records:
        console.print("[yellow]No records to export.[/yellow]")
        raise typer.Exit(code=0)

    output_path = Path(output)
    suffix = output_path.suffix.lower()
    fmt = format if format != "auto" else suffix

    if fmt == ".json" or fmt == "json":
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2, ensure_ascii=False)
        console.print(f"[green]Exported {len(records)} records to {output_path}[/green]")
    elif fmt == ".html" or fmt == "html":
        _export_html(records[-1] if len(records) == 1 else {"records": records}, output_path)
        console.print(f"[green]Exported HTML report to {output_path}[/green]")
    else:
        lines = ["# SimulateDecision Analysis History\n", f"## {len(records)} records\n"]
        for record in records:
            lines.append(_record_to_markdown(record))
            lines.append("\n---")
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        console.print(f"[green]Exported {len(records)} records to {output_path}[/green]")


def _record_to_markdown(record: dict[str, Any]) -> str:
    lines = []
    lines.append(f"\n### {record.get('concept', 'Unknown')}")
    lines.append(f"**Status:** {record.get('status', 'unknown')}")
    lines.append(f"**Timestamp:** {record.get('timestamp', 'unknown')}")
    lines.append(f"**Iterations:** {record.get('iterations', '-')}")

    meta = record.get("metadata", {})
    if meta:
        lines.append(f"**Total Tokens:** {meta.get('total_tokens_used', 'N/A')}")
        lines.append(f"**Model:** {meta.get('model_name', 'N/A')}")
        lines.append(f"**Converged:** {meta.get('converged', 'N/A')}")

    strategy_history = record.get("strategy_history", [])
    if strategy_history:
        lines.append("\n### Iteration Details")
        for i, attempt in enumerate(strategy_history, 1):
            lines.append(f"\n**Iteration {i}**")
            lines.append(f"- Strategy: {attempt.get('strategy', 'N/A')[:80]}...")
            lines.append(f"- Atoms: {attempt.get('atoms_count', 0)}")
            lines.append(f"- Axioms: {attempt.get('axioms_count', 0)}")
            if attempt.get("reasoning"):
                lines.append(f"- Reasoning: {attempt.get('reasoning')[:150]}...")

    if record.get("purified_atoms"):
        lines.append(f"\n**Purified Atoms:**\n{record.get('purified_atoms')}")
    if record.get("blueprint"):
        lines.append(f"\n**Blueprint:**\n{record.get('blueprint')}")

    return "\n".join(lines)


def _display_record(record: dict[str, Any], details: bool) -> None:
    status = record.get("status", "unknown")
    status_color = "green" if status == "SUCCESS" else "red"

    console.print(Panel.fit(
        f"[bold]{record.get('concept', 'Unknown')}[/bold]\n"
        f"Status: [{status_color}]{status}[/{status_color}]",
        title="Analysis Result"
    ))

    meta = record.get("metadata", {})
    if meta:
        table = Table(title="Metadata", show_header=False)
        table.add_column("Key", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Iterations", str(record.get("iterations", "N/A")))
        table.add_row("Total Tokens", str(meta.get("total_tokens_used", "N/A")))
        table.add_row("Model", meta.get("model_name", "N/A"))
        table.add_row("Converged", "Yes" if meta.get("converged") else "No")
        table.add_row("Initial Strategy", meta.get("initial_strategy", "N/A")[:50] + "...")

        console.print(table)

    if details:
        strategy_history = record.get("strategy_history", [])
        if strategy_history:
            tree = Tree("[bold]Iteration Details[/bold]")
            for i, attempt in enumerate(strategy_history, 1):
                stage_info = f"Iteration {i}: {attempt.get('atoms_count', 0)} atoms -> {attempt.get('axioms_count', 0)} axioms"
                branch = tree.add(stage_info)
                if attempt.get("reasoning"):
                    branch.add(f"Reasoning: {attempt.get('reasoning')[:100]}...")
                if attempt.get("raw_atoms"):
                    branch.add(f"Raw Atoms: {attempt.get('raw_atoms')[:80]}...")
                if attempt.get("verified_atoms"):
                    branch.add(f"Verified: {attempt.get('verified_atoms')[:80]}...")
            console.print(tree)

    if record.get("purified_atoms"):
        console.print("\n[bold]Purified Atoms:[/bold]")
        console.print(Panel(record.get("purified_atoms")))

    if record.get("blueprint"):
        console.print("\n[bold]Technical Blueprint:[/bold]")
        code = Syntax(record.get("blueprint"), "markdown", theme="monokai")
        console.print(Panel(code))


@app.command()
def clear_history(
    force: Annotated[
        bool,
        typer.Option("--force", help="Skip confirmation"),
    ] = False,
) -> None:
    """Clear all history."""
    storage = Storage()
    if not force:
        confirm = typer.confirm("Delete all history?")
        if not confirm:
            console.print("[yellow]Cancelled.[/yellow]")
            raise typer.Exit(code=0)
    storage.clear()
    console.print("[green]History cleared.[/green]")


@app.command()
def config_show() -> None:
    """Display current SimulateDecision configuration."""
    config = EngineConfig()
    storage = Storage()
    table = Table(title="SimulateDecision Configuration")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("LM Studio URL", config.lm_studio_url)
    table.add_row("Max Iterations", str(config.max_iterations))
    table.add_row("Model", config.model_name)
    table.add_row("Signal Loss Threshold", str(config.signal_loss_threshold))
    table.add_row("History File", str(storage.storage_path))

    console.print(table)


@app.command()
def pipelines() -> None:
    """List available pipeline templates."""
    templates = PipelineTemplates.list_templates()

    table = Table(title="Available Pipeline Templates")
    table.add_column("Name", style="cyan")
    table.add_column("Description", style="green")
    table.add_column("Stages", style="yellow")
    table.add_column("Use Cases", style="dim")

    for t in templates:
        table.add_row(
            t["name"],
            t["description"][:50] + "..." if len(t["description"]) > 50 else t["description"],
            ", ".join(t["stages"]),
            ", ".join(t["use_cases"][:2]),
        )

    console.print(table)
    console.print("\n[dim]Use: SimulateDecision analyze 'concept' -p <template-name>[/dim]")


@app.command()
def story_analysis(
    story: Annotated[str, typer.Argument(help="User story or problem description")],
    template: Annotated[
        str,
        typer.Option("-t", "--template", help="Analysis template (user_story, business_analysis, technical_story, problem_decomposition, decision_framework)"),
    ] = "user_story",
    iterations: Annotated[
        int,
        typer.Option("--iterations", "-i", help="Maximum iterations"),
    ] = 3,
    verbose: Annotated[
        bool,
        typer.Option("--verbose", "-v", help="Enable verbose output"),
    ] = False,
    html: Annotated[
        str | None,
        typer.Option("--html", help="Export result to HTML file"),
    ] = None,
) -> None:
    """Analyze a user story using specialized decomposition pipeline."""
    config = get_config()
    config.configure_dspy()

    template_info = StoryPipelineTemplates.list_templates()
    selected = next((t for t in template_info if t["name"] == template), None)

    if not selected:
        console.print(f"[red]Unknown template: {template}[/red]")
        console.print(f"[yellow]Available: {', '.join(t['name'] for t in template_info)}[/yellow]")
        raise typer.Exit(code=1)

    console.print(Panel.fit(
        f"[bold cyan]Story Analysis[/bold cyan]\n{story[:100]}...",
        subtitle=f"Template: {template} | Stages: {len(selected['stages'])}"
    ))

    try:
        pipeline_config = StoryPipelineTemplates.create_config(template, max_iterations=iterations)
        engine = SimulateDecision(config=config, pipeline_config=pipeline_config)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Analyzing story...", total=None)
            result = engine(story, save_result=True)
            progress.update(task, completed=True)

        if result["status"] == "SUCCESS":
            _display_story_result(result, verbose)
            if html:
                _export_html(result, Path(html))
        else:
            _display_failure(result)
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1) from e


@app.command()
def story_templates() -> None:
    """List available story analysis templates."""
    templates = StoryPipelineTemplates.list_templates()

    table = Table(title="Story Analysis Templates")
    table.add_column("Name", style="cyan")
    table.add_column("Description", style="green")
    table.add_column("Stages", style="yellow")
    table.add_column("Use Cases", style="dim")

    for t in templates:
        table.add_row(
            t["name"],
            t["description"][:60] + "..." if len(t["description"]) > 60 else t["description"],
            ", ".join(t["stages"]),
            ", ".join(t["use_cases"][:2]),
        )

    console.print(table)
    console.print("\n[dim]Use: SimulateDecision story-analysis 'your story' -t <template-name>[/dim]")


def _display_story_result(result: dict[str, Any], verbose: bool) -> None:
    metadata = result.get("metadata", {})

    console.print("\n[bold green]Story Analysis Complete![/bold green]")

    table = Table(show_header=False)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Status", result.get("status", "N/A"))
    table.add_row("Iterations", str(result.get("iterations", "N/A")))
    table.add_row("Pipeline", metadata.get("pipeline_name", "N/A"))

    console.print(table)

    if verbose:
        if result.get("purified_atoms"):
            console.print("\n[bold]Key Findings:[/bold]")
            console.print(Panel(result.get("purified_atoms")))

        if result.get("blueprint"):
            console.print("\n[bold]Detailed Specification:[/bold]")
            code = Syntax(result.get("blueprint"), "markdown", theme="monokai")
            console.print(Panel(code))


def _export_html(result: dict[str, Any], output_path: Path) -> None:
    html = _generate_html_report(result)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    console.print(f"[green]HTML report saved to {output_path}[/green]")


def _generate_html_report(data: dict[str, Any]) -> str:
    if "records" in data:
        records = data["records"]
        concept = f"Multiple Records ({len(records)})"
        status = "MULTI"
        iterations = len(records)
        purified_atoms = ""
        blueprint = ""
        metadata = records[-1].get("metadata", {}) if records else {}
        strategy_history = []
        for r in records:
            strategy_history.extend(r.get("strategy_history", []))
    else:
        records = [data]
        concept = data.get("concept", "Unknown")
        status = data.get("status", "unknown")
        iterations = data.get("iterations", 0)
        purified_atoms = data.get("purified_atoms", "")
        blueprint = data.get("blueprint", "")
        metadata = data.get("metadata", {})
        strategy_history = data.get("strategy_history", [])

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SimulateDecision Report - {concept}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: #e0e0e0;
            line-height: 1.6;
            min-height: 100vh;
        }}
        .container {{ max-width: 1200px; margin: 0 auto; padding: 2rem; }}
        h1, h2, h3 {{ color: #00d4ff; margin-bottom: 1rem; }}
        h1 {{ font-size: 2.5rem; border-bottom: 2px solid #00d4ff; padding-bottom: 1rem; }}
        
        .card {{
            background: rgba(255,255,255,0.05);
            border-radius: 12px;
            padding: 1.5rem;
            margin-bottom: 1.5rem;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255,255,255,0.1);
        }}
        
        .status {{
            display: inline-block;
            padding: 0.5rem 1rem;
            border-radius: 20px;
            font-weight: bold;
            text-transform: uppercase;
        }}
        .status.success {{ background: #00c853; color: #000; }}
        .status.failure {{ background: #ff5252; color: #fff; }}
        
        .grid {{ 
            display: grid; 
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
            margin: 1rem 0;
        }}
        
        .stat-box {{
            background: rgba(0,212,255,0.1);
            border-radius: 8px;
            padding: 1rem;
            text-align: center;
        }}
        .stat-box .value {{ font-size: 1.5rem; font-weight: bold; color: #00d4ff; }}
        .stat-box .label {{ color: #888; font-size: 0.9rem; }}
        
        .section {{ margin: 2rem 0; }}
        
        .timeline {{
            position: relative;
            padding-left: 2rem;
            border-left: 2px solid #00d4ff;
        }}
        .timeline-item {{
            position: relative;
            margin-bottom: 1.5rem;
            padding-left: 1rem;
        }}
        .timeline-item::before {{
            content: '';
            position: absolute;
            left: -2.4rem;
            top: 0;
            width: 12px;
            height: 12px;
            background: #00d4ff;
            border-radius: 50%;
        }}
        
        .reasoning {{
            background: rgba(0,0,0,0.3);
            border-left: 3px solid #00d4ff;
            padding: 1rem;
            margin: 0.5rem 0;
            font-family: monospace;
            font-size: 0.9rem;
        }}
        
        .blueprint {{
            background: #0d1117;
            border-radius: 8px;
            padding: 1.5rem;
            overflow-x: auto;
            white-space: pre-wrap;
            font-family: 'Courier New', monospace;
            font-size: 0.85rem;
            color: #c9d1d9;
        }}
        
        .atoms {{
            background: rgba(0,200,83,0.1);
            border-radius: 8px;
            padding: 1rem;
            white-space: pre-wrap;
        }}
        
        .noise {{
            background: rgba(255,82,82,0.1);
            border-radius: 8px;
            padding: 1rem;
            font-size: 0.9rem;
        }}
        
        .tabs {{ display: flex; gap: 0.5rem; margin-bottom: 1rem; }}
        .tab {{
            padding: 0.75rem 1.5rem;
            background: rgba(255,255,255,0.05);
            border: none;
            color: #888;
            cursor: pointer;
            border-radius: 8px 8px 0 0;
            transition: all 0.3s;
        }}
        .tab.active {{ background: rgba(0,212,255,0.2); color: #00d4ff; }}
        .tab-content {{ display: none; }}
        .tab-content.active {{ display: block; }}
        
        .metadata-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 0.5rem;
        }}
        .metadata-item {{
            background: rgba(255,255,255,0.03);
            padding: 0.5rem;
            border-radius: 4px;
        }}
        .metadata-item .key {{ color: #888; font-size: 0.8rem; }}
        .metadata-item .val {{ color: #00d4ff; }}
        
        @media print {{
            body {{ background: white; color: black; }}
            .card {{ border: 1px solid #ddd; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>SimulateDecision Analysis Report</h1>
        
        <div class="card">
            <span class="status {'success' if status == 'SUCCESS' else 'failure'}">{status}</span>
            <h2 style="margin-top: 1rem;">{concept}</h2>
        </div>
        
        <div class="grid">
            <div class="stat-box">
                <div class="value">{iterations}</div>
                <div class="label">Iterations</div>
            </div>
            <div class="stat-box">
                <div class="value">{metadata.get('total_tokens_used', 'N/A')}</div>
                <div class="label">Total Tokens</div>
            </div>
            <div class="stat-box">
                <div class="value">{"Yes" if metadata.get('converged') else "No"}</div>
                <div class="label">Converged</div>
            </div>
            <div class="stat-box">
                <div class="value">{metadata.get('signal_loss_threshold', 'N/A')}</div>
                <div class="label">Signal Threshold</div>
            </div>
        </div>
        
        <div class="section">
            <h3>Configuration & Metadata</h3>
            <div class="card">
                <div class="metadata-grid">
                    <div class="metadata-item">
                        <div class="key">Model</div>
                        <div class="val">{metadata.get('model_name', 'N/A')}</div>
                    </div>
                    <div class="metadata-item">
                        <div class="key">Initial Strategy</div>
                        <div class="val">{metadata.get('initial_strategy', 'N/A')[:60]}...</div>
                    </div>
                    <div class="metadata-item">
                        <div class="key">Final Strategy</div>
                        <div class="val">{metadata.get('final_strategy', 'N/A')[:60]}...</div>
                    </div>
                    <div class="metadata-item">
                        <div class="key">Stages Executed</div>
                        <div class="val">{', '.join(metadata.get('stages_executed', []))}</div>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="tabs">
            <button class="tab active" onclick="showTab('atoms')">Atoms</button>
            <button class="tab" onclick="showTab('iterations')">Iteration Details</button>
            <button class="tab" onclick="showTab('blueprint')">Blueprint</button>
        </div>
        
        <div id="atoms" class="tab-content active">
            <div class="section">
                <h3>Purified Atoms</h3>
                <div class="atoms">{purified_atoms or 'No atoms available'}</div>
            </div>
"""

    if metadata.get("noise_filtered"):
        html += f"""
            <div class="section">
                <h3>Noise Filtered</h3>
                <div class="noise">Noise detected during processing: {metadata.get('noise_filtered', 'None')}</div>
            </div>
"""

    html += """
        </div>
        
        <div id="iterations" class="tab-content">
            <div class="section">
                <h3>Iteration Breakdown</h3>
                <div class="timeline">
"""

    for i, attempt in enumerate(strategy_history, 1):
        reasoning_snippet = f'<div class="reasoning">Why: {attempt.get("reasoning", "N/A")[:200]}...</div>' if attempt.get("reasoning") else ""
        raw_atoms_snippet = f'<p><strong>Raw Atoms:</strong> {attempt.get("raw_atoms", "N/A")[:100]}...</p>' if attempt.get("raw_atoms") else ""
        verified_snippet = f'<p><strong>Verified:</strong> {attempt.get("verified_atoms", "N/A")[:100]}...</p>' if attempt.get("verified_atoms") else ""
        rejection_snippet = f'<p><strong>Rejection:</strong> {attempt.get("rejection_reason", "N/A")}</p>' if attempt.get("rejection_reason") else ""
        optimization_snippet = f'<p><strong>Optimization:</strong> {attempt.get("optimization_reasoning", "N/A")[:100]}...</p>' if attempt.get("optimization_reasoning") else ""

        html += f"""
                    <div class="timeline-item">
                        <h4>Iteration {attempt.get('iteration', i)}</h4>
                        <p><strong>Strategy:</strong> {attempt.get('strategy', 'N/A')[:80]}...</p>
                        <p><strong>Atoms:</strong> {attempt.get('atoms_count', 0)} -> <strong>Axioms:</strong> {attempt.get('axioms_count', 0)}</p>
                        <p><strong>Stage:</strong> {attempt.get('stage', 'N/A')}</p>
                        <p><strong>Tokens:</strong> ~{attempt.get('tokens_used', 0)}</p>
                        {reasoning_snippet}
                        {raw_atoms_snippet}
                        {verified_snippet}
                        {rejection_snippet}
                        {optimization_snippet}
                    </div>
"""

    all_reasonings = metadata.get("all_reasonings", [])
    if all_reasonings:
        html += """
                </div>
            </div>
            
            <div class="section">
                <h3>All Reasoning Traces</h3>
"""
        for j, reasoning in enumerate(all_reasonings, 1):
            html += f'<div class="reasoning">[{j}] {reasoning[:300]}...</div>\n'

    html += """
            </div>
        </div>
        
        <div id="blueprint" class="tab-content">
            <div class="section">
                <h3>Technical Blueprint</h3>
                <div class="blueprint">""" + (blueprint or "No blueprint generated") + """</div>
            </div>
        </div>
        
        <div class="section">
            <h3>Raw Data (JSON)</h3>
            <pre class="blueprint">""" + json.dumps(records[0] if len(records) == 1 else records, indent=2) + """</pre>
        </div>
    </div>
    
    <script>
        function showTab(tabId) {
            document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.getElementById(tabId).classList.add('active');
            event.target.classList.add('active');
        }
    </script>
</body>
</html>"""
    return html


def _display_success(result: dict[str, Any], verbose: bool) -> None:
    metadata = result.get("metadata", {})

    console.print("\n[bold green]Analysis Complete![/bold green]")

    table = Table(show_header=False)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Status", result.get("status", "N/A"))
    table.add_row("Iterations", str(result.get("iterations", "N/A")))
    table.add_row("Total Tokens", f"~{metadata.get('total_tokens_used', 'N/A')}")
    table.add_row("Model", metadata.get("model_name", "N/A"))
    table.add_row("Converged", "Yes" if metadata.get("converged") else "No")

    console.print(table)

    if verbose:
        console.print("\n[bold]Iteration Details:[/bold]")
        strategy_history = result.get("strategy_history", [])
        if strategy_history:
            for i, attempt in enumerate(strategy_history, 1):
                stage = attempt.get("stage", "unknown")
                atoms = attempt.get("atoms_count", 0)
                axioms = attempt.get("axioms_count", 0)
                tokens = attempt.get("tokens_used", 0)
                console.print(f"  [{i}] {stage}: {atoms} atoms -> {axioms} axioms (~{tokens} tokens)")
                if attempt.get("reasoning"):
                    console.print(f"      Why: {attempt.get('reasoning')[:100]}...")

        console.print("\n[bold]Purified Atoms:[/bold]")
        console.print(Panel(str(result.get("purified_atoms", "N/A"))))

        console.print("\n[bold]Technical Blueprint:[/bold]")
        code = Syntax(str(result.get("blueprint", "N/A")), "markdown", theme="monokai")
        console.print(Panel(code))

        if result.get("strategy_history"):
            console.print("\n[bold]Strategy History:[/bold]")
            for i, attempt in enumerate(result.get("strategy_history", []), 1):
                console.print(f"  {i}. {attempt.get('strategy', 'N/A')[:60]}...")


def _display_failure(result: dict[str, Any]) -> None:
    console.print("\n[bold red]Analysis Failed[/bold red]")
    console.print(f"[red]{result.get('error', 'Unknown error')}[/red]")

    metadata = result.get("metadata", {})
    if metadata:
        console.print(f"\n[dim]Total tokens used before failure: ~{metadata.get('total_tokens_used', 0)}[/dim]")
        console.print(f"[dim]Iterations attempted: {metadata.get('total_iterations', 'N/A')}[/dim]")


if __name__ == "__main__":
    app
