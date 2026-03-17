# -*- coding: utf-8 -*-

import os
import re
import traceback
import math

from qgis.PyQt.QtCore import QCoreApplication, QSize, Qt, QPointF
from qgis.PyQt.QtGui import QIcon, QImage, QPainter, QColor, QFont, QPen, QPolygonF
from qgis.PyQt.QtWidgets import QAction, QMessageBox
from qgis.core import (
    Qgis,
    QgsMapLayerType,
    QgsMapRendererCustomPainterJob,
    QgsPointXY,
    QgsRectangle,
    QgsUnitTypes,
    QgsWkbTypes,
)

from .pointscreenshoter_dialog import PointScreenShoterDialog


class PointScreenShoterPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.canvas = iface.mapCanvas()
        self.action = None
        self.dialog = None

    def initGui(self):
        # Icon-only toolbar button + normal menu entry
        icon_path = os.path.join(os.path.dirname(__file__), "icon.png")
        icon = QIcon(icon_path)

        # Toolbar action: icon only (no text)
        self.action_toolbar = QAction(icon, "", self.iface.mainWindow())
        self.action_toolbar.setToolTip("PointScreenShoter")
        self.action_toolbar.triggered.connect(self.run)
        self.iface.addToolBarIcon(self.action_toolbar)

        # Menu action: keep text in menu
        self.action_menu = QAction(icon, "PointScreenShoter", self.iface.mainWindow())
        self.action_menu.triggered.connect(self.run)
        self.iface.addPluginToMenu("&PointScreenShoter", self.action_menu)

    def unload(self):
        if getattr(self, "action_toolbar", None):
            self.iface.removeToolBarIcon(self.action_toolbar)
            self.action_toolbar = None
        if getattr(self, "action_menu", None):
            self.iface.removePluginMenu("&PointScreenShoter", self.action_menu)
            self.action_menu = None

    def run(self):
        if self.dialog is None:
            self.dialog = PointScreenShoterDialog(self.iface.mainWindow())
            self.dialog.layer_combo.layerChanged.connect(self._on_layer_changed)
            self.dialog.export_btn.clicked.connect(self._export)

        self._on_layer_changed(self.dialog.layer_combo.currentLayer())
        self.dialog.progress.setValue(0)
        self.dialog.show()
        self.dialog.raise_()
        self.dialog.activateWindow()

    def _on_layer_changed(self, layer):
        if self.dialog is None:
            return
        if layer is None:
            self.dialog.set_fields([])
            self.dialog.set_coord_fields([])
            return
        fields = layer.fields()
        self.dialog.set_fields(fields)
        # Populate X/Y/Z field combos for the optional info panel
        self.dialog.set_coord_fields(fields)

    @staticmethod
    def _safe_name(value):
        text = str(value) if value is not None else ""
        text = text.strip()
        text = re.sub(r'[\/*?:"<>|]+', '_', text)
        text = re.sub(r'\s+', '_', text)
        return text or "feature"

    @staticmethod
    def _point_from_feature(feat):
        geom = feat.geometry()
        if geom is None or geom.isNull():
            return None
        if geom.isMultipart():
            pts = geom.asMultiPoint()
            if not pts:
                return None
            p = pts[0]
        else:
            p = geom.asPoint()
        return QgsPointXY(p.x(), p.y())

    def _validate_layer(self, layer):
        if layer is None:
            raise Exception("No point layer is selected.")
        if layer.type() != QgsMapLayerType.VectorLayer:
            raise Exception("The selected layer is not a vector layer.")
        if QgsWkbTypes.geometryType(layer.wkbType()) != QgsWkbTypes.PointGeometry:
            raise Exception("The selected layer is not a point layer.")

    def _message(self, text, level=Qgis.Info, duration=5):
        self.iface.messageBar().pushMessage("PointScreenShoter", text, level=level, duration=duration)

    @staticmethod
    def _meters_per_map_unit(map_settings):
        unit = map_settings.destinationCrs().mapUnits()
        try:
            return QgsUnitTypes.fromUnitToUnitFactor(unit, QgsUnitTypes.DistanceMeters)
        except Exception:
            return 1.0

    def _extent_for_point_scale(self, center_pt, scale_denominator, width_px, height_px, dpi, source_ms):
        meters_per_mu = self._meters_per_map_unit(source_ms)
        if meters_per_mu == 0:
            meters_per_mu = 1.0

        # Ground size of one screen pixel at the requested scale.
        # Formula: scale * physical_pixel_size_in_meters / meters_per_map_unit
        map_units_per_pixel = (float(scale_denominator) * 0.0254 / float(dpi)) / float(meters_per_mu)
        half_w = (float(width_px) * map_units_per_pixel) / 2.0
        half_h = (float(height_px) * map_units_per_pixel) / 2.0
        return QgsRectangle(center_pt.x() - half_w, center_pt.y() - half_h,
                            center_pt.x() + half_w, center_pt.y() + half_h)

    @staticmethod
    def _save_world_file(image_path, map_settings):
        base, ext = os.path.splitext(image_path)
        ext = ext.lower()
        if ext in ('.jpg', '.jpeg'):
            world_ext = '.jgw'
        elif ext == '.png':
            world_ext = '.pgw'
        else:
            world_ext = ext + 'w'
        world_path = base + world_ext

        mtp = map_settings.mapToPixel()
        p00 = mtp.toMapCoordinates(0, 0)
        p10 = mtp.toMapCoordinates(1, 0)
        p01 = mtp.toMapCoordinates(0, 1)

        a = p10.x() - p00.x()
        d = p10.y() - p00.y()
        b = p01.x() - p00.x()
        e = p01.y() - p00.y()

        c = p00.x() + 0.5 * a + 0.5 * b
        f = p00.y() + 0.5 * d + 0.5 * e

        with open(world_path, 'w', encoding='ascii') as wf:
            wf.write(f"{a:.12f}\n{d:.12f}\n{b:.12f}\n{e:.12f}\n{c:.12f}\n{f:.12f}\n")

        return world_path

    @staticmethod
    def _render_to_image(map_settings, width, height):
        image = QImage(width, height, QImage.Format_ARGB32)
        image.fill(map_settings.backgroundColor().rgba())

        painter = QPainter(image)
        try:
            job = QgsMapRendererCustomPainterJob(map_settings, painter)
            job.start()
            job.waitForFinished()
        finally:
            painter.end()

        # Return the rendered map image
        return image
    @staticmethod
    def _nice_scale_length_m(target_m):
        # Choose a "nice" number (1,2,5)*10^n close to target_m
        if target_m <= 0:
            return 1.0
        exp = math.floor(math.log10(target_m))
        base = target_m / (10 ** exp)
        if base < 1.5:
            nice = 1.0
        elif base < 3.5:
            nice = 2.0
        elif base < 7.5:
            nice = 5.0
        else:
            nice = 10.0
        return nice * (10 ** exp)

    def _decorate_image(self, image, map_settings, rotation_deg, point_label, xyz_tuple):
        # Draws an info panel overlay at the bottom of the image
        w = image.width()
        h = image.height()
        panel_h = max(170, int(h * 0.18))

        painter = QPainter(image)
        try:
            painter.setRenderHint(QPainter.Antialiasing, True)

            # Panel background (semi-transparent white)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(255, 255, 255, 200))
            painter.drawRect(0, h - panel_h, w, panel_h)

            # Text styles
            title_font = QFont()
            title_font.setPointSize(12)
            title_font.setBold(True)
            body_font = QFont()
            body_font.setPointSize(10)

            # Title
            painter.setPen(QColor(0, 0, 0))
            painter.setFont(title_font)
            painter.drawText(12, h - panel_h + 24, f"Point: {point_label}")

            # Coordinates
            painter.setFont(body_font)
            x_val, y_val, z_val = xyz_tuple
            y0 = h - panel_h + 50
            painter.drawText(12, y0, f"X: {x_val}")
            painter.drawText(12, y0 + 20, f"Y: {y_val}")
            painter.drawText(12, y0 + 40, f"Z: {z_val}")

            # North arrow (shows where North is on the image; rotate by -map rotation)
            arrow_cx = w - 70
            arrow_cy = h - panel_h + 55
            painter.save()
            painter.translate(arrow_cx, arrow_cy)
            painter.rotate(-float(rotation_deg))
            painter.setPen(QPen(QColor(0, 0, 0), 2))
            painter.setBrush(QColor(0, 0, 0))
            poly = QPolygonF()
            poly.append(QPointF(0, -30))
            poly.append(QPointF(10, 10))
            poly.append(QPointF(0, 0))
            poly.append(QPointF(-10, 10))
            painter.drawPolygon(poly)
            painter.setBrush(Qt.NoBrush)
            painter.drawLine(0, 10, 0, 32)
            painter.restore()

            painter.setFont(body_font)
            painter.drawText(w - 85, h - panel_h + 105, "N")

            # Scale bar
            # Use map units per pixel -> meters per pixel
            mup = float(map_settings.mapUnitsPerPixel())
            meters_per_mu = self._meters_per_map_unit(map_settings)
            m_per_px = mup * meters_per_mu if meters_per_mu else mup

            # desired scale bar pixel length
            target_px = w * 0.25
            target_m = target_px * m_per_px
            nice_m = self._nice_scale_length_m(target_m)

            # convert nice length back to pixels
            nice_px = nice_m / m_per_px if m_per_px > 0 else target_px
            nice_px = max(40.0, min(nice_px, w * 0.5))

            bar_x0 = w - 30 - nice_px
            bar_y0 = h - 35
            painter.setPen(QPen(QColor(0, 0, 0), 3))
            painter.drawLine(int(bar_x0), int(bar_y0), int(bar_x0 + nice_px), int(bar_y0))
            painter.setPen(QPen(QColor(0, 0, 0), 2))
            painter.drawLine(int(bar_x0), int(bar_y0 - 8), int(bar_x0), int(bar_y0 + 8))
            painter.drawLine(int(bar_x0 + nice_px), int(bar_y0 - 8), int(bar_x0 + nice_px), int(bar_y0 + 8))

            # label
            if nice_m >= 1000:
                label = f"{nice_m/1000:.3g} km"
            else:
                label = f"{nice_m:.3g} m"
            painter.setFont(body_font)
            painter.drawText(int(bar_x0), int(bar_y0 - 12), label)

        finally:
            painter.end()

        return image


    def _export(self):
        try:
            if self.dialog is None or not self.dialog.validate_inputs():
                return

            point_layer = self.dialog.layer_combo.currentLayer()
            self._validate_layer(point_layer)

            visible_layers = [lyr for lyr in self.canvas.layers() if lyr is not None]
            if not visible_layers:
                raise Exception("There are no visible layers in the main map canvas.")

            if self.dialog.only_selected.isChecked():
                features = list(point_layer.getSelectedFeatures())
                if not features:
                    raise Exception("No points are selected.")
            else:
                features = list(point_layer.getFeatures())
                if not features:
                    raise Exception("The point layer contains no features.")

            out_dir = self.dialog.output_dir()
            scale = float(self.dialog.scale_spin.value())
            width = int(self.dialog.width_spin.value())
            height = int(self.dialog.height_spin.value())
            image_format = self.dialog.format_combo.currentText().upper()
            save_format = 'JPEG' if image_format == 'JPG' else 'PNG'
            ext = 'jpg' if image_format == 'JPG' else 'png'
            field_name = self.dialog.selected_field()
            rotation = self.canvas.rotation() if self.dialog.keep_rotation.isChecked() else 0.0
            dpi = 96

            total = len(features)
            self.dialog.progress.setRange(0, total)
            self.dialog.progress.setValue(0)
            self.dialog.export_btn.setEnabled(False)
            self.dialog.repaint()
            QCoreApplication.processEvents()

            used_names = {}
            exported = 0
            skipped = 0

            base_ms = self.canvas.mapSettings()

            for idx, feat in enumerate(features, start=1):
                pt = self._point_from_feature(feat)
                if pt is None:
                    skipped += 1
                    self.dialog.progress.setValue(idx)
                    QCoreApplication.processEvents()
                    continue

                if field_name and field_name in point_layer.fields().names():
                    raw_name = feat[field_name]
                else:
                    raw_name = f"fid_{feat.id()}"

                base_name = self._safe_name(raw_name)
                serial = used_names.get(base_name, 0)
                used_names[base_name] = serial + 1
                final_name = base_name if serial == 0 else f"{base_name}_{serial + 1}"
                out_path = os.path.join(out_dir, f"{final_name}.{ext}")

                ms = self.canvas.mapSettings()
                ms.setLayers(visible_layers)
                ms.setOutputSize(QSize(width, height))
                ms.setOutputDpi(dpi)
                try:
                    ms.setRotation(rotation)
                except Exception:
                    pass
                try:
                    ms.setEllipsoid(base_ms.ellipsoid())
                except Exception:
                    pass
                try:
                    ms.setBackgroundColor(self.canvas.canvasColor())
                except Exception:
                    pass

                extent = self._extent_for_point_scale(pt, scale, width, height, dpi, ms)
                ms.setExtent(extent)

                image = self._render_to_image(ms, width, height)
                if self.dialog.add_info_panel.isChecked():
                    # Determine XYZ values (prefer attribute fields if selected)
                    x_field, y_field, z_field = self.dialog.coord_fields()
                    def _val(field, default):
                        try:
                            if field and field in point_layer.fields().names():
                                v = feat[field]
                                return v
                        except Exception:
                            pass
                        return default

                    gx = pt.x()
                    gy = pt.y()
                    # geometry Z if present
                    gz = None
                    try:
                        g = feat.geometry()
                        if g and not g.isNull() and g.constGet() is not None:
                            # asPoint may carry z
                            p = g.asPoint()
                            if hasattr(p, "z"):
                                ztmp = p.z()
                                if ztmp is not None:
                                    gz = ztmp
                    except Exception:
                        pass

                    x_val = _val(x_field, gx)
                    y_val = _val(y_field, gy)
                    z_val = _val(z_field, gz if gz is not None else "")

                    def _fmt(v):
                        if v is None:
                            return ""
                        try:
                            return f"{float(v):.3f}"
                        except Exception:
                            return str(v)

                    image = self._decorate_image(image, ms, rotation, final_name, (_fmt(x_val), _fmt(y_val), _fmt(z_val)))
                saved = image.save(out_path, save_format, 95)
                if not saved:
                    raise Exception(f"Failed to save image: {out_path}")

                self._save_world_file(out_path, ms)

                exported += 1
                self.dialog.progress.setValue(idx)
                QCoreApplication.processEvents()

            self.dialog.export_btn.setEnabled(True)
            self._message(
                f"Done. Exported: {exported}, skipped: {skipped}. Images and world files were saved side by side.",
                level=Qgis.Success,
                duration=8,
            )
            QMessageBox.information(
                self.dialog,
                "PointScreenShoter",
                f"Export finished.\n\nExported: {exported}\nSkipped: {skipped}\n\nFolder:\n{out_dir}",
            )
        except Exception as e:
            if self.dialog is not None:
                self.dialog.export_btn.setEnabled(True)
            self._message(str(e), level=Qgis.Critical, duration=8)
            QMessageBox.critical(
                self.iface.mainWindow(),
                "PointScreenShoter - error",
                f"{e}\n\n{traceback.format_exc()}",
            )
