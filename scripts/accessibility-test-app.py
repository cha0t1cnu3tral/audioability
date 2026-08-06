#!/usr/bin/env python3
"""Native GTK controls for interactive AT-SPI screen-reader testing."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk  # noqa: E402


class TestWindow(Gtk.Window):
    def __init__(self) -> None:
        super().__init__(title="Audioability Accessibility Test")
        self.set_border_width(18)
        self.set_default_size(560, 420)
        self.connect("destroy", Gtk.main_quit)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.add(box)

        heading = Gtk.Label(label="Audioability native GTK control test")
        heading.set_xalign(0)
        heading.get_accessible().set_name("Audioability test heading")
        box.pack_start(heading, False, False, 0)

        name_label = Gtk.Label(label="Name")
        name_label.set_xalign(0)
        box.pack_start(name_label, False, False, 0)
        name_entry = Gtk.Entry()
        name_entry.set_placeholder_text("Type your name")
        name_entry.get_accessible().set_name("Name")
        name_entry.get_accessible().set_description("Enter a name for this test")
        box.pack_start(name_entry, False, False, 0)

        enabled = Gtk.CheckButton(label="Enable notifications")
        enabled.set_active(True)
        box.pack_start(enabled, False, False, 0)

        choice_label = Gtk.Label(label="Priority")
        choice_label.set_xalign(0)
        box.pack_start(choice_label, False, False, 0)
        priority = Gtk.ComboBoxText()
        for value in ("Low", "Normal", "High"):
            priority.append_text(value)
        priority.set_active(1)
        priority.get_accessible().set_name("Priority")
        box.pack_start(priority, False, False, 0)

        volume = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 10)
        volume.set_value(50)
        volume.set_hexpand(True)
        volume.get_accessible().set_name("Test volume")
        box.pack_start(volume, False, False, 0)

        status = Gtk.Label(label="Ready. Move with Tab and Shift+Tab.")
        status.set_xalign(0)
        status.get_accessible().set_name("Test status")
        box.pack_start(status, False, False, 0)

        button_row = Gtk.Box(spacing=10)
        submit = Gtk.Button(label="Submit test")
        submit.connect(
            "clicked",
            lambda _button: status.set_text(
                f"Submitted for {name_entry.get_text() or 'anonymous'}"
            ),
        )
        reset = Gtk.Button(label="Reset")
        reset.connect("clicked", lambda _button: name_entry.set_text(""))
        button_row.pack_start(submit, False, False, 0)
        button_row.pack_start(reset, False, False, 0)
        box.pack_start(button_row, False, False, 0)


window = TestWindow()
window.show_all()
Gtk.main()
