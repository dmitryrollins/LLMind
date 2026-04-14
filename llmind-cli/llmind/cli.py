import click
from rich.console import Console
from rich.table import Table
from pathlib import Path
from llmind import __version__
from llmind.embedder import EMBEDDING_DEFAULTS

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

    from llmind.enricher import is_already_enriched_file

    for path in paths:
        if is_already_enriched_file(path):
            console.print(f"[dim]SKIP[/dim] {path.name} (already enriched — use [bold]reenrich[/bold])")
            continue
        result = do_enrich(path, model=model, creation_key=creation_key, force=force, provider=provider)
        if result.skipped:
            console.print(f"[yellow]SKIP[/yellow] {path.name} (already fresh)")
        elif result.success:
            console.print(f"[green]OK[/green]   {result.path.name} v{result.version} ({result.elapsed:.1f}s)")
        else:
            console.print(f"[red]ERR[/red]  {path.name}: {result.error}")


# ── reenrich ─────────────────────────────────────────────────────────────────

@main.command()
@click.argument("paths", nargs=-1, type=click.Path(exists=True, path_type=Path))
@click.option("--model", default=None, show_default=True)
@click.option("--key", "key_path", type=click.Path(path_type=Path), default=None)
@click.option("--force", is_flag=True, default=False, help="Re-enrich even if already fresh")
@click.option(
    "--provider",
    type=click.Choice(["ollama", "anthropic", "openai"]),
    default="ollama",
    show_default=True,
)
def reenrich(paths, model, key_path, force, provider):
    """Re-enrich existing .llmind files in-place (no rename)."""
    from llmind.enricher import reenrich as do_reenrich
    from llmind.crypto import load_key_file

    creation_key = None
    if key_path:
        creation_key = load_key_file(key_path).creation_key

    for path in paths:
        result = do_reenrich(path, model=model, creation_key=creation_key, force=force, provider=provider)
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


# ── embed ────────────────────────────────────────────────────────────────────

@main.command()
@click.argument("paths", nargs=-1, type=click.Path(exists=True, path_type=Path))
@click.option(
    "--provider",
    type=click.Choice(["ollama", "openai", "voyage", "anthropic"]),
    default="ollama",
    show_default=True,
    help="Embedding API provider. 'anthropic' routes to Voyage AI (Anthropic's recommended partner) and requires a Voyage API key from voyageai.com.",
)
@click.option("--model", default=None, help="Override embedding model (defaults to provider default).")
@click.option("--api-key", "api_key", envvar="LLMIND_EMBED_API_KEY", default=None, help="API key (or set LLMIND_EMBED_API_KEY).")
@click.option("--base-url", "base_url", default="http://localhost:11434/api/embeddings", show_default=True, help="Ollama base URL.")
@click.option("--force", is_flag=True, default=False, help="Re-embed even if embedding already present.")
def embed(paths, provider, model, api_key, base_url, force):
    """Embed LLMind files — store a semantic vector inside each file's XMP.

    Reads llmind:description from the XMP, generates an embedding with the
    chosen provider, and writes the vector back as llmind:embedding.  The
    original file content is unchanged.  Run once; search anytime.
    """
    from llmind.embedder import embed_text, patch_xmp_embedding, read_embedding_from_xmp
    from llmind.injector import inject, read_xmp_jpeg, read_xmp_png, read_xmp_pdf
    from llmind.reader import read as do_read
    import time

    resolved_model = model or EMBEDDING_DEFAULTS.get(provider, "")

    for path in paths:
        t0 = time.monotonic()
        suffix = path.suffix.lower()

        # Read current XMP string from the file
        if suffix in {".jpg", ".jpeg"}:
            xmp_string = read_xmp_jpeg(path)
        elif suffix == ".png":
            xmp_string = read_xmp_png(path)
        elif suffix == ".pdf":
            xmp_string = read_xmp_pdf(path)
        else:
            console.print(f"[yellow]SKIP[/yellow] {path.name} (unsupported format)")
            continue

        if xmp_string is None:
            console.print(f"[yellow]SKIP[/yellow] {path.name} (no LLMind layer — enrich first)")
            continue

        if not force and read_embedding_from_xmp(xmp_string) is not None:
            console.print(f"[yellow]SKIP[/yellow] {path.name} (already embedded; use --force to redo)")
            continue

        # Extract description from the parsed layer
        try:
            meta = do_read(path)
        except Exception as exc:
            console.print(f"[yellow]SKIP[/yellow] {path.name} (malformed XMP: {exc})")
            continue
        if meta is None:
            console.print(f"[red]ERR[/red]  {path.name}: no LLMind metadata")
            continue

        text_to_embed = meta.current.description or meta.current.text
        if not text_to_embed.strip():
            console.print(f"[yellow]SKIP[/yellow] {path.name} (empty description)")
            continue

        try:
            vector = embed_text(text_to_embed, provider=provider, model=model, api_key=api_key, base_url=base_url)
        except Exception as exc:
            console.print(f"[red]ERR[/red]  {path.name}: {exc}")
            continue

        # Patch embedding into the existing XMP and re-inject
        patched_xmp = patch_xmp_embedding(xmp_string, vector, resolved_model)
        try:
            inject(path, patched_xmp)
        except Exception as exc:
            console.print(f"[red]ERR[/red]  {path.name}: inject failed: {exc}")
            continue

        elapsed = time.monotonic() - t0
        console.print(f"[green]OK[/green]   {path.name} dim={len(vector)} ({elapsed:.1f}s) [{provider}/{resolved_model}]")


# ── search ────────────────────────────────────────────────────────────────────

@main.command()
@click.argument("query")
@click.argument("paths", nargs=-1, type=click.Path(exists=True, path_type=Path))
@click.option(
    "--mode",
    type=click.Choice(["hybrid", "vector", "keyword"]),
    default="hybrid",
    show_default=True,
    help="Search mode: hybrid combines vector + keyword scoring.",
)
@click.option(
    "--vector-weight",
    default=0.6,
    show_default=True,
    help="Weight for vector score in hybrid mode (0–1).",
)
@click.option(
    "--provider",
    type=click.Choice(["ollama", "openai", "voyage", "anthropic"]),
    default="ollama",
    show_default=True,
    help="Embedding API provider (must match the one used for embed).",
)
@click.option("--model", default=None, help="Override embedding model.")
@click.option("--api-key", "api_key", envvar="LLMIND_EMBED_API_KEY", default=None)
@click.option("--base-url", "base_url", default="http://localhost:11434/api/embeddings", show_default=True)
@click.option("--top", "top_k", default=10, show_default=True, help="Number of results to show.")
@click.option("--threshold", default=0.0, show_default=True, help="Minimum score to include.")
@click.option("--reveal", is_flag=True, default=False, help="Reveal result files in Finder after search.")
def search(query, paths, mode, vector_weight, provider, model, api_key, base_url, top_k, threshold, reveal):
    """Hybrid semantic + keyword search across LLMind files.

    Examples:

        llmind search "wedding ring" *.llmind.jpg

        llmind search "invoice" *.llmind.png --mode keyword

        llmind search "sunset" ~/Photos/*.llmind.jpg --mode hybrid --vector-weight 0.7

        llmind search "ring" ~/Desktop/*.llmind.png --reveal
    """
    from llmind.embedder import embed_text, cosine_similarity, read_embedding_from_xmp, keyword_score
    from llmind.injector import read_xmp_jpeg, read_xmp_png, read_xmp_pdf
    from llmind.reader import read as do_read

    if not paths:
        console.print("[yellow]No files given.[/yellow]")
        return

    use_vector = mode in {"hybrid", "vector"}
    use_keyword = mode in {"hybrid", "keyword"}
    kw_weight = 1.0 - vector_weight

    query_vec = None
    if use_vector:
        try:
            with console.status("Embedding query…"):
                query_vec = embed_text(query, provider=provider, model=model, api_key=api_key, base_url=base_url)
        except Exception as exc:
            console.print(f"[red]Error embedding query:[/red] {exc}")
            if mode == "vector":
                return
            console.print("[yellow]Falling back to keyword-only search.[/yellow]")
            use_vector = False

    results: list[tuple[float, float, float, Path]] = []
    skipped = 0

    for path in paths:
        suffix = path.suffix.lower()
        if suffix in {".jpg", ".jpeg"}:
            xmp_string = read_xmp_jpeg(path)
        elif suffix == ".png":
            xmp_string = read_xmp_png(path)
        elif suffix == ".pdf":
            xmp_string = read_xmp_pdf(path)
        else:
            skipped += 1
            continue

        if xmp_string is None:
            skipped += 1
            continue

        vec_score = 0.0
        if use_vector and query_vec is not None:
            vec = read_embedding_from_xmp(xmp_string)
            if vec is not None:
                vec_score = cosine_similarity(query_vec, vec)
            elif mode == "vector":
                skipped += 1
                continue

        kw_score = 0.0
        if use_keyword:
            meta = do_read(path)
            if meta is not None:
                desc = meta.current.description or ""
                text = meta.current.text or ""
                kw_score = keyword_score(query, f"{desc} {text}")

        if mode == "vector":
            combined = vec_score
        elif mode == "keyword":
            combined = kw_score
        else:
            combined = (vector_weight * vec_score) + (kw_weight * kw_score)

        if combined >= threshold:
            results.append((combined, vec_score, kw_score, path))

    results.sort(key=lambda x: x[0], reverse=True)
    results = results[:top_k]

    if not results:
        console.print("[yellow]No matching files found.[/yellow]")
        if skipped:
            console.print(f"[dim]{skipped} file(s) skipped (no embedding).[/dim]")
        return

    mode_label = {"vector": "Vector", "keyword": "Keyword", "hybrid": "Hybrid"}[mode]
    table = Table(title=f'{mode_label} Search: "{query}"', show_lines=False)
    table.add_column("#", style="dim", width=3, justify="right")
    table.add_column("Score", style="cyan", width=8, justify="right")
    if mode == "hybrid":
        table.add_column("Vec", style="dim", width=6, justify="right")
        table.add_column("Key", style="dim", width=6, justify="right")
    table.add_column("File")
    table.add_column("Description", style="dim")

    for i, (combined, vec_score, kw_score, path) in enumerate(results, 1):
        file_url = path.resolve().as_uri()
        file_link = f"[link={file_url}]{path.name}[/link]"
        meta = do_read(path)
        description = (meta.current.description[:60] + "…") if meta and meta.current.description else ""
        if mode == "hybrid":
            table.add_row(str(i), f"{combined:.4f}", f"{vec_score:.2f}", f"{kw_score:.2f}", file_link, description)
        else:
            table.add_row(str(i), f"{combined:.4f}", file_link, description)

    console.print(table)
    console.print("[dim]💡 Tip: filenames are clickable in iTerm2/Warp — or add [bold]--reveal[/bold] to open in Finder[/dim]")

    if skipped:
        console.print(f"[dim]{skipped} file(s) skipped (no embedding).[/dim]")

    if reveal:
        import subprocess
        console.print(f"\n[green]Opening {len(results)} file(s) in Finder…[/green]")
        for _, _, _, path in results:
            subprocess.run(["open", "-R", str(path.resolve())], check=False)


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
