"""Cyber-themed reactive slash command auto-completion popup widget with multi-selection support."""

from typing import Dict, List, Optional
from PySide6.QtCore import QPoint, QSize, Qt, Signal
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QPushButton, QVBoxLayout, QWidget
)

from entropy.core.slash_commands import SlashCommand

class SlashCommandItemWidget(QWidget):
    """Custom row widget rendering multi-select check indicator, badge, command name, description, and usage."""

    def __init__(self, command: SlashCommand, is_selected: bool = False, parent=None):
        super().__init__(parent)
        self.command = command
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(8)

        # Check Indicator for Multi-Select
        self.check_lbl = QLabel("[✓]" if is_selected else "[ ]")
        self._update_check_style(is_selected)
        layout.addWidget(self.check_lbl)

        # Badge Pill
        badge_lbl = QLabel(command.badge)
        badge_color = command.color or "#00F0FF"
        badge_lbl.setStyleSheet(f"""
            background-color: {badge_color}18;
            color: {badge_color};
            border: 1px solid {badge_color}55;
            border-radius: 3px;
            padding: 2px 6px;
            font-size: 9px;
            font-weight: bold;
        """)
        layout.addWidget(badge_lbl)

        # Command Name (bold neon monospace)
        name_lbl = QLabel(command.name)
        name_lbl.setStyleSheet("color: #F0F6FC; font-family: 'Consolas', 'Courier New', monospace; font-size: 12px; font-weight: bold;")
        layout.addWidget(name_lbl)

        # Description (muted)
        desc_lbl = QLabel(command.description)
        desc_lbl.setStyleSheet("color: #8B949E; font-size: 11px;")
        desc_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        layout.addWidget(desc_lbl)

        layout.addStretch()

        # Usage hint (subtle)
        if command.usage:
            usage_lbl = QLabel(command.usage)
            usage_lbl.setStyleSheet("color: #484F58; font-family: 'Consolas', monospace; font-size: 10px;")
            layout.addWidget(usage_lbl)

    def set_checked(self, checked: bool):
        self.check_lbl.setText("[✓]" if checked else "[ ]")
        self._update_check_style(checked)

    def _update_check_style(self, checked: bool):
        if checked:
            self.check_lbl.setStyleSheet("color: #00FF9D; font-family: 'Consolas', monospace; font-size: 11px; font-weight: bold;")
        else:
            self.check_lbl.setStyleSheet("color: #30363D; font-family: 'Consolas', monospace; font-size: 11px;")


class SlashCommandPopupWidget(QFrame):
    """Floating autocomplete popup supporting single and multi-selection of slash commands."""

    command_selected = Signal(str)
    commands_updated = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setObjectName("slashPopupFrame")

        self.setStyleSheet("""
            QFrame#slashPopupFrame {
                background-color: #0A0E17;
                border: 1px solid #00F0FF;
                border-radius: 6px;
            }
            QListWidget {
                background-color: #080B10;
                border: none;
                border-radius: 4px;
                outline: none;
            }
            QListWidget::item {
                border-radius: 4px;
                padding: 1px;
                margin: 1px 2px;
                border: 1px solid transparent;
            }
            QListWidget::item:selected {
                background-color: #162238;
                border: 1px solid #00F0FF;
            }
            QListWidget::item:hover:!selected {
                background-color: #101826;
            }
            QScrollBar:vertical {
                background: #080B10;
                width: 6px;
                margin: 0px;
                border-radius: 3px;
            }
            QScrollBar::handle:vertical {
                background: #1F2B42;
                border-radius: 3px;
            }
            QScrollBar::handle:vertical:hover {
                background: #00F0FF;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        # Header Bar
        header = QHBoxLayout()
        header.setContentsMargins(4, 2, 4, 2)
        title_lbl = QLabel("<b style='color:#00F0FF; font-size:10px;'>⚡ KOMUT & YETENEK TAMAMLAYICI</b>")
        header.addWidget(title_lbl)
        header.addStretch()
        hints_lbl = QLabel("<span style='color:#8B949E; font-size:9px;'>[Tıkla]: Ekle/Kaldır &nbsp; [Tab/Enter]: Tamamla &nbsp; [Esc]: Kapat</span>")
        header.addWidget(hints_lbl)
        layout.addLayout(header)

        # Divider
        divider = QFrame()
        divider.setFixedHeight(1)
        divider.setStyleSheet("background-color: #1F2B42;")
        layout.addWidget(divider)

        # List Widget
        self.list_widget = QListWidget()
        self.list_widget.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.list_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list_widget.itemClicked.connect(self._on_item_clicked)
        self.list_widget.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self.list_widget)

        # Bottom Multi-Select Actions Bar
        bottom_bar = QHBoxLayout()
        bottom_bar.setContentsMargins(4, 3, 4, 2)
        self.chips_lbl = QLabel("<span style='color:#8B949E; font-size:10px;'>Çoklu seçim: Komutlara tıklayarak birden fazlasını ekleyin</span>")
        bottom_bar.addWidget(self.chips_lbl)
        bottom_bar.addStretch()

        self.clear_btn = QPushButton("Temizle")
        self.clear_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #8B949E;
                border: 1px solid #1F2B42;
                border-radius: 3px;
                padding: 2px 8px;
                font-size: 10px;
            }
            QPushButton:hover {
                color: #FF0055;
                border-color: #FF0055;
            }
        """)
        self.clear_btn.clicked.connect(self.clear_selection)
        bottom_bar.addWidget(self.clear_btn)

        self.apply_btn = QPushButton("✔ Tamamla")
        self.apply_btn.setStyleSheet("""
            QPushButton {
                background: #00F0FF;
                color: #080B10;
                font-weight: bold;
                border-radius: 3px;
                padding: 3px 12px;
                font-size: 11px;
            }
            QPushButton:hover {
                background: #00FF9D;
            }
        """)
        self.apply_btn.clicked.connect(self.confirm_selection)
        bottom_bar.addWidget(self.apply_btn)

        layout.addLayout(bottom_bar)

        self._commands: List[SlashCommand] = []
        self._item_widgets: Dict[str, SlashCommandItemWidget] = {}
        self.selected_commands: List[str] = []
        self._explicitly_cleared: bool = False

    def set_commands(self, commands: List[SlashCommand], preselected: Optional[List[str]] = None):
        """Populate list with commands, restore preselected status, and resize dynamically."""
        self._commands = commands
        self._item_widgets.clear()
        self.list_widget.clear()
        self._explicitly_cleared = False

        if preselected is not None:
            self.selected_commands = list(preselected)

        for cmd in commands:
            item = QListWidgetItem()
            item.setData(Qt.ItemDataRole.UserRole, cmd.name)
            item.setSizeHint(QSize(100, 32))
            is_sel = cmd.name in self.selected_commands
            widget = SlashCommandItemWidget(cmd, is_selected=is_sel)
            self._item_widgets[cmd.name] = widget
            self.list_widget.addItem(item)
            self.list_widget.setItemWidget(item, widget)

        if commands:
            self.list_widget.setCurrentRow(0)

        self._update_footer()

        # Adjust height dynamically based on count (min 120, max 320)
        row_height = 34
        computed_height = min(320, max(120, 72 + len(commands) * row_height))
        self.setFixedHeight(computed_height)

    def _update_footer(self):
        if self.selected_commands:
            chips = " ".join(self.selected_commands)
            self.chips_lbl.setText(f"<b style='color:#00FF9D; font-size:10px;'>Seçilenler:</b> <span style='color:#F0F6FC; font-family:Consolas; font-size:10px;'>{chips}</span>")
        else:
            self.chips_lbl.setText("<span style='color:#8B949E; font-size:10px;'>Çoklu seçim: Komutlara tıklayarak birden fazlasını ekleyin</span>")

    def select_next(self):
        """Move selection to next item."""
        count = self.list_widget.count()
        if count == 0:
            return
        curr = self.list_widget.currentRow()
        next_row = (curr + 1) % count
        self.list_widget.setCurrentRow(next_row)

    def select_previous(self):
        """Move selection to previous item."""
        count = self.list_widget.count()
        if count == 0:
            return
        curr = self.list_widget.currentRow()
        prev_row = (curr - 1 + count) % count
        self.list_widget.setCurrentRow(prev_row)

    def has_selection(self) -> bool:
        """Return True if an item is currently selected."""
        return (self.list_widget.currentRow() >= 0 and self.list_widget.count() > 0) or len(self.selected_commands) > 0

    def clear_selection(self):
        """Clear all selected commands."""
        self.selected_commands.clear()
        self._explicitly_cleared = True
        for w in self._item_widgets.values():
            w.set_checked(False)
        self._update_footer()
        self.commands_updated.emit([])

    def confirm_selection(self):
        """Confirm selected items, emit signals, and hide."""
        if not self.selected_commands and not self._explicitly_cleared:
            item = self.list_widget.currentItem()
            if item:
                cmd_name = item.data(Qt.ItemDataRole.UserRole)
                if cmd_name:
                    self.selected_commands.append(cmd_name)
                    if cmd_name in self._item_widgets:
                        self._item_widgets[cmd_name].set_checked(True)

        if self.selected_commands:
            self.command_selected.emit(self.selected_commands[-1])
        self.commands_updated.emit(list(self.selected_commands))

        self.hide()

    def _on_item_clicked(self, item: QListWidgetItem):
        """Toggle command selection on click and keep popup open for sequential multi-selection."""
        if not item:
            return
        cmd_name = item.data(Qt.ItemDataRole.UserRole)
        if not cmd_name:
            return

        was_selected = cmd_name in self.selected_commands
        if was_selected:
            self.selected_commands.remove(cmd_name)
            if cmd_name in self._item_widgets:
                self._item_widgets[cmd_name].set_checked(False)
        else:
            self.selected_commands.append(cmd_name)
            if cmd_name in self._item_widgets:
                self._item_widgets[cmd_name].set_checked(True)

        self._explicitly_cleared = False
        self._update_footer()
        if not was_selected:
            self.command_selected.emit(cmd_name)
        self.commands_updated.emit(list(self.selected_commands))

    def _on_item_double_clicked(self, item: QListWidgetItem):
        """Double click selects and immediately confirms/closes."""
        if not item:
            return
        cmd_name = item.data(Qt.ItemDataRole.UserRole)
        if cmd_name and cmd_name not in self.selected_commands:
            self.selected_commands.append(cmd_name)
        self.confirm_selection()

    def show_at_input(self, input_widget: QWidget):
        """Position popup directly above (or below if needed) the input widget with multi-monitor awareness."""
        if not input_widget:
            return

        global_pt = input_widget.mapToGlobal(QPoint(0, 0))
        target_width = max(540, min(800, input_widget.width()))
        target_height = self.height()

        screen = input_widget.screen()
        if screen:
            geo = screen.availableGeometry()
            top_bound = geo.top()
            bottom_bound = geo.bottom()
            left_bound = geo.left()
            right_bound = geo.right()
        else:
            top_bound = 0
            bottom_bound = 1080
            left_bound = 0
            right_bound = 1920

        # Default position: above the input widget
        x = global_pt.x()
        y = global_pt.y() - target_height - 6

        # If too close to the top of available screen area, flip below
        if y < top_bound + 10:
            y = global_pt.y() + input_widget.height() + 6

        # Ensure it does not extend beyond horizontal edges
        if x + target_width > right_bound:
            x = max(left_bound + 8, right_bound - target_width - 8)
        if x < left_bound:
            x = left_bound + 8

        # Ensure it does not extend beyond vertical bottom
        if y + target_height > bottom_bound:
            y = max(top_bound + 8, bottom_bound - target_height - 8)

        self.setGeometry(x, y, target_width, target_height)
        self.show()
        self.raise_()

