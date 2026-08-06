#!/usr/bin/env python3
"""Native GTK edge cases for interactive AT-SPI screen-reader testing."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk  # noqa: E402


class TestWindow(Gtk.Window):
    def __init__(self) -> None:
        super().__init__(title="Audioability Accessibility Edge-Case Lab")
        self.set_border_width(12)
        self.set_default_size(760, 650)
        self.connect("destroy", Gtk.main_quit)
        self.progress_value = 0.0

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        self.add(root)
        root.pack_start(self._build_menu(), False, False, 0)

        intro = Gtk.Label(
            label="Audioability test lab — use Tab, Shift+Tab, arrows, menus, and browse mode."
        )
        intro.set_xalign(0)
        intro.set_line_wrap(True)
        intro.get_accessible().set_name("Audioability edge-case test instructions")
        root.pack_start(intro, False, False, 0)

        notebook = Gtk.Notebook()
        notebook.set_scrollable(True)
        notebook.get_accessible().set_name("Accessibility test categories")
        notebook.append_page(self._build_form_page(), Gtk.Label(label="Form controls"))
        notebook.append_page(self._build_text_page(), Gtk.Label(label="Text and data"))
        notebook.append_page(self._build_dynamic_page(), Gtk.Label(label="Dynamic states"))
        root.pack_start(notebook, True, True, 0)

        self.status = Gtk.Statusbar()
        self.status_context = self.status.get_context_id("test")
        self.set_status("Ready. Audioability is collecting detailed diagnostics.")
        root.pack_end(self.status, False, False, 0)

    def _build_menu(self) -> Gtk.MenuBar:
        menu_bar = Gtk.MenuBar()
        file_item = Gtk.MenuItem.new_with_mnemonic("_File")
        file_menu = Gtk.Menu()
        dialog_item = Gtk.MenuItem.new_with_mnemonic("_Open test dialog")
        dialog_item.connect("activate", self._show_dialog)
        disabled_item = Gtk.MenuItem(label="Unavailable action")
        disabled_item.set_sensitive(False)
        quit_item = Gtk.MenuItem.new_with_mnemonic("_Quit")
        quit_item.connect("activate", lambda _item: Gtk.main_quit())
        file_menu.append(dialog_item)
        file_menu.append(disabled_item)
        file_menu.append(Gtk.SeparatorMenuItem())
        file_menu.append(quit_item)
        file_item.set_submenu(file_menu)

        options_item = Gtk.MenuItem.new_with_mnemonic("_Options")
        options_menu = Gtk.Menu()
        check_item = Gtk.CheckMenuItem(label="Announce updates")
        check_item.set_active(True)
        options_menu.append(check_item)
        options_item.set_submenu(options_menu)

        menu_bar.append(file_item)
        menu_bar.append(options_item)
        return menu_bar

    def _build_form_page(self) -> Gtk.Widget:
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        page.set_border_width(12)

        name_label = Gtk.Label.new_with_mnemonic("_Name")
        name_label.set_xalign(0)
        name_entry = Gtk.Entry()
        name_entry.set_placeholder_text("Type your full name")
        name_entry.get_accessible().set_name("Full name")
        name_entry.get_accessible().set_description(
            "Editable field used to test focus mode and typed character echo"
        )
        name_label.set_mnemonic_widget(name_entry)
        page.pack_start(name_label, False, False, 0)
        page.pack_start(name_entry, False, False, 0)

        password_label = Gtk.Label.new_with_mnemonic("_Password")
        password_label.set_xalign(0)
        password = Gtk.Entry()
        password.set_visibility(False)
        password.set_invisible_char("•")
        password.get_accessible().set_name("Test password")
        password.get_accessible().set_description("Characters must be announced as star")
        password_label.set_mnemonic_widget(password)
        page.pack_start(password_label, False, False, 0)
        page.pack_start(password, False, False, 0)

        notify = Gtk.CheckButton(label="Enable notifications")
        notify.set_active(True)
        page.pack_start(notify, False, False, 0)

        radio_label = Gtk.Label(label="Delivery speed")
        radio_label.set_xalign(0)
        page.pack_start(radio_label, False, False, 0)
        standard = Gtk.RadioButton.new_with_label_from_widget(None, "Standard")
        express = Gtk.RadioButton.new_with_label_from_widget(standard, "Express")
        page.pack_start(standard, False, False, 0)
        page.pack_start(express, False, False, 0)

        priority = Gtk.ComboBoxText()
        for value in ("Low", "Normal", "High", "Critical — requires confirmation"):
            priority.append_text(value)
        priority.set_active(1)
        priority.get_accessible().set_name("Priority")
        page.pack_start(priority, False, False, 0)

        quantity = Gtk.SpinButton.new_with_range(0, 25, 1)
        quantity.set_value(3)
        quantity.get_accessible().set_name("Quantity")
        page.pack_start(quantity, False, False, 0)

        volume = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 5)
        volume.set_value(50)
        volume.set_hexpand(True)
        volume.get_accessible().set_name("Test volume")
        page.pack_start(volume, False, False, 0)

        toggle = Gtk.ToggleButton(label="Toggle advanced mode")
        toggle.connect("toggled", self._toggle_advanced)
        page.pack_start(toggle, False, False, 0)
        unavailable = Gtk.Button(label="Disabled submit button")
        unavailable.set_sensitive(False)
        page.pack_start(unavailable, False, False, 0)

        return self._scroll(page)

    def _build_text_page(self) -> Gtk.Widget:
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        page.set_border_width(12)

        text_label = Gtk.Label(label="Multiline notes")
        text_label.set_xalign(0)
        page.pack_start(text_label, False, False, 0)
        text_view = Gtk.TextView()
        text_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        text_view.get_buffer().set_text(
            "First line with punctuation: comma, semicolon; question?\n"
            "Second line has Unicode: café, naïve, résumé, 東京, and emoji 🚀."
        )
        text_view.get_accessible().set_name("Multiline notes editor")
        text_scroll = Gtk.ScrolledWindow()
        text_scroll.set_min_content_height(130)
        text_scroll.add(text_view)
        page.pack_start(text_scroll, False, True, 0)

        expander = Gtk.Expander(label="Nested advanced settings")
        nested = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        nested.set_border_width(8)
        nested.pack_start(Gtk.CheckButton(label="Nested check box"), False, False, 0)
        nested_entry = Gtk.Entry()
        nested_entry.set_placeholder_text("Nested editable field")
        nested_entry.get_accessible().set_name("Nested value")
        nested.pack_start(nested_entry, False, False, 0)
        expander.add(nested)
        page.pack_start(expander, False, False, 0)

        link = Gtk.LinkButton.new_with_label("https://example.com", "Example accessible link")
        page.pack_start(link, False, False, 0)

        store = Gtk.ListStore(str, str, bool)
        for row in (
            ("Alpha", "Ready", True),
            ("Bravo", "Needs review", False),
            ("Charlie with a deliberately long name", "Blocked", True),
        ):
            store.append(row)
        tree = Gtk.TreeView(model=store)
        for index, title in enumerate(("Item", "Status")):
            tree.append_column(Gtk.TreeViewColumn(title, Gtk.CellRendererText(), text=index))
        tree.append_column(
            Gtk.TreeViewColumn("Enabled", Gtk.CellRendererToggle(), active=2)
        )
        tree.get_accessible().set_name("Project status table")
        tree_scroll = Gtk.ScrolledWindow()
        tree_scroll.set_min_content_height(150)
        tree_scroll.add(tree)
        page.pack_start(tree_scroll, True, True, 0)

        return page

    def _build_dynamic_page(self) -> Gtk.Widget:
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        page.set_border_width(12)

        self.progress = Gtk.ProgressBar()
        self.progress.set_show_text(True)
        self.progress.set_text("Idle")
        self.progress.get_accessible().set_name("Background task progress")
        page.pack_start(self.progress, False, False, 0)

        advance = Gtk.Button(label="Advance progress by 10 percent")
        advance.connect("clicked", self._advance_progress)
        page.pack_start(advance, False, False, 0)

        dialog = Gtk.Button(label="Open modal confirmation dialog")
        dialog.connect("clicked", self._show_dialog)
        page.pack_start(dialog, False, False, 0)

        alert = Gtk.Button(label="Change status message")
        alert.connect(
            "clicked",
            lambda _button: self.set_status(
                "Updated: punctuation ! @ # $ %, repeated words words, and number 1,234.56"
            ),
        )
        page.pack_start(alert, False, False, 0)

        long_button = Gtk.Button()
        long_label = Gtk.Label(
            label=(
                "Extremely long button label used to verify that speech remains responsive "
                "when an accessible name contains far more words than a normal control"
            )
        )
        long_label.set_line_wrap(True)
        long_button.add(long_label)
        page.pack_start(long_button, False, False, 0)

        unnamed = Gtk.Button()
        unnamed.get_accessible().set_description(
            "Intentionally unnamed button with only an accessible description"
        )
        page.pack_start(unnamed, False, False, 0)

        return page

    def _show_dialog(self, _widget: Gtk.Widget) -> None:
        dialog = Gtk.Dialog(
            title="Edge-case confirmation",
            transient_for=self,
            modal=True,
        )
        dialog.add_button("Cancel", Gtk.ResponseType.CANCEL)
        dialog.add_button("Confirm", Gtk.ResponseType.OK)
        area = dialog.get_content_area()
        label = Gtk.Label(
            label="Confirm the action? Focus should remain trapped in this modal dialog."
        )
        label.set_line_wrap(True)
        area.pack_start(label, False, False, 10)
        reason = Gtk.Entry()
        reason.set_placeholder_text("Optional reason")
        reason.get_accessible().set_name("Confirmation reason")
        area.pack_start(reason, False, False, 10)
        dialog.show_all()
        response = dialog.run()
        self.set_status(f"Dialog response {response}")
        dialog.destroy()

    def _advance_progress(self, _button: Gtk.Button) -> None:
        self.progress_value = min(self.progress_value + 0.1, 1.0)
        self.progress.set_fraction(self.progress_value)
        self.progress.set_text(f"{round(self.progress_value * 100)} percent")
        self.set_status(f"Progress changed to {round(self.progress_value * 100)} percent")
        if self.progress_value >= 1.0:
            GLib.timeout_add(800, self._reset_progress)

    def _reset_progress(self) -> bool:
        self.progress_value = 0.0
        self.progress.set_fraction(0.0)
        self.progress.set_text("Complete, then reset")
        return False

    def _toggle_advanced(self, button: Gtk.ToggleButton) -> None:
        state = "pressed" if button.get_active() else "not pressed"
        self.set_status(f"Advanced mode {state}")

    def set_status(self, text: str) -> None:
        self.status.pop(self.status_context)
        self.status.push(self.status_context, text)

    @staticmethod
    def _scroll(child: Gtk.Widget) -> Gtk.ScrolledWindow:
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.add(child)
        return scroll


window = TestWindow()
window.show_all()
Gtk.main()
