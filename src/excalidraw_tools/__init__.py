"""Excalidraw diagram tools: create, edit, validate, and preview."""

__version__ = "0.1.0"

from excalidraw_tools.lib import (
    IdFactory,
    add_label,
    connect,
    load_diagram,
    make_arrow,
    make_shape,
    make_text,
    new_document,
    save_diagram,
)
from excalidraw_tools.spec import diagram_to_spec, sync_spec_for_data, sync_spec_for_diagram
from excalidraw_tools.validate import validate_document, validate_file
