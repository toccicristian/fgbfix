#!/usr/bin/env python3
"""Reparación vectorial de PDFs defectuosos de Federación Gráfica.

Detecta streams de contenido que declaran ``/FlateDecode`` aunque sus datos
no estén comprimidos con Flate/zlib. La reparación elimina únicamente ese
filtro incorrecto, sustituyéndolo por espacios del mismo largo para no mover
los offsets existentes del archivo.

El módulo puede importarse desde otra aplicación o ejecutarse por terminal.
"""

from __future__ import annotations

import argparse
import re
import sys
import zlib
from collections.abc import Callable
from pathlib import Path

from pypdf import PdfReader

LogCallback = Callable[[str], None]

FILTER_PATTERNS = (
    b"/Filter/FlateDecode",
    b"/Filter /FlateDecode",
)

CONTENT_MARKERS = (
    b" BT",
    b"BT\n",
    b"\nBT",
    b" ET",
    b"ET\n",
    b" Tj",
    b"Tj\n",
    b" TJ",
    b"TJ\n",
    b" Tm",
    b" Td",
    b" TD",
    b" re",
    b" m",
    b" l",
    b" S",
    b" f",
    b" Do",
    b" cm",
    b" q",
    b" Q",
)


class PdfVectorRepairError(RuntimeError):
    """Error durante la reparación vectorial del PDF."""


def _emit(log: LogCallback | None, message: str) -> None:
    if log is not None:
        log(message)


def _get_content_object_numbers(pdf_path: Path) -> set[int]:
    reader = PdfReader(str(pdf_path), strict=False)
    numbers: set[int] = set()

    for page in reader.pages:
        contents = page.get("/Contents")
        if contents is None:
            continue

        refs = contents if isinstance(contents, list) else [contents]

        for ref in refs:
            obj_num = getattr(ref, "idnum", None)
            if obj_num is not None:
                numbers.add(int(obj_num))

    return numbers


def _find_object_region(data: bytes, obj_num: int) -> tuple[int, int]:
    pattern = re.compile(
        rb"(?m)^" + str(obj_num).encode("ascii") + rb"\s+\d+\s+obj\b"
    )
    match = pattern.search(data)

    if match is None:
        raise PdfVectorRepairError(f"No se encontró el objeto {obj_num}.")

    end = data.find(b"endobj", match.end())
    if end < 0:
        raise PdfVectorRepairError(
            f"No se encontró 'endobj' para el objeto {obj_num}."
        )

    return match.start(), end + len(b"endobj")


def _stream_bytes_from_object(obj: bytes) -> bytes | None:
    stream_pos = obj.find(b"stream")
    if stream_pos < 0:
        return None

    header = obj[:stream_pos]
    length_match = re.search(rb"/Length\s+(\d+)", header)
    if length_match is None:
        return None

    length = int(length_match.group(1))
    start = stream_pos + len(b"stream")

    if obj[start : start + 2] == b"\r\n":
        start += 2
    elif obj[start : start + 1] in (b"\r", b"\n"):
        start += 1

    end = start + length
    if end > len(obj):
        return None

    return obj[start:end]


def _looks_like_plain_pdf_content(stream: bytes) -> bool:
    if not stream:
        return False

    sample = stream[:4096]
    printable = sum(
        1
        for byte in sample
        if byte in (9, 10, 13) or 32 <= byte <= 126
    )
    printable_ratio = printable / len(sample)
    marker_count = sum(marker in sample for marker in CONTENT_MARKERS)

    return printable_ratio >= 0.90 and marker_count >= 2


def _flate_is_invalid(stream: bytes) -> bool:
    try:
        zlib.decompress(stream)
        return False
    except zlib.error:
        return True


def repair_pdf_vectorial(
    source: str | Path,
    destination: str | Path,
    *,
    dry_run: bool = False,
    log: LogCallback | None = None,
) -> list[int]:
    """Repara streams de contenido con ``/FlateDecode`` inválido.

    Args:
        source: PDF de origen.
        destination: PDF reparado. No se escribe cuando ``dry_run`` es True.
        dry_run: Detecta defectos sin modificar ni generar archivos.
        log: Callback opcional para recibir mensajes de progreso.

    Returns:
        Lista de números de objeto corregidos.

    Raises:
        FileNotFoundError: Si el PDF de origen no existe.
        PdfVectorRepairError: Si no se encuentran streams reparables o la
            estructura necesaria no puede analizarse.
    """
    source_path = Path(source).expanduser().resolve()
    destination_path = Path(destination).expanduser().resolve()

    if not source_path.is_file():
        raise FileNotFoundError(f"No existe el PDF de origen: {source_path}")

    original = source_path.read_bytes()
    repaired = bytearray(original)
    content_objects = sorted(_get_content_object_numbers(source_path))

    _emit(log, "Objetos usados por /Contents:")
    _emit(log, "  " + ", ".join(map(str, content_objects)))

    patched: list[int] = []

    for obj_num in content_objects:
        start, end = _find_object_region(original, obj_num)
        obj = original[start:end]
        stream = _stream_bytes_from_object(obj)

        if stream is None:
            continue

        stream_keyword = obj.find(b"stream")
        filter_pos_local = -1
        filter_token: bytes | None = None

        for candidate in FILTER_PATTERNS:
            pos = obj.find(candidate, 0, stream_keyword)
            if pos >= 0:
                filter_pos_local = pos
                filter_token = candidate
                break

        if filter_token is None:
            continue

        if not _flate_is_invalid(stream):
            continue

        if not _looks_like_plain_pdf_content(stream):
            _emit(
                log,
                f"AVISO: objeto {obj_num}: Flate inválido, pero el stream "
                "no parece contenido PDF en texto plano. No se modifica.",
            )
            continue

        patched.append(obj_num)

        if not dry_run:
            absolute = start + filter_pos_local
            repaired[absolute : absolute + len(filter_token)] = (
                b" " * len(filter_token)
            )

        _emit(
            log,
            f"Objeto {obj_num}: /FlateDecode inválido sobre contenido "
            "sin comprimir -> corregido.",
        )

    if not patched:
        raise PdfVectorRepairError(
            "No se encontraron streams de contenido reparables."
        )

    if dry_run:
        _emit(log, "Modo --dry-run: no se escribió ningún archivo.")
    else:
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        destination_path.write_bytes(repaired)
        _emit(log, f"PDF reparado: {destination_path}")

    _emit(log, "Objetos corregidos: " + ", ".join(map(str, patched)))
    return patched


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Repara streams /FlateDecode inválidos sin rasterizar."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Detecta el problema pero no escribe el PDF reparado.",
    )
    parser.add_argument("origen", type=Path)
    parser.add_argument("destino", type=Path)
    return parser


def main() -> int:
    args = _build_parser().parse_args()

    try:
        repair_pdf_vectorial(
            args.origen,
            args.destino,
            dry_run=args.dry_run,
            log=print,
        )
    except (OSError, PdfVectorRepairError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
