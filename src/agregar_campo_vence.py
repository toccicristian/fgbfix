#!/usr/bin/env python3
"""Agrega el campo AcroForm ``VENCE_EL`` a una boleta reparada.

El campo lógico posee dos widgets: uno para el comprobante del banco y otro
para el comprobante del depositante. Los widgets no dibujan borde ni fondo,
por lo que se conserva el aspecto gráfico original de la boleta.

El módulo puede importarse desde otra aplicación o ejecutarse por terminal.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Sequence
from pathlib import Path

from pypdf import PdfReader, PdfWriter
from pypdf.generic import (
    ArrayObject,
    BooleanObject,
    DecodedStreamObject,
    DictionaryObject,
    FloatObject,
    NameObject,
    NumberObject,
    TextStringObject,
)

LogCallback = Callable[[str], None]
Rect = tuple[float, float, float, float]

FIELD_NAME = "VENCE_EL"
DEFAULT_APPEARANCE = "/Helv 9 Tf 0 g"

# Coordenadas PDF en puntos; origen en la esquina inferior izquierda.
RECT_BANCO: Rect = (468.0, 648.0, 552.0, 659.0)
RECT_DEPOSITANTE: Rect = (468.0, 320.0, 552.0, 331.0)
WIDGET_RECTS: tuple[Rect, Rect] = (RECT_BANCO, RECT_DEPOSITANTE)


class PdfFormError(RuntimeError):
    """Error al construir el campo AcroForm."""


def _emit(log: LogCallback | None, message: str) -> None:
    if log is not None:
        log(message)


def _make_transparent_appearance(
    width: float,
    height: float,
) -> DecodedStreamObject:
    """Crea una apariencia inicial válida, vacía y transparente."""
    stream = DecodedStreamObject()
    stream.set_data(b"q\nQ\n")
    stream.update(
        {
            NameObject("/Type"): NameObject("/XObject"),
            NameObject("/Subtype"): NameObject("/Form"),
            NameObject("/BBox"): ArrayObject(
                [
                    FloatObject(0),
                    FloatObject(0),
                    FloatObject(width),
                    FloatObject(height),
                ]
            ),
            NameObject("/Resources"): DictionaryObject(),
        }
    )
    return stream


def _ensure_acroform(writer: PdfWriter) -> DictionaryObject:
    root = writer._root_object
    acroform_ref = root.get("/AcroForm")

    if acroform_ref is None:
        acroform = DictionaryObject()
        root[NameObject("/AcroForm")] = writer._add_object(acroform)
        return acroform

    return acroform_ref.get_object()


def _ensure_helvetica(
    writer: PdfWriter,
    acroform: DictionaryObject,
) -> None:
    dr_ref = acroform.get("/DR")
    if dr_ref is None:
        dr = DictionaryObject()
        acroform[NameObject("/DR")] = dr
    else:
        dr = dr_ref.get_object()

    fonts_ref = dr.get("/Font")
    if fonts_ref is None:
        fonts = DictionaryObject()
        dr[NameObject("/Font")] = fonts
    else:
        fonts = fonts_ref.get_object()

    if "/Helv" not in fonts:
        helvetica = DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Helvetica"),
                NameObject("/Encoding"): NameObject("/WinAnsiEncoding"),
            }
        )
        fonts[NameObject("/Helv")] = writer._add_object(helvetica)


def _ensure_fields(acroform: DictionaryObject) -> ArrayObject:
    fields_ref = acroform.get("/Fields")

    if fields_ref is None:
        fields = ArrayObject()
        acroform[NameObject("/Fields")] = fields
        return fields

    return fields_ref.get_object()


def _ensure_annots(page: DictionaryObject) -> ArrayObject:
    annots_ref = page.get("/Annots")

    if annots_ref is None:
        annots = ArrayObject()
        page[NameObject("/Annots")] = annots
        return annots

    return annots_ref.get_object()


def _field_exists(fields: Sequence[object], field_name: str) -> bool:
    for field_ref in fields:
        try:
            field = field_ref.get_object()  # type: ignore[attr-defined]
        except AttributeError:
            field = field_ref

        if isinstance(field, DictionaryObject) and field.get("/T") == field_name:
            return True

    return False


def add_vence_field(
    input_pdf: str | Path,
    output_pdf: str | Path,
    *,
    log: LogCallback | None = None,
) -> None:
    """Agrega un único campo lógico ``VENCE_EL`` con dos widgets.

    Args:
        input_pdf: PDF previamente reparado por ``vecfix.py``.
        output_pdf: Ruta del PDF final.
        log: Callback opcional para recibir mensajes de progreso.

    Raises:
        FileNotFoundError: Si el PDF de entrada no existe.
        PdfFormError: Si no hay páginas o el campo ya existe.
    """
    input_path = Path(input_pdf).expanduser().resolve()
    output_path = Path(output_pdf).expanduser().resolve()

    if not input_path.is_file():
        raise FileNotFoundError(f"No existe el PDF de entrada: {input_path}")

    reader = PdfReader(str(input_path), strict=False)
    writer = PdfWriter()

    for page in reader.pages:
        writer.add_page(page)

    if not writer.pages:
        raise PdfFormError("El PDF no contiene páginas.")

    page = writer.pages[0]
    acroform = _ensure_acroform(writer)
    _ensure_helvetica(writer, acroform)

    acroform[NameObject("/DA")] = TextStringObject(DEFAULT_APPEARANCE)
    acroform[NameObject("/NeedAppearances")] = BooleanObject(False)

    fields = _ensure_fields(acroform)
    if _field_exists(fields, FIELD_NAME):
        raise PdfFormError(
            f"El PDF ya contiene un campo llamado {FIELD_NAME!r}."
        )

    field = DictionaryObject(
        {
            NameObject("/FT"): NameObject("/Tx"),
            NameObject("/T"): TextStringObject(FIELD_NAME),
            NameObject("/V"): TextStringObject(""),
            NameObject("/DV"): TextStringObject(""),
            NameObject("/DA"): TextStringObject(DEFAULT_APPEARANCE),
            NameObject("/Ff"): NumberObject(0),
            NameObject("/Q"): NumberObject(1),
        }
    )
    field_ref = writer._add_object(field)
    widgets = ArrayObject()
    annots = _ensure_annots(page)

    for rect in WIDGET_RECTS:
        x1, y1, x2, y2 = rect
        width = x2 - x1
        height = y2 - y1

        appearance_ref = writer._add_object(
            _make_transparent_appearance(width, height)
        )
        appearance = DictionaryObject(
            {NameObject("/N"): appearance_ref}
        )

        widget = DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Annot"),
                NameObject("/Subtype"): NameObject("/Widget"),
                NameObject("/Rect"): ArrayObject(
                    [FloatObject(value) for value in rect]
                ),
                NameObject("/Parent"): field_ref,
                NameObject("/P"): page.indirect_reference,
                NameObject("/F"): NumberObject(4),
                NameObject("/AP"): appearance,
                NameObject("/Border"): ArrayObject(
                    [NumberObject(0), NumberObject(0), NumberObject(0)]
                ),
            }
        )

        widget_ref = writer._add_object(widget)
        widgets.append(widget_ref)
        annots.append(widget_ref)

    field[NameObject("/Kids")] = widgets
    fields.append(field_ref)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("wb") as output_file:
        writer.write(output_file)

    _emit(log, f"PDF final creado: {output_path}")
    _emit(log, f"Campo lógico agregado: {FIELD_NAME}")
    _emit(log, f"Widgets creados: {len(widgets)}")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Agrega el campo VENCE_EL a una boleta PDF reparada."
    )
    parser.add_argument("entrada", type=Path)
    parser.add_argument("salida", type=Path)
    return parser


def main() -> int:
    args = _build_parser().parse_args()

    try:
        add_vence_field(args.entrada, args.salida, log=print)
    except (OSError, PdfFormError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
