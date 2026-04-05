import sys

import click
from yeet.app import YeetApp


def set_process_title(title: str) -> None:
    """Set the process title.

    Args:
        title: Desired title.
    """
    try:
        import setproctitle

        setproctitle.setproctitle(title)
    except Exception:
        pass


def check_directory(path: str) -> None:
    """Check a path is directory, or exit the app.

    Args:
        path: Path to check.
    """
    from pathlib import Path

    if not Path(path).resolve().is_dir():
        print(f"Not a directory: {path}")
        sys.exit(-1)


class DefaultCommandGroup(click.Group):
    def parse_args(self, ctx, args):
        if "--help" in args or "-h" in args:
            return super().parse_args(ctx, args)
        if "--version" in args or "-v" in args:
            return super().parse_args(ctx, args)
        # Check if first arg is a known subcommand
        if not args or args[0] not in self.commands:
            # If not a subcommand, prepend the default command name
            args.insert(0, "run")
        return super().parse_args(ctx, args)

    def format_usage(self, ctx, formatter):
        formatter.write_usage(ctx.command_path, "[OPTIONS] PATH [ARGS]...")


@click.group(cls=DefaultCommandGroup, invoke_without_command=True)
@click.option("-v", "--version", is_flag=True, help="Show version and exit.")
@click.pass_context
def main(ctx, version):
    """🪃 Yeet — a terminal git client."""
    if version:
        from yeet import get_version

        click.echo(get_version())
        ctx.exit()
    # If no command and no version flag, let the default command handling proceed
    if ctx.invoked_subcommand is None and not version:
        pass


@main.command("run")
@click.argument("project_dir", metavar="PATH", required=False, default=".")
@click.option(
    "-p",
    "--port",
    metavar="PORT",
    default=8000,
    type=int,
    help="Port to use in conjunction with --serve",
)
@click.option(
    "-H",
    "--host",
    metavar="HOST",
    default="localhost",
    type=str,
    help="Host to use in conjunction with --serve",
)
@click.option(
    "--public-url",
    metavar="URL",
    default=None,
    help="Public URL to use in conjunction with --serve",
)
@click.option("-s", "--serve", is_flag=True, help="Serve Yeet as a web application")
def run(
    port: int,
    host: str,
    serve: bool,
    project_dir: str = ".",
    public_url: str | None = None,
):
    """Run the git client (same as `yeet PATH`)."""

    check_directory(project_dir)

    app = YeetApp(
        project_dir=project_dir,
    )
    if serve:
        import shlex
        from textual_serve.server import Server

        command_args = sys.argv
        # Remove serve flag from args (could be either --serve or -s)
        for flag in ["--serve", "-s"]:
            try:
                command_args.remove(flag)
                break
            except ValueError:
                pass
        serve_command = shlex.join(command_args)
        server = Server(
            serve_command,
            host=host,
            port=port,
            title=serve_command,
            public_url=public_url,
        )
        set_process_title("yeet --serve")
        server.serve()
    else:
        app.run()
    app.run_on_exit()


@main.command("settings")
def settings() -> None:
    """Settings information."""
    app = YeetApp()
    print(f"{app.settings_path}")


@main.command("serve")
@click.option("-p", "--port", metavar="PORT", default=8000, type=int)
@click.option("-H", "--host", metavar="HOST", default="localhost")
@click.option(
    "--public-url",
    metavar="URL",
    default=None,
    help="Public URL for textual_serve Server (e.g. https://example.com)",
)
def serve(port: int, host: str, public_url: str | None = None) -> None:
    """Serve Yeet as a web application."""
    from textual_serve.server import Server

    server = Server(
        sys.argv[0], host=host, port=port, title="Yeet", public_url=public_url
    )
    set_process_title("yeet serve")
    server.serve()

if __name__ == "__main__":
    main()
