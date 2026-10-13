"""Small dependency-free desktop controller for the Hybrid connector.

This is intentionally a Tkinter controller rather than a privileged service:
it starts/stops the existing outbound connector process and never opens a
listening socket. Use register-connector-startup.ps1 to launch it at logon.
"""

import argparse
import subprocess
import sys
import tkinter as tk
from pathlib import Path


class ConnectorController:
    def __init__(self, root, args):
        self.root = root
        self.args = args
        self.process = None
        root.title("Syntax Local AI Connector")
        root.geometry("430x190")
        root.resizable(False, False)
        self.status = tk.StringVar(value="Stopped")
        tk.Label(root, text="Hybrid local connector", font=("Segoe UI", 13, "bold")).pack(pady=(14, 4))
        tk.Label(root, textvariable=self.status, anchor="w").pack(fill="x", padx=22)
        buttons = tk.Frame(root)
        buttons.pack(pady=18)
        tk.Button(buttons, text="Start", width=12, command=self.start).pack(side="left", padx=4)
        tk.Button(buttons, text="Pause", width=12, command=self.stop).pack(side="left", padx=4)
        tk.Button(buttons, text="Exit", width=12, command=self.close).pack(side="left", padx=4)
        root.protocol("WM_DELETE_WINDOW", self.close)
        self.refresh()
        if args.autostart:
            self.start()

    def command(self):
        connector = Path(self.args.connector).resolve()
        command = [
            sys.executable,
            str(connector),
            "--server-url",
            self.args.server_url,
            "--token",
            self.args.token,
            "--workspace",
            self.args.workspace,
            "--ollama-url",
            self.args.ollama_url,
        ]
        return command

    def start(self):
        if self.process and self.process.poll() is None:
            self.status.set("Running")
            return
        try:
            self.process = subprocess.Popen(self.command(), creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            self.status.set("Running")
        except OSError as exc:
            self.status.set("Unable to start: " + str(exc))

    def stop(self):
        if self.process and self.process.poll() is None:
            self.process.terminate()
            self.status.set("Paused")
        else:
            self.status.set("Stopped")

    def refresh(self):
        if self.process and self.process.poll() is not None:
            self.status.set("Stopped (exit %s)" % self.process.returncode)
        self.root.after(1000, self.refresh)

    def close(self):
        self.stop()
        self.root.destroy()


def main():
    parser = argparse.ArgumentParser(description="Control the outbound Syntax Local AI connector.")
    parser.add_argument("--server-url", required=True)
    parser.add_argument("--token", required=True)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--connector", default=str(Path(__file__).with_name("local_connector.py")))
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    parser.add_argument("--autostart", action="store_true")
    args = parser.parse_args()
    if not Path(args.workspace).expanduser().is_dir():
        parser.error("--workspace must be an existing directory")
    root = tk.Tk()
    ConnectorController(root, args)
    root.mainloop()


if __name__ == "__main__":
    main()
