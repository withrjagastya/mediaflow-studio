"""Optional lightweight Windows/macOS/Linux GUI (Tkinter, no pip installs)."""
from __future__ import annotations

from pathlib import Path
import queue
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk


class Studio(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("MediaFlow Studio — Video Batch Processor")
        self.geometry("770x580")
        self.minsize(630, 450)
        self.input_path = tk.StringVar()
        self.output_path = tk.StringVar()
        self.mode = tk.StringVar(value="pad")
        self.preset_selection = {key: tk.BooleanVar(value=key != "preview")
                                 for key in ("reel", "square", "landscape", "preview")}
        self.events = queue.Queue()
        self.process = None
        self.work_thread = None
        self._layout()
        self.after(150, self.drain_events)
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def _layout(self):
        top = ttk.Frame(self, padding=18)
        top.pack(fill="both", expand=True)
        ttk.Label(top, text="MediaFlow Studio", font=("Segoe UI", 20, "bold")).pack(anchor="w")
        ttk.Label(top, text="One video in. Multiple formats, thumbnails and QC reports out.").pack(anchor="w", pady=(3, 16))
        self.folder_picker(top, "Source video folder", self.input_path)
        self.folder_picker(top, "Export folder", self.output_path)
        select = ttk.LabelFrame(top, text="Export formats", padding=10)
        select.pack(fill="x", pady=(8, 8))
        for name, var in self.preset_selection.items():
            ttk.Checkbutton(select, text=name.title(), variable=var).pack(side="left", padx=(4, 18))
        settings = ttk.Frame(top)
        settings.pack(fill="x", pady=(4, 14))
        ttk.Label(settings, text="Framing:").pack(side="left", padx=(0, 8))
        ttk.Radiobutton(settings, text="Fit whole video (bars)", variable=self.mode, value="pad").pack(side="left")
        ttk.Radiobutton(settings, text="Fill frame (crop edges)", variable=self.mode, value="crop").pack(side="left", padx=(15, 0))
        actions = ttk.Frame(top)
        actions.pack(fill="x")
        self.start_btn = ttk.Button(actions, text="Build videos", command=self.start)
        self.start_btn.pack(side="left")
        ttk.Button(actions, text="Stop", command=self.stop).pack(side="left", padx=10)
        ttk.Label(top, text="Logs", font=("Segoe UI", 10, "bold")).pack(anchor="w", pady=(15, 5))
        self.log = tk.Text(top, height=12, wrap="word", state="disabled")
        self.log.pack(fill="both", expand=True)
        ttk.Label(top, text="Requires Python 3.10+ and FFmpeg installed on your computer.").pack(anchor="w", pady=(8, 0))

    def folder_picker(self, parent, title, variable):
        ttk.Label(parent, text=title).pack(anchor="w")
        frame = ttk.Frame(parent)
        frame.pack(fill="x", pady=(2, 10))
        ttk.Entry(frame, textvariable=variable).pack(side="left", fill="x", expand=True)
        ttk.Button(frame, text="Browse", command=lambda: variable.set(filedialog.askdirectory() or variable.get())).pack(side="left", padx=(8, 0))

    def append(self, text):
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def start(self):
        src, dest = Path(self.input_path.get()), Path(self.output_path.get())
        selected = [name for name, selected in self.preset_selection.items() if selected.get()]
        if not self.input_path.get() or not src.is_dir():
            messagebox.showerror("Input missing", "Select an existing folder containing videos.")
            return
        if not self.output_path.get() or not selected:
            messagebox.showerror("Missing setting", "Select an export folder and at least one preset.")
            return
        cmd = [sys.executable, "-u", "-m", "mediaflow", "build", "--input", str(src),
               "--output", str(dest), "--mode", self.mode.get(), "--presets", *selected]
        self.start_btn.configure(state="disabled")
        self.append("Starting batch build...")
        self.work_thread = threading.Thread(target=self.run_worker, args=(cmd,), daemon=True)
        self.work_thread.start()

    def run_worker(self, command):
        try:
            self.process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                            text=True, encoding="utf-8", errors="replace", bufsize=1)
            for line in self.process.stdout:
                self.events.put(line.rstrip())
            exit_code = self.process.wait()
            self.events.put(f"Finished with exit code {exit_code}.")
        except Exception as exc:
            self.events.put(f"ERROR: {exc}")
        finally:
            self.process = None
            self.events.put(None)

    def drain_events(self):
        try:
            while True:
                item = self.events.get_nowait()
                if item is None:
                    self.start_btn.configure(state="normal")
                else:
                    self.append(item)
        except queue.Empty:
            pass
        self.after(150, self.drain_events)

    def stop(self):
        if self.process and self.process.poll() is None:
            self.process.terminate()
            self.append("Stop requested. Active FFmpeg operations may continue briefly.")

    def on_close(self):
        if self.process and self.process.poll() is None:
            if not messagebox.askyesno("Close MediaFlow?", "A build is running. Exit anyway?"):
                return
            self.stop()
        self.destroy()


def main():
    Studio().mainloop()


if __name__ == "__main__":
    main()
