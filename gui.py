import argparse
import os
import queue
import re
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

try:
    from app import run_scrape
except ModuleNotFoundError as exc:
    dependency_error = tk.Tk()
    dependency_error.withdraw()
    messagebox.showerror(
        "Missing dependency",
        f"A required Python package is missing: {exc.name}\n\nRun install.bat, then start the application again.",
    )
    dependency_error.destroy()
    raise SystemExit(1) from exc


class ScraperGUI(tk.Tk):
    TABLE_COLUMNS = ("provider_name", "town_or_location", "website", "email", "phone")

    def __init__(self):
        super().__init__()
        self.root_dir = Path(__file__).resolve().parent
        self.title("UK Training Provider Scraper")
        self.geometry("1120x720")
        self.minsize(820, 580)
        self.events = queue.Queue()
        self.counter_vars = {name: tk.StringVar(value="0") for name in ("processed", "emails", "phones", "websites", "locations")}
        self.total = 0
        self._build()
        self.after(100, self._drain_events)

    def _build(self):
        frame = ttk.Frame(self, padding=14)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(1, weight=1)

        ttk.Label(frame, text="Directory").grid(row=0, column=0, sticky="w", pady=4)
        self.scraper = tk.StringVar(value="CITB")
        ttk.Combobox(frame, textvariable=self.scraper, values=("CITB",), state="readonly").grid(row=0, column=1, sticky="ew", pady=4)
        ttk.Label(frame, text="Limit").grid(row=1, column=0, sticky="w", pady=4)
        self.limit = tk.StringVar(value="50")
        ttk.Entry(frame, textvariable=self.limit).grid(row=1, column=1, sticky="ew", pady=4)
        ttk.Label(frame, text="Leave empty to scrape all providers", foreground="#666666").grid(row=2, column=1, sticky="w", pady=(0, 4))
        self.find_emails = tk.BooleanVar(value=True)
        ttk.Checkbutton(frame, text="Search missing emails on provider websites", variable=self.find_emails).grid(row=3, column=1, sticky="w", pady=4)
        ttk.Label(frame, text="Output name").grid(row=4, column=0, sticky="w", pady=4)
        self.output_name = tk.StringVar(value="citb_export")
        ttk.Entry(frame, textvariable=self.output_name).grid(row=4, column=1, sticky="ew", pady=4)

        actions = ttk.Frame(frame)
        actions.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(10, 6))
        self.start_button = ttk.Button(actions, text="Start", command=self._start)
        self.start_button.pack(side="left")
        ttk.Button(actions, text="Open outputs folder", command=self._open_outputs).pack(side="left", padx=8)

        counters = ttk.LabelFrame(frame, text="Live progress", padding=8)
        counters.grid(row=6, column=0, columnspan=2, sticky="ew", pady=6)
        labels = (("Processed", "processed"), ("Emails", "emails"), ("Phones", "phones"), ("Websites", "websites"), ("Locations", "locations"))
        for index, (label, key) in enumerate(labels):
            ttk.Label(counters, text=label + ":").grid(row=0, column=index * 2, padx=(6, 2))
            ttk.Label(counters, textvariable=self.counter_vars[key], width=9).grid(row=0, column=index * 2 + 1, padx=(0, 12))

        table_frame = ttk.Frame(frame)
        table_frame.grid(row=7, column=0, columnspan=2, sticky="nsew", pady=6)
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)
        self.table = ttk.Treeview(table_frame, columns=self.TABLE_COLUMNS, show="headings", height=15)
        headings = {
            "provider_name": "Provider name", "town_or_location": "Town / location",
            "website": "Website", "email": "Email", "phone": "Phone",
        }
        widths = {"provider_name": 230, "town_or_location": 170, "website": 250, "email": 230, "phone": 120}
        for column in self.TABLE_COLUMNS:
            self.table.heading(column, text=headings[column])
            self.table.column(column, width=widths[column], minwidth=90, stretch=True)
        vertical = ttk.Scrollbar(table_frame, orient="vertical", command=self.table.yview)
        horizontal = ttk.Scrollbar(table_frame, orient="horizontal", command=self.table.xview)
        self.table.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        self.table.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")

        ttk.Label(frame, text="Status").grid(row=8, column=0, columnspan=2, sticky="w")
        self.status = tk.Text(frame, height=7, wrap="word", state="disabled")
        self.status.grid(row=9, column=0, columnspan=2, sticky="nsew")
        frame.rowconfigure(7, weight=4)
        frame.rowconfigure(9, weight=1)

    def _append(self, text):
        self.status.configure(state="normal")
        self.status.insert("end", text + "\n")
        self.status.see("end")
        self.status.configure(state="disabled")

    def _parse_limit(self):
        value = self.limit.get().strip().lower()
        if value in ("", "all"):
            return None
        try:
            number = int(value)
        except ValueError as exc:
            raise ValueError("Limit must be a positive number, empty, or 'all'.") from exc
        if number < 1:
            raise ValueError("Limit must be a positive number, empty, or 'all'.")
        return number

    def _start(self):
        try:
            limit = self._parse_limit()
            output = self.output_name.get().strip()
            if not output or not re.fullmatch(r"[A-Za-z0-9._-]+", output):
                raise ValueError("Output name may contain only letters, numbers, dots, dashes, and underscores.")
        except ValueError as exc:
            messagebox.showerror("Invalid settings", str(exc))
            return
        for item in self.table.get_children():
            self.table.delete(item)
        for variable in self.counter_vars.values():
            variable.set("0")
        self.total = 0
        self.start_button.configure(state="disabled")
        self._append("Starting CITB scrape...")
        threading.Thread(target=self._worker, args=(limit, output, self.find_emails.get()), daemon=True).start()

    def _worker(self, limit, output, find_emails):
        try:
            run_scrape(
                root=self.root_dir, scraper_name="citb", limit=limit,
                find_emails=find_emails, output_name=output,
                progress_callback=self.events.put,
            )
        except PermissionError as exc:
            self.events.put({"type": "error", "message": f"Cannot write the output files. Close any open CSV/XLSX files and try again.\n{exc}"})
        except OSError as exc:
            self.events.put({"type": "error", "message": f"Network or file-system error. Check your connection and output folder, then try again.\n{exc}"})
        except Exception as exc:
            self.events.put({"type": "error", "message": f"The scrape could not be completed.\n{exc}"})

    def _provider_processed(self, event):
        record = event["record"]
        values = tuple(record.get(column, "") for column in self.TABLE_COLUMNS)
        item = self.table.insert("", "end", values=values)
        self.table.see(item)
        processed, total = event["processed"], event["total"]
        self.counter_vars["processed"].set(f"{processed} / {total}")
        if record.get("email") and record["email"] != "not_found":
            self.counter_vars["emails"].set(str(int(self.counter_vars["emails"].get()) + 1))
        for field, counter in (("phone", "phones"), ("website", "websites"), ("town_or_location", "locations")):
            if record.get(field):
                self.counter_vars[counter].set(str(int(self.counter_vars[counter].get()) + 1))
        self._append(f"[{processed}/{total}] {record.get('provider_name', '')}")

    def _drain_events(self):
        try:
            while True:
                event = self.events.get_nowait()
                event_type = event.get("type")
                if event_type == "start":
                    self.total = event["total"]
                    self.counter_vars["processed"].set(f"0 / {self.total}")
                    self._append(f"Found {self.total} providers to process.")
                elif event_type == "provider_processed":
                    self._provider_processed(event)
                elif event_type == "export_complete":
                    self._append(f"CSV: {event['csv_path']}\nXLSX: {event['xlsx_path']}")
                elif event_type == "done":
                    self.start_button.configure(state="normal")
                    summary = (
                        f"Rows exported: {event['rows']}\nCSV: {event['csv_path']}\nXLSX: {event['xlsx_path']}\n"
                        f"Emails found: {event['emails']}\nPhones found: {event['phones']}\n"
                        f"Websites found: {event['websites']}\nLocations found: {event['locations']}"
                    )
                    self._append("Completed.\n" + summary)
                    messagebox.showinfo("Scrape complete", summary)
                elif event_type == "error":
                    self.start_button.configure(state="normal")
                    self._append("Error: " + event["message"])
                    messagebox.showerror("Scrape failed", event["message"])
        except queue.Empty:
            pass
        self.after(100, self._drain_events)

    def _open_outputs(self):
        path = self.root_dir / "outputs"
        path.mkdir(exist_ok=True)
        try:
            os.startfile(path)
        except Exception as exc:
            messagebox.showerror("Cannot open folder", f"Windows could not open the outputs folder.\n{exc}")


def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--test", action="store_true")
    args, _ = parser.parse_known_args()

    if args.test:
        # Headless smoke test: do not create a Tk window.
        # This keeps automated checks working on systems without a display.
        if not callable(run_scrape):
            raise RuntimeError("run_scrape is not callable")
        print("GUI smoke test passed")
        return

    app = ScraperGUI()
    app.mainloop()


if __name__ == "__main__":
    main()
