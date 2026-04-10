import click
from rich.console import Console
from rich.table import Table
from pathlib import Path
from llmind import __version__

console = Console()


@click.group()
@click.version_option(version=__version__, prog_name="llmind-cli")
def main() -> None:
    """LLMind — semantic file enrichment engine."""


# ── enrich ──────────────────────────────────────────────────────────────────

@main.command()
@click.argument("paths", nargs=-1, type=click.Path(exists=True, path_type=Path))
@click.option("--model", default=None, show_default=True, help="Model identifier (defaults to provider default)")
@click.option("--key", "key_path", type=click.Path(path_type=Path), default=None, help="Path to .key file")
@click.option("--force", is_flag=True, default=False)
@click.option("--generate-key", is_flag=True, default=False, help="Generate a new signing key")
@click.option("--key-output", type=click.Path(path_type=Path), default=None, help="Directory to save generated key")
@click.option(
    "--provider",
    type=click.Choice(["ollama", "anthropic", "openai"]),
    default="ollama",
    show_default=True,
    help="Vision AI provider to use.",
)
def enrich(paths, model, key_path, force, generate_key, key_output, provider):
    """Enrich files with semantic XMP metadata."""
    from llmind.enricher import enrich as do_enrich
    from llmind.crypto import generate_key as gen_key, save_key_file, load_key_file, derive_key_id
    from llmind.models import KeyFile
    from datetime import datetime, timezone

    creation_key = None
    if generate_key:
        k = gen_key()
        key_id = derive_key_id(k)
        out_dir = key_output or Path.cwd()
        kf = KeyFile(key_id=key_id, creation_key=k, created=datetime.now(timezone.utc).isoformat(), file=key_id)
        saved = save_key_file(out_dir, kf)
        console.print(f"[green]Key saved:[/green] {saved}")
        creation_key = k
    elif key_path:
        kf = load_key_file(key_path)
        creation_key = kf.creation_key

    for path in paths:
        result = do_enrich(path, model=model, creation_key=creation_key, force=force, provider=provider)
        if result.skipped:
            console.print(f"[yellow]SKIP[/yellow] {path.name} (already fresh)")
        elif result.success:
            console.print(f"[green]OK[/green]   {result.path.name} v{result.version} ({result.elapsed:.1f}s)")
        else:
            console.print(f"[red]ERR[/red]  {path.name}: {result.error}")


# ── read ─────────────────────────────────────────────────────────────────────

@main.command()
@click.argument("path", type=click.Path(exists=True, path_type=Path))
def read(path):
    """Display LLMind metadata for a file."""
    from llmind.reader import read as do_read
    meta = do_read(path)
    if meta is None:
        console.print("[yellow]No LLMind layer found.[/yellow]")
        return
    cur = meta.current
    console.print(f"[bold]Version:[/bold] {cur.version}")
    console.print(f"[bold]Timestamp:[/bold] {cur.timestamp}")
    console.print(f"[bold]Language:[/bold] {cur.language}")
    console.print(f"[bold]Generator:[/bold] {cur.generator} / {cur.generator_model}")
    console.print(f"[bold]Checksum:[/bold] {cur.checksum[:16]}…")
    console.print(f"[bold]Description:[/bold] {cur.description}")
    console.print(f"[bold]Text:[/bold]\n{cur.text}")


# ── history ───────────────────────────────────────────────────────────────────

@main.command()
@click.argument("path", type=click.Path(exists=True, path_type=Path))
def history(path):
    """Show version history for a file."""
    from llmind.reader import read as do_read
    meta = do_read(path)
    if meta is None:
        console.print("[yellow]No LLMind layer found.[/yellow]")
        return
    table = Table(title=f"History: {path.name}")
    table.add_column("Ver", style="cyan")
    table.add_column("Timestamp")
    table.add_column("Model")
    table.add_column("Checksum")
    for layer in meta.layers:
        table.add_row(
            str(layer.version),
            layer.timestamp,
            layer.generator_model,
            layer.checksum[:16] + "…",
        )
    console.print(table)


# ── verify ────────────────────────────────────────────────────────────────────

@main.command()
@click.argument("paths", nargs=-1, type=click.Path(exists=True, path_type=Path))
@click.option("--key", "key_path", type=click.Path(path_type=Path), default=None)
def verify(paths, key_path):
    """Verify file checksums and signatures."""
    from llmind.verifier import verify as do_verify
    from llmind.crypto import load_key_file

    creation_key = None
    if key_path:
        creation_key = load_key_file(key_path).creation_key

    for path in paths:
        result = do_verify(path, creation_key=creation_key)
        if not result.has_layer:
            console.print(f"[yellow]NONE[/yellow] {path.name}: no LLMind layer")
            continue
        checksum_icon = "[green]✓[/green]" if result.checksum_valid else "[red]✗[/red]"
        sig_icon = ""
        if result.signature_valid is True:
            sig_icon = " sig[green]✓[/green]"
        elif result.signature_valid is False:
            sig_icon = " sig[red]✗[/red]"
        console.print(f"{checksum_icon}{sig_icon} {path.name} v{result.current_version}")


# ── strip ─────────────────────────────────────────────────────────────────────

@main.command()
@click.argument("paths", nargs=-1, type=click.Path(exists=True, path_type=Path))
def strip(paths):
    """Remove LLMind XMP metadata from files."""
    from llmind.injector import remove_llmind_xmp

    for path in paths:
        removed = remove_llmind_xmp(path)
        if removed:
            console.print(f"[green]Stripped[/green] {path.name}")
        else:
            console.print(f"[yellow]Nothing to strip[/yellow] {path.name}")


# ── watch ─────────────────────────────────────────────────────────────────────

@main.command()
@click.argument("directory", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.option("--mode", type=click.Choice(["new", "backfill", "existing"]), default="new", show_default=True)
@click.option("--model", default=None, show_default=True, help="Model identifier (defaults to provider default)")
@click.option("--key", "key_path", type=click.Path(path_type=Path), default=None)
@click.option(
    "--provider",
    type=click.Choice(["ollama", "anthropic", "openai"]),
    default="ollama",
    show_default=True,
    help="Vision AI provider to use.",
)
def watch(directory, mode, model, key_path, provider):
    """Watch a directory and enrich new files automatically."""
    from llmind.watcher import run_watch, WatchMode
    from llmind.enricher import enrich as do_enrich
    from llmind.crypto import load_key_file

    creation_key = None
    if key_path:
        creation_key = load_key_file(key_path).creation_key

    watch_mode = WatchMode(mode)

    def _enrich(path):
        result = do_enrich(path, model=model, creation_key=creation_key, provider=provider)
        if result.skipped:
            console.print(f"[yellow]SKIP[/yellow] {path.name}")
        elif result.success:
            console.print(f"[green]OK[/green] {path.name} v{result.version}")
        else:
            console.print(f"[red]ERR[/red] {path.name}: {result.error}")

    console.print(f"Watching [bold]{directory}[/bold] (mode={mode})")
    run_watch(directory, _enrich, mode=watch_mode)
