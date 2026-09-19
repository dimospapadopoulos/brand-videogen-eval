"""`vgeval` command-line interface."""

from __future__ import annotations

import asyncio
import subprocess
import sys

import typer
from rich.console import Console
from rich.table import Table

from vgeval.config import REPO_ROOT
from vgeval.providers import available, register_local_providers
from vgeval.runner import run_batch
from vgeval.scoring import judge_run
from vgeval.store import RunStore

app = typer.Typer(add_completion=False, help="Image-to-video model evaluation harness.")
console = Console()


@app.command()
def providers() -> None:
    """List registered providers (including bring-your-own-clip model folders)."""
    register_local_providers()
    console.print("Registered providers: " + (", ".join(available()) or "(none)"))


@app.command()
def run(
    provider: list[str] = typer.Option(["mock"], "--provider", "-p", help="Provider(s) to run."),
    suite: str = typer.Option("example_suite", "--suite", "-s", help="Prompt suite name/path."),
    rubric: str = typer.Option("rubric_v1", "--rubric", "-r", help="Rubric to record for the run."),
    concurrency: int | None = typer.Option(None, "--concurrency", "-c"),
    run_id: str | None = typer.Option(None, "--run-id", help="Resume an existing run."),
) -> None:
    """Generate videos for the provider × prompt matrix."""
    register_local_providers()  # pick up any bring-your-own-clip model folders
    rid = asyncio.run(
        run_batch(provider, suite, concurrency=concurrency, run_id=run_id, rubric_version=rubric)
    )
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
    rubric: str | None = typer.Option(None, "--rubric", "-r", help="Override rubric."),
    defects: bool = typer.Option(
        True, "--defects/--no-defects", help="Run the dedicated defect-hunt pass (extra call/clip)."
    ),
) -> None:
    """Score a run with the hybrid judge (VLM + deterministic + defect hunt), or the stub."""
    rid = run_id or RunStore.latest_run_id()
    if not rid:
        console.print("[red]No runs found.[/] Run `vgeval run` first.")
        raise typer.Exit(1)
    try:
        scored = judge_run(
            rid, use_stub=stub, force=force, rubric_name=rubric, hunt_defects=defects
        )
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
    """Shadow-mode: full mock pipeline end-to-end, keyless. Exits non-zero on failure.

    Uses rubric_v2 so the shadow run also exercises the hybrid routing and the
    deterministic scorers (ΔE color + loop seam), not just the stub VLM.
    """
    rid = asyncio.run(
        run_batch(["mock"], "example_suite", run_id="canary", rubric_version="rubric_v2")
    )
    store = RunStore.open(rid)
    states = store.read_job_states()
    if any(s.status.value == "failed" for s in states.values()):
        console.print("[red]Canary FAILED[/]: some generation jobs failed.")
        raise typer.Exit(1)
    scored = judge_run(rid, use_stub=True, force=True, rubric_name="rubric_v2")
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
