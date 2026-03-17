# -*- coding: utf-8 -*-

import os

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QComboBox,
    QDoubleSpinBox,
    QSpinBox,
    QLineEdit,
    QPushButton,
    QFileDialog,
    QCheckBox,
    QProgressBar,
    QMessageBox,
)
from qgis.gui import QgsMapLayerComboBox
from qgis.core import QgsMapLayerProxyModel


class PointScreenShoterDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("PointScreenShoter")
        self.setMinimumWidth(520)
        self.resize(560, 420)
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        intro = QLabel(
            "Creates one georeferenced screenshot for each point. "
            "All currently visible layers from the main QGIS map canvas will be used."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignLeft)
        form.setFormAlignment(Qt.AlignTop)

        self.layer_combo = QgsMapLayerComboBox()
        self.layer_combo.setFilters(QgsMapLayerProxyModel.PointLayer)
        form.addRow("Point layer:", self.layer_combo)

        self.field_combo = QComboBox()
        form.addRow("Filename field:", self.field_combo)

        self.scale_spin = QDoubleSpinBox()
        self.scale_spin.setDecimals(2)
        self.scale_spin.setRange(1.0, 1000000000.0)
        self.scale_spin.setValue(200.0)
        self.scale_spin.setSuffix("   (1:x)")
        form.addRow("Scale:", self.scale_spin)

        self.width_spin = QSpinBox()
        self.width_spin.setRange(64, 20000)
        self.width_spin.setValue(1200)
        form.addRow("Image width (px):", self.width_spin)

        self.height_spin = QSpinBox()
        self.height_spin.setRange(64, 20000)
        self.height_spin.setValue(1200)
        form.addRow("Image height (px):", self.height_spin)

        self.format_combo = QComboBox()
        self.format_combo.addItems(["JPG", "PNG"])
        form.addRow("Format:", self.format_combo)

        out_row = QHBoxLayout()
        self.out_edit = QLineEdit()
        self.browse_btn = QPushButton("Browse…")
        out_row.addWidget(self.out_edit, 1)
        out_row.addWidget(self.browse_btn)
        form.addRow("Output folder:", out_row)

        self.keep_rotation = QCheckBox("Use rotation from main map canvas")
        self.keep_rotation.setChecked(True)
        form.addRow("", self.keep_rotation)

        self.only_selected = QCheckBox("Export selected points only")
        self.only_selected.setChecked(False)
        form.addRow("", self.only_selected)

        self.add_info_panel = QCheckBox("Add info panel (north arrow, scale bar, coordinates)")
        self.add_info_panel.setChecked(False)
        form.addRow("", self.add_info_panel)

        self.x_field_combo = QComboBox()
        self.y_field_combo = QComboBox()
        self.z_field_combo = QComboBox()
        form.addRow("X field (optional):", self.x_field_combo)
        form.addRow("Y field (optional):", self.y_field_combo)
        form.addRow("Z field (optional):", self.z_field_combo)

        layout.addLayout(form)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        layout.addWidget(self.progress)

        btn_row = QHBoxLayout()
        self.export_btn = QPushButton("Export")
        self.close_btn = QPushButton("Close")
        btn_row.addStretch(1)
        btn_row.addWidget(self.export_btn)
        btn_row.addWidget(self.close_btn)
        layout.addLayout(btn_row)

        self.browse_btn.clicked.connect(self._choose_folder)
        self.close_btn.clicked.connect(self.reject)

    def _choose_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select output folder", self.out_edit.text() or "")
        if folder:
            self.out_edit.setText(folder)

    def output_dir(self):
        return self.out_edit.text().strip()

    def selected_field(self):
        data = self.field_combo.currentData()
        if isinstance(data, str):
            return data
        txt = self.field_combo.currentText().strip()
        return txt or None

    def set_fields(self, fields):
        current = self.selected_field()
        self.field_combo.blockSignals(True)
        self.field_combo.clear()
        self.field_combo.addItem("<FID>", None)
        for f in fields:
            self.field_combo.addItem(f.name(), f.name())
        idx = self.field_combo.findData(current)
        if idx >= 0:
            self.field_combo.setCurrentIndex(idx)
        self.field_combo.blockSignals(False)


    def _combo_selected_field(self, combo):
        data = combo.currentData()
        if isinstance(data, str):
            return data
        return None

    def coord_fields(self):
        # Returns tuple (x_field, y_field, z_field) where each can be None -> use geometry
        x = self._combo_selected_field(self.x_field_combo)
        y = self._combo_selected_field(self.y_field_combo)
        z = self._combo_selected_field(self.z_field_combo)
        return (x, y, z)

    def set_coord_fields(self, fields):
        # "<Geometry>" means None -> take from point geometry
        combos = [self.x_field_combo, self.y_field_combo, self.z_field_combo]
        prev = [cb.currentData() for cb in combos]

        for cb in combos:
            cb.blockSignals(True)
            cb.clear()
            cb.addItem("<Geometry>", None)
            for f in fields:
                cb.addItem(f.name(), f.name())
            cb.blockSignals(False)

        # Restore previous selections if possible
        for cb, p in zip(combos, prev):
            idx = cb.findData(p)
            if idx >= 0:
                cb.setCurrentIndex(idx)


    def validate_inputs(self):
        if not self.layer_combo.currentLayer():
            QMessageBox.warning(self, "PointScreenShoter", "Select a point layer.")
            return False
        out_dir = self.output_dir()
        if not out_dir:
            QMessageBox.warning(self, "PointScreenShoter", "Select an output folder.")
            return False
        if not os.path.isdir(out_dir):
            QMessageBox.warning(self, "PointScreenShoter", "The output folder does not exist.")
            return False
        return True
