import click

from llmind import __version__


@click.group()
@click.version_option(version=__version__, prog_name="llmind-cli")
def main() -> None:
    """LLMind — semantic file enrichment engine."""
    pass
