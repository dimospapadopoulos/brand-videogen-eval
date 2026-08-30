"""`vgeval` command-line interface."""

from __future__ import annotations

import asyncio
import subprocess
import sys

import typer
from rich.console import Console
from rich.table import Table

from vgeval.config import REPO_ROOT
from vgeval.providers import available
from vgeval.runner import run_batch
from vgeval.scoring import judge_run
from vgeval.store import RunStore

app = typer.Typer(add_completion=False, help="Image-to-video model evaluation harness.")
console = Console()


@app.command()
def providers() -> None:
    """List registered providers."""
    console.print("Registered providers: " + (", ".join(available()) or "(none)"))


@app.command()
def run(
    provider: list[str] = typer.Option(["mock"], "--provider", "-p", help="Provider(s) to run."),
    suite: str = typer.Option("example_suite", "--suite", "-s", help="Prompt suite name/path."),
    concurrency: int | None = typer.Option(None, "--concurrency", "-c"),
    run_id: str | None = typer.Option(None, "--run-id", help="Resume an existing run."),
) -> None:
    """Generate videos for the provider × prompt matrix."""
    rid = asyncio.run(run_batch(provider, suite, concurrency=concurrency, run_id=run_id))
    store = RunStore.open(rid)
    states = store.read_job_states()
    done = sum(1 for s in states.values() if s.status.value == "done")
    failed = sum(1 for s in states.values() if s.status.value == "failed")
    console.print(f"[green]Run {rid}[/]: {done} done, {failed} failed, {len(states)} total")
    console.print(f"Artifacts: {store.dir}")


@app.command()
def judge(
    run_id: str | None = typer.Option(None, "--run", help="Run id (default: latest)."),
    stub: bool = typer.Option(False, "--stub", help="Use the keyless deterministic judge."),
    force: bool = typer.Option(False, "--force", help="Re-score already-scored jobs."),
) -> None:
    """Score a run with the VLM judge (or the stub)."""
    rid = run_id or RunStore.latest_run_id()
    if not rid:
        console.print("[red]No runs found.[/] Run `vgeval run` first.")
        raise typer.Exit(1)
    try:
        scored = judge_run(rid, use_stub=stub, force=force)
    except RuntimeError as exc:
        console.print(f"[yellow]Skipping real judge:[/] {exc}")
        console.print("Tip: pass --stub for a keyless run.")
        raise typer.Exit(1) from None
    console.print(f"[green]Judged {len(scored)} job(s)[/] in run {rid}")
    _print_leaderboard(rid)


@app.command()
def dashboard(port: int = typer.Option(8501, "--port")) -> None:
    """Launch the Streamlit dashboard."""
    app_path = REPO_ROOT / "dashboard" / "app.py"
    subprocess.run(
        [sys.executable, "-m", "streamlit", "run", str(app_path), "--server.port", str(port)],
        check=False,
    )


@app.command()
def canary() -> None:
    """Shadow-mode: full mock pipeline end-to-end, keyless. Exits non-zero on failure."""
    rid = asyncio.run(run_batch(["mock"], "example_suite", run_id="canary"))
    store = RunStore.open(rid)
    states = store.read_job_states()
    if any(s.status.value == "failed" for s in states.values()):
        console.print("[red]Canary FAILED[/]: some generation jobs failed.")
        raise typer.Exit(1)
    scored = judge_run(rid, use_stub=True, force=True)
    done = [s for s in states.values() if s.status.value == "done"]
    if len(scored) != len(done):
        console.print(f"[red]Canary FAILED[/]: scored {len(scored)} of {len(done)} done jobs.")
        raise typer.Exit(1)
    console.print(f"[green]Canary OK[/]: {len(done)} jobs generated and scored.")


def _print_leaderboard(run_id: str) -> None:
    from vgeval.report import leaderboard

    rows = leaderboard(run_id)
    if not rows:
        return
    table = Table(title=f"Leaderboard — {run_id}")
    table.add_column("provider")
    table.add_column("n")
    table.add_column("overall", justify="right")
    for r in rows:
        table.add_row(r["provider"], str(r["n"]), f"{r['overall']:.2f}")
    console.print(table)


if __name__ == "__main__":
    app()
