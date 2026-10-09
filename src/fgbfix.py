#!/usr/bin/env python3
"""Interfaz Tkinter para reparar boletas PDF de Federación Gráfica."""

from __future__ import annotations

import queue
import tempfile
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from agregar_campo_vence import PdfFormError, add_vence_field
from vecfix import PdfVectorRepairError, repair_pdf_vectorial

APP_TITLE = "Reparador PDF: Federación Gráfica - by M4r01i0 ;D"
WINDOW_SIZE = "780x560"
MIN_WIDTH = 700
MIN_HEIGHT = 500

Event = tuple[str, object]


class PdfRepairGui(tk.Tk):
    """Ventana principal de la aplicación."""

    def __init__(self) -> None:
        super().__init__()

        self.title(APP_TITLE)
        self.geometry(WINDOW_SIZE)
        self.minsize(MIN_WIDTH, MIN_HEIGHT)

        self.event_queue: queue.Queue[Event] = queue.Queue()
        self.worker: threading.Thread | None = None

        self.source_var = tk.StringVar()
        self.destination_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Listo.")
        self.progress_var = tk.DoubleVar(value=0)

        self._build_ui()
        self.after(100, self._process_events)

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=16)
        root.pack(fill="both", expand=True)
        root.columnconfigure(1, weight=1)
        root.rowconfigure(5, weight=1)

        ttk.Label(
            root,
            text="Reparador de boletas PDF",
            font=("TkDefaultFont", 14, "bold"),
        ).grid(
            row=0,
            column=0,
            columnspan=3,
            sticky="w",
            pady=(0, 16),
        )

        ttk.Label(root, text="PDF de origen:").grid(
            row=1,
            column=0,
            sticky="w",
            padx=(0, 10),
            pady=5,
        )

        self.source_entry = ttk.Entry(root, textvariable=self.source_var)
        self.source_entry.grid(row=1, column=1, sticky="ew", pady=5)

        self.source_button = ttk.Button(
            root,
            text="Examinar...",
            command=self._choose_source,
        )
        self.source_button.grid(
            row=1,
            column=2,
            padx=(10, 0),
            pady=5,
        )

        ttk.Label(root, text="PDF de destino:").grid(
            row=2,
            column=0,
            sticky="w",
            padx=(0, 10),
            pady=5,
        )

        self.destination_entry = ttk.Entry(
            root,
            textvariable=self.destination_var,
        )
        self.destination_entry.grid(row=2, column=1, sticky="ew", pady=5)

        self.destination_button = ttk.Button(
            root,
            text="Guardar como...",
            command=self._choose_destination,
        )
        self.destination_button.grid(
            row=2,
            column=2,
            padx=(10, 0),
            pady=5,
        )

        self.repair_button = ttk.Button(
            root,
            text="REPARAR",
            command=self._start_repair,
        )
        self.repair_button.grid(
            row=3,
            column=0,
            columnspan=3,
            sticky="ew",
            pady=(15, 15),
        )

        self._build_progress_area(root)
        self._build_log_area(root)

    def _build_progress_area(self, parent: ttk.Frame) -> None:
        frame = ttk.Frame(parent)
        frame.grid(
            row=4,
            column=0,
            columnspan=3,
            sticky="ew",
            pady=(0, 12),
        )
        frame.columnconfigure(0, weight=1)

        ttk.Progressbar(
            frame,
            variable=self.progress_var,
            maximum=100,
            mode="determinate",
        ).grid(row=0, column=0, sticky="ew")

        ttk.Label(
            frame,
            textvariable=self.status_var,
        ).grid(row=1, column=0, sticky="w", pady=(6, 0))

    def _build_log_area(self, parent: ttk.Frame) -> None:
        frame = ttk.LabelFrame(parent, text="Registro", padding=8)
        frame.grid(
            row=5,
            column=0,
            columnspan=3,
            sticky="nsew",
        )
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)

        self.log_text = tk.Text(
            frame,
            wrap="word",
            height=15,
            state="disabled",
        )
        self.log_text.grid(row=0, column=0, sticky="nsew")

        scrollbar = ttk.Scrollbar(
            frame,
            orient="vertical",
            command=self.log_text.yview,
        )
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.log_text.configure(yscrollcommand=scrollbar.set)

    def _choose_source(self) -> None:
        selected = filedialog.askopenfilename(
            title="Seleccionar PDF roto",
            filetypes=[
                ("Documentos PDF", "*.pdf"),
                ("Todos los archivos", "*.*"),
            ],
        )

        if not selected:
            return

        self.source_var.set(selected)

        if not self.destination_var.get().strip():
            source = Path(selected)
            suggested = source.with_name(f"{source.stem}_REPARADO.pdf")
            self.destination_var.set(str(suggested))

    def _choose_destination(self) -> None:
        source_text = self.source_var.get().strip()

        if source_text:
            source = Path(source_text)
            initial_dir = str(source.parent)
            initial_file = f"{source.stem}_REPARADO.pdf"
        else:
            initial_dir = str(Path.home())
            initial_file = "boleta_REPARADA.pdf"

        selected = filedialog.asksaveasfilename(
            title="Guardar PDF final",
            defaultextension=".pdf",
            filetypes=[("Documentos PDF", "*.pdf")],
            initialdir=initial_dir,
            initialfile=initial_file,
        )

        if selected:
            self.destination_var.set(selected)

    def _append_log(self, text: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", text)

        if not text.endswith("\n"):
            self.log_text.insert("end", "\n")

        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _clear_log(self) -> None:
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    def _set_busy(self, busy: bool) -> None:
        state = "disabled" if busy else "normal"
        widgets = (
            self.source_entry,
            self.destination_entry,
            self.source_button,
            self.destination_button,
            self.repair_button,
        )

        for widget in widgets:
            widget.configure(state=state)

    def _validate_paths(self) -> tuple[Path, Path] | None:
        source_text = self.source_var.get().strip()
        destination_text = self.destination_var.get().strip()

        if not source_text:
            messagebox.showwarning(APP_TITLE, "Seleccioná el PDF de origen.")
            return None

        if not destination_text:
            messagebox.showwarning(
                APP_TITLE,
                "Elegí la ruta y el nombre del PDF de destino.",
            )
            return None

        source = Path(source_text).expanduser().resolve()
        destination = Path(destination_text).expanduser().resolve()

        if not source.is_file():
            messagebox.showerror(
                APP_TITLE,
                f"No existe el archivo de origen:\n{source}",
            )
            return None

        if source.suffix.lower() != ".pdf":
            messagebox.showerror(
                APP_TITLE,
                "El archivo de origen debe ser un PDF.",
            )
            return None

        if destination.suffix.lower() != ".pdf":
            destination = destination.with_suffix(".pdf")
            self.destination_var.set(str(destination))

        if source == destination:
            messagebox.showerror(
                APP_TITLE,
                "El archivo de destino debe ser distinto del original.",
            )
            return None

        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            messagebox.showerror(
                APP_TITLE,
                f"No se pudo preparar la carpeta de destino:\n{exc}",
            )
            return None

        if destination.exists() and not messagebox.askyesno(
            APP_TITLE,
            "El archivo de destino ya existe.\n\n¿Querés reemplazarlo?",
        ):
            return None

        return source, destination

    def _start_repair(self) -> None:
        validated = self._validate_paths()
        if validated is None:
            return

        source, destination = validated

        self._clear_log()
        self.progress_var.set(0)
        self.status_var.set("Preparando reparación...")
        self._set_busy(True)

        self._append_log(f"Origen: {source}")
        self._append_log(f"Destino: {destination}")
        self._append_log("")

        self.worker = threading.Thread(
            target=self._repair_worker,
            args=(source, destination),
            daemon=True,
        )
        self.worker.start()

    def _queue_log(self, message: str) -> None:
        self.event_queue.put(("log", message))

    def _queue_progress(self, percent: int, status: str) -> None:
        self.event_queue.put(("progress", (percent, status)))

    def _repair_worker(self, source: Path, destination: Path) -> None:
        try:
            self._queue_progress(10, "Preparando archivo temporal...")

            with tempfile.TemporaryDirectory(
                prefix="federacion_pdf_",
                dir=destination.parent,
            ) as temp_dir:
                intermediate = Path(temp_dir) / "vectorial_reparado.pdf"

                self._queue_log("=== ETAPA 1: REPARACIÓN VECTORIAL ===")
                self._queue_progress(20, "Reparando estructura vectorial...")

                patched = repair_pdf_vectorial(
                    source,
                    intermediate,
                    log=self._queue_log,
                )

                self._queue_progress(60, "Reparación vectorial completada.")
                self._queue_log(
                    f"Streams corregidos: {len(patched)}."
                )
                self._queue_log("")

                self._queue_log("=== ETAPA 2: CAMPO VENCE EL ===")
                self._queue_progress(70, "Agregando el campo VENCE EL...")

                add_vence_field(
                    intermediate,
                    destination,
                    log=self._queue_log,
                )

            self._queue_progress(95, "Verificando el archivo final...")

            if not destination.is_file() or destination.stat().st_size == 0:
                raise RuntimeError(
                    "El PDF final no se creó correctamente."
                )

            self._queue_log("")
            self._queue_log("=== PROCESO COMPLETADO ===")
            self._queue_log(f"Archivo final: {destination}")
            self._queue_progress(
                100,
                "Reparación completada correctamente.",
            )
            self.event_queue.put(("done", destination))

        except (
            FileNotFoundError,
            OSError,
            PdfVectorRepairError,
            PdfFormError,
            RuntimeError,
        ) as exc:
            self._queue_log("")
            self._queue_log(f"ERROR: {exc}")
            self._queue_progress(0, "La reparación no pudo completarse.")
            self.event_queue.put(("error", str(exc)))

        finally:
            self.event_queue.put(("idle", None))

    def _process_events(self) -> None:
        try:
            while True:
                event, value = self.event_queue.get_nowait()

                if event == "log":
                    self._append_log(str(value))

                elif event == "progress":
                    percent, status = value  # type: ignore[misc]
                    self.progress_var.set(percent)
                    self.status_var.set(status)

                elif event == "done":
                    messagebox.showinfo(
                        APP_TITLE,
                        "El PDF fue reparado correctamente.\n\n"
                        f"Archivo generado:\n{value}",
                    )

                elif event == "error":
                    messagebox.showerror(
                        APP_TITLE,
                        f"Error durante la reparación:\n\n{value}",
                    )

                elif event == "idle":
                    self._set_busy(False)

        except queue.Empty:
            pass

        self.after(100, self._process_events)


def main() -> None:
    app = PdfRepairGui()
    app.mainloop()


if __name__ == "__main__":
    main()
