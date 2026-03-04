#!/usr/bin/env python3
"""
STL Viewer - 3D STL 파일 뷰어
실행 디렉토리의 STL 파일을 좌측 패널에서 선택하고 우측에서 3D 미리보기
"""

import sys
import os
import math
from pathlib import Path

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QListWidget, QListWidgetItem, QLabel, QFrame, QSplitter,
    QStatusBar, QToolBar, QAction, QSizePolicy, QPushButton,
    QSlider, QGroupBox, QScrollArea
)
from PyQt5.QtCore import Qt, QSize, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import (
    QIcon, QPixmap, QPainter, QColor, QFont, QLinearGradient,
    QPen, QBrush, QRadialGradient, QPalette
)

import vtk
from vtk.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor


# ─────────────────────────────────────────────
#  STL 썸네일 생성 (오프스크린 렌더링)
# ─────────────────────────────────────────────
def render_stl_thumbnail(stl_path: str, size: int = 120, color=(0.3, 0.6, 1.0)) -> QPixmap:
    """VTK 오프스크린 렌더링으로 STL 썸네일 생성"""
    try:
        reader = vtk.vtkSTLReader()
        reader.SetFileName(stl_path)
        reader.Update()

        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputConnection(reader.GetOutputPort())

        actor = vtk.vtkActor()
        actor.SetMapper(mapper)
        actor.GetProperty().SetColor(*color)
        actor.GetProperty().SetAmbient(0.3)
        actor.GetProperty().SetDiffuse(0.7)
        actor.GetProperty().SetSpecular(0.4)
        actor.GetProperty().SetSpecularPower(30)

        renderer = vtk.vtkRenderer()
        renderer.AddActor(actor)
        renderer.SetBackground(0.12, 0.14, 0.18)
        renderer.ResetCamera()
        renderer.GetActiveCamera().Azimuth(30)
        renderer.GetActiveCamera().Elevation(20)
        renderer.ResetCameraClippingRange()

        light = vtk.vtkLight()
        light.SetLightTypeToSceneLight()
        light.SetPosition(1, 1, 1)
        light.SetIntensity(1.0)
        renderer.AddLight(light)

        render_window = vtk.vtkRenderWindow()
        render_window.SetOffScreenRendering(1)
        render_window.AddRenderer(renderer)
        render_window.SetSize(size, size)
        render_window.Render()

        window_to_image = vtk.vtkWindowToImageFilter()
        window_to_image.SetInput(render_window)
        window_to_image.Update()

        writer = vtk.vtkPNGWriter()
        writer.SetWriteToMemory(1)
        writer.SetInputConnection(window_to_image.GetOutputPort())
        writer.Write()

        data = writer.GetResult()
        raw = bytes(data)

        pixmap = QPixmap()
        pixmap.loadFromData(raw, "PNG")
        return pixmap

    except Exception as e:
        # 실패시 기본 아이콘 생성
        return _make_fallback_icon(size)


def _make_fallback_icon(size: int) -> QPixmap:
    pixmap = QPixmap(size, size)
    pixmap.fill(QColor(30, 35, 45))
    painter = QPainter(pixmap)
    painter.setPen(QPen(QColor(80, 130, 220), 2))
    painter.setFont(QFont("monospace", 10, QFont.Bold))
    painter.drawText(pixmap.rect(), Qt.AlignCenter, "STL")
    painter.end()
    return pixmap


# ─────────────────────────────────────────────
#  파일 아이콘 위젯 (좌측 패널 아이템)
# ─────────────────────────────────────────────
class STLFileItem(QListWidgetItem):
    def __init__(self, filepath: str):
        super().__init__()
        self.filepath = filepath
        self.filename = os.path.basename(filepath)
        size = os.path.getsize(filepath)
        self.filesize = f"{size/1024:.1f} KB" if size < 1024*1024 else f"{size/1024/1024:.1f} MB"

        self.setText(self.filename)
        self.setToolTip(f"{filepath}\n크기: {self.filesize}")
        self.setSizeHint(QSize(140, 155))

        # 썸네일 로딩은 나중에
        icon_pm = _make_fallback_icon(100)
        self.setIcon(QIcon(icon_pm))


# ─────────────────────────────────────────────
#  썸네일 로더 스레드
# ─────────────────────────────────────────────
class ThumbnailLoader(QThread):
    loaded = pyqtSignal(str, QPixmap)  # (filepath, pixmap)

    def __init__(self, filepaths, color_map=None):
        super().__init__()
        self.filepaths = filepaths
        self.color_map = color_map or {}

    def run(self):
        for fp in self.filepaths:
            color = self.color_map.get(fp, (0.3, 0.6, 1.0))
            pm = render_stl_thumbnail(fp, size=100, color=color)
            self.loaded.emit(fp, pm)


# ─────────────────────────────────────────────
#  메인 윈도우
# ─────────────────────────────────────────────
class STLViewer(QMainWindow):
    def __init__(self, directory: str = "."):
        super().__init__()
        self.directory = os.path.abspath(directory)
        self.current_file = None
        self.vtk_actor = None
        self._item_map: dict[str, STLFileItem] = {}
        self._color_map: dict[str, tuple] = {}  # filepath -> (r,g,b)

        self._setup_ui()
        self._apply_theme()
        self._load_file_list()

        self.setWindowTitle("STL Viewer")
        self.resize(1280, 800)

    # ── UI 구성 ──────────────────────────────
    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # ── 툴바 ──
        self._build_toolbar()

        # ── 메인 스플리터 ──
        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(3)
        root_layout.addWidget(splitter)

        # 좌측: 파일 목록
        left_panel = self._build_left_panel()
        splitter.addWidget(left_panel)

        # 우측: 3D 뷰
        right_panel = self._build_right_panel()
        splitter.addWidget(right_panel)

        splitter.setSizes([240, 1040])
        splitter.setStretchFactor(0, 0)
        splitter.setChildrenCollapsible(False)
        splitter.setStretchFactor(1, 1)

        # 상태바
        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status.showMessage(f"디렉토리: {self.directory}")

    def _build_toolbar(self):
        tb = QToolBar("메인 툴바")
        tb.setMovable(False)
        tb.setIconSize(QSize(18, 18))
        tb.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.addToolBar(tb)

        # 디렉토리 레이블
        self.dir_label = QLabel(f"  📁 {self.directory}")
        self.dir_label.setObjectName("dirLabel")
        tb.addWidget(self.dir_label)

        tb.addSeparator()

        # 새로고침
        act_refresh = QAction("🔄  새로고침", self)
        act_refresh.triggered.connect(self._load_file_list)
        tb.addAction(act_refresh)

        tb.addSeparator()

        # 뷰 조작 버튼
        for label, cb in [
            ("⬜ 앞면", lambda: self._set_view("front")),
            ("◻ 윗면", lambda: self._set_view("top")),
            ("◈ 등각", lambda: self._set_view("iso")),
        ]:
            btn = QPushButton(label)
            btn.setObjectName("toolBtn")
            btn.clicked.connect(cb)
            tb.addWidget(btn)

        tb.addSeparator()

        # 와이어프레임 토글
        self.wire_btn = QPushButton("▦ 와이어프레임")
        self.wire_btn.setObjectName("toolBtn")
        self.wire_btn.setCheckable(True)
        self.wire_btn.clicked.connect(self._toggle_wireframe)
        tb.addWidget(self.wire_btn)

        # 색상 버튼들
        for label, color in [
            ("🔵", (0.3, 0.6, 1.0)),
            ("🟢", (0.3, 0.9, 0.5)),
            ("🟠", (1.0, 0.6, 0.2)),
            ("🟡", (1.0, 0.9, 0.1)),
            ("⬛", (0.08, 0.08, 0.08)),
            ("⬜", (0.85, 0.85, 0.85)),
        ]:
            btn = QPushButton(label)
            btn.setObjectName("colorBtn")
            btn.setFixedSize(32, 32)
            c = color
            btn.clicked.connect(lambda _, col=c: self._set_model_color(*col))
            tb.addWidget(btn)

    def _build_left_panel(self):
        frame = QFrame()
        frame.setObjectName("leftPanel")
        frame.setMinimumWidth(160)
        frame.setMaximumWidth(1200)
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        title_row = QHBoxLayout()
        title = QLabel("STL 파일 목록")
        title.setObjectName("panelTitle")
        title_row.addWidget(title)
        title_row.addStretch()
        layout.addLayout(title_row)

        self.file_list = QListWidget()
        self.file_list.setObjectName("fileList")
        self.file_list.setViewMode(QListWidget.IconMode)
        self.file_list.setIconSize(QSize(100, 100))
        self.file_list.setGridSize(QSize(120, 138))
        self.file_list.setResizeMode(QListWidget.Adjust)
        self.file_list.setMovement(QListWidget.Static)
        self.file_list.setSpacing(4)
        self.file_list.setWordWrap(True)
        self.file_list.currentItemChanged.connect(self._on_file_selected)
        layout.addWidget(self.file_list)

        # 아이콘 크기 슬라이더 행
        slider_row = QHBoxLayout()
        slider_row.setContentsMargins(0, 2, 0, 2)

        icon_lbl = QLabel("🔍")
        icon_lbl.setFixedWidth(18)
        icon_lbl.setObjectName("countLabel")
        slider_row.addWidget(icon_lbl)

        self.icon_slider = QSlider(Qt.Horizontal)
        self.icon_slider.setObjectName("iconSlider")
        self.icon_slider.setMinimum(40)
        self.icon_slider.setMaximum(180)
        self.icon_slider.setValue(100)
        self.icon_slider.setTickInterval(20)
        self.icon_slider.setFixedHeight(18)
        self.icon_slider.valueChanged.connect(self._on_icon_size_changed)
        slider_row.addWidget(self.icon_slider)

        self.size_label = QLabel("100px")
        self.size_label.setObjectName("countLabel")
        self.size_label.setFixedWidth(38)
        self.size_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        slider_row.addWidget(self.size_label)

        layout.addLayout(slider_row)

        self.file_count_label = QLabel("0개 파일")
        self.file_count_label.setObjectName("countLabel")
        layout.addWidget(self.file_count_label)

        return frame

    def _build_right_panel(self):
        frame = QFrame()
        frame.setObjectName("rightPanel")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 파일 정보 헤더
        self.info_bar = QLabel("  파일을 선택하세요")
        self.info_bar.setObjectName("infoBar")
        self.info_bar.setFixedHeight(36)
        layout.addWidget(self.info_bar)

        # VTK 렌더 위젯
        self.vtk_widget = QVTKRenderWindowInteractor(frame)
        layout.addWidget(self.vtk_widget)

        # VTK 렌더러 설정
        self.renderer = vtk.vtkRenderer()
        self.renderer.SetBackground(0.10, 0.12, 0.16)
        self.renderer.SetBackground2(0.18, 0.20, 0.28)
        self.renderer.SetGradientBackground(True)

        # 그리드 바닥
        self._add_grid()

        self.vtk_widget.GetRenderWindow().AddRenderer(self.renderer)
        self.interactor = self.vtk_widget.GetRenderWindow().GetInteractor()

        style = vtk.vtkInteractorStyleTrackballCamera()
        self.interactor.SetInteractorStyle(style)

        # 조명
        self._setup_lights()

        # 빈 화면 안내 텍스트
        self.text_actor = vtk.vtkTextActor()
        self.text_actor.SetInput("← 좌측에서 STL 파일을 선택하세요")
        self.text_actor.GetTextProperty().SetColor(0.5, 0.55, 0.65)
        self.text_actor.GetTextProperty().SetFontSize(18)
        self.text_actor.GetTextProperty().SetFontFamilyToArial()
        self.text_actor.GetPositionCoordinate().SetCoordinateSystemToNormalizedDisplay()
        self.text_actor.SetPosition(0.5, 0.5)
        self.text_actor.GetTextProperty().SetJustificationToCentered()
        self.renderer.AddActor2D(self.text_actor)

        # 하단 컨트롤 바
        ctrl_bar = self._build_control_bar()
        layout.addWidget(ctrl_bar)

        return frame

    def _build_control_bar(self):
        bar = QFrame()
        bar.setObjectName("ctrlBar")
        bar.setFixedHeight(50)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 4, 16, 4)

        # 조작법 안내
        tips = [
            ("🖱 좌클릭 드래그", "회전"),
            ("🖱 우클릭 드래그", "줌"),
            ("🖱 중간 드래그", "이동"),
            ("🔄 스크롤", "줌"),
        ]
        for key, val in tips:
            lbl = QLabel(f"<b>{key}</b> {val}")
            lbl.setObjectName("tipLabel")
            layout.addWidget(lbl)
            layout.addStretch(1)
        return bar

    # ── 조명 ─────────────────────────────────
    def _setup_lights(self):
        self.renderer.RemoveAllLights()

        light1 = vtk.vtkLight()
        light1.SetLightTypeToSceneLight()
        light1.SetPosition(5, 5, 8)
        light1.SetIntensity(0.9)
        light1.SetColor(1.0, 0.98, 0.95)

        light2 = vtk.vtkLight()
        light2.SetLightTypeToSceneLight()
        light2.SetPosition(-5, -3, 4)
        light2.SetIntensity(0.4)
        light2.SetColor(0.8, 0.88, 1.0)

        light3 = vtk.vtkLight()
        light3.SetLightTypeToSceneLight()
        light3.SetPosition(0, 0, -6)
        light3.SetIntensity(0.15)

        self.renderer.AddLight(light1)
        self.renderer.AddLight(light2)
        self.renderer.AddLight(light3)

    # ── 바닥 그리드 ───────────────────────────
    def _add_grid(self):
        extent = 50
        step = 5
        vals = list(range(-extent, extent + 1, step))

        grid_points = vtk.vtkPoints()
        grid_lines = vtk.vtkCellArray()
        for v in vals:
            # 수평선
            p1 = grid_points.InsertNextPoint(-extent, v, -0.01)
            p2 = grid_points.InsertNextPoint(extent, v, -0.01)
            line = vtk.vtkLine()
            line.GetPointIds().SetId(0, p1)
            line.GetPointIds().SetId(1, p2)
            grid_lines.InsertNextCell(line)
            # 수직선
            p3 = grid_points.InsertNextPoint(v, -extent, -0.01)
            p4 = grid_points.InsertNextPoint(v, extent, -0.01)
            line2 = vtk.vtkLine()
            line2.GetPointIds().SetId(0, p3)
            line2.GetPointIds().SetId(1, p4)
            grid_lines.InsertNextCell(line2)

        grid_pd = vtk.vtkPolyData()
        grid_pd.SetPoints(grid_points)
        grid_pd.SetLines(grid_lines)

        grid_mapper = vtk.vtkPolyDataMapper()
        grid_mapper.SetInputData(grid_pd)

        self.grid_actor = vtk.vtkActor()
        self.grid_actor.SetMapper(grid_mapper)
        self.grid_actor.GetProperty().SetColor(0.25, 0.28, 0.38)
        self.grid_actor.GetProperty().SetOpacity(0.5)
        self.renderer.AddActor(self.grid_actor)

    # ── 파일 목록 로드 ────────────────────────
    def _load_file_list(self):
        self.file_list.clear()
        self._item_map.clear()

        stl_files = sorted(
            [str(p) for p in Path(self.directory).glob("*.stl")]
            + [str(p) for p in Path(self.directory).glob("*.STL")]
        )
        stl_files = list(dict.fromkeys(stl_files))  # dedup

        for fp in stl_files:
            item = STLFileItem(fp)
            self.file_list.addItem(item)
            self._item_map[fp] = item

        count = len(stl_files)
        self.file_count_label.setText(f"{count}개 STL 파일")
        self.status.showMessage(f"디렉토리: {self.directory}  |  {count}개 파일 발견")

        if stl_files:
            # 썸네일 비동기 로드
            self.thumb_loader = ThumbnailLoader(stl_files, self._color_map)
            self.thumb_loader.loaded.connect(self._on_thumbnail_loaded)
            self.thumb_loader.start()
        else:
            self.info_bar.setText("  ⚠  현재 디렉토리에 STL 파일이 없습니다")

    def _on_thumbnail_loaded(self, filepath: str, pixmap: QPixmap):
        if filepath in self._item_map:
            self._item_map[filepath].setIcon(QIcon(pixmap))

    # ── 파일 선택 ─────────────────────────────
    def _on_file_selected(self, current, previous):
        if not current:
            return
        item: STLFileItem = current
        self._load_stl(item.filepath)

    def _load_stl(self, filepath: str):
        self.current_file = filepath
        name = os.path.basename(filepath)
        size = os.path.getsize(filepath)
        size_str = f"{size/1024:.1f} KB" if size < 1024*1024 else f"{size/1024/1024:.1f} MB"

        # 기존 모델 제거
        if self.vtk_actor:
            self.renderer.RemoveActor(self.vtk_actor)
            self.vtk_actor = None

        self.text_actor.VisibilityOff()

        # STL 로드
        reader = vtk.vtkSTLReader()
        reader.SetFileName(filepath)
        reader.Update()

        pd = reader.GetOutput()
        n_pts = pd.GetNumberOfPoints()
        n_cells = pd.GetNumberOfCells()

        # 법선 계산
        normals = vtk.vtkPolyDataNormals()
        normals.SetInputConnection(reader.GetOutputPort())
        normals.ComputePointNormalsOn()
        normals.ComputeCellNormalsOn()
        normals.SplittingOff()
        normals.Update()

        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputConnection(normals.GetOutputPort())

        self.vtk_actor = vtk.vtkActor()
        self.vtk_actor.SetMapper(mapper)
        prop = self.vtk_actor.GetProperty()
        saved_color = self._color_map.get(filepath, (0.3, 0.6, 1.0))
        prop.SetColor(*saved_color)
        prop.SetAmbient(0.2)
        prop.SetDiffuse(0.75)
        prop.SetSpecular(0.5)
        prop.SetSpecularPower(50)

        self.renderer.AddActor(self.vtk_actor)
        self.renderer.ResetCamera()

        # 카메라 등각 뷰
        cam = self.renderer.GetActiveCamera()
        cam.Azimuth(30)
        cam.Elevation(25)
        self.renderer.ResetCameraClippingRange()

        self.vtk_widget.GetRenderWindow().Render()
        self.interactor.Initialize()

        # 정보 표시
        bounds = pd.GetBounds()
        dx = bounds[1]-bounds[0]
        dy = bounds[3]-bounds[2]
        dz = bounds[5]-bounds[4]

        self.info_bar.setText(
            f"  📐 {name}   |   크기: {size_str}   |   "
            f"삼각형: {n_cells:,}개   |   "
            f"치수: {dx:.1f} × {dy:.1f} × {dz:.1f} mm"
        )
        self.status.showMessage(f"로드 완료: {filepath}")
        self.wire_btn.setChecked(False)

    # ── 아이콘 크기 변경 ──────────────────────
    def _on_icon_size_changed(self, value: int):
        self.size_label.setText(f"{value}px")
        self.file_list.setIconSize(QSize(value, value))
        self.file_list.setGridSize(QSize(value + 20, value + 38))

    # ── 뷰 제어 ───────────────────────────────
    def _set_view(self, view: str):
        if not self.vtk_actor:
            return
        cam = self.renderer.GetActiveCamera()
        cam.SetFocalPoint(0, 0, 0)
        if view == "front":
            cam.SetPosition(0, -1, 0)
            cam.SetViewUp(0, 0, 1)
        elif view == "top":
            cam.SetPosition(0, 0, 1)
            cam.SetViewUp(0, 1, 0)
        elif view == "iso":
            cam.SetPosition(1, -1, 1)
            cam.SetViewUp(0, 0, 1)
        self.renderer.ResetCamera()
        cam.Azimuth(0)
        self.renderer.ResetCameraClippingRange()
        self.vtk_widget.GetRenderWindow().Render()

    def _toggle_wireframe(self, checked: bool):
        if self.vtk_actor:
            if checked:
                self.vtk_actor.GetProperty().SetRepresentationToWireframe()
                self.vtk_actor.GetProperty().SetColor(0.4, 0.8, 1.0)
            else:
                self.vtk_actor.GetProperty().SetRepresentationToSurface()
                self.vtk_actor.GetProperty().SetColor(0.3, 0.6, 1.0)
            self.vtk_widget.GetRenderWindow().Render()

    def _set_model_color(self, r, g, b):
        if self.vtk_actor and self.current_file:
            self.vtk_actor.GetProperty().SetColor(r, g, b)
            self.vtk_widget.GetRenderWindow().Render()
            # 색상 저장
            self._color_map[self.current_file] = (r, g, b)
            # 썸네일 갱신 (백그라운드)
            fp = self.current_file
            loader = ThumbnailLoader([fp], {fp: (r, g, b)})
            loader.loaded.connect(self._on_thumbnail_loaded)
            loader.start()
            self._thumb_reloader = loader  # GC 방지

    # ── 테마 ─────────────────────────────────
    def _apply_theme(self):
        self.setStyleSheet("""
            QMainWindow {
                background: #0d0f14;
            }

            /* 툴바 */
            QToolBar {
                background: #161820;
                border-bottom: 1px solid #2a2d3e;
                padding: 4px 8px;
                spacing: 4px;
            }
            QToolBar QToolButton {
                background: transparent;
                color: #a0a8c0;
                border: none;
                padding: 4px 10px;
                border-radius: 4px;
                font-size: 13px;
            }
            QToolBar QToolButton:hover {
                background: #252840;
                color: #e0e8ff;
            }
            #toolBtn {
                background: #1e2135;
                color: #8090b8;
                border: 1px solid #2a2d3e;
                padding: 4px 12px;
                border-radius: 5px;
                font-size: 12px;
                font-weight: 600;
            }
            #toolBtn:hover {
                background: #2a3055;
                color: #c0d0ff;
                border-color: #4060a0;
            }
            #toolBtn:checked {
                background: #1a3060;
                color: #60a0ff;
                border-color: #4080e0;
            }
            #colorBtn {
                background: #1e2135;
                border: 1px solid #2a2d3e;
                border-radius: 5px;
                font-size: 16px;
            }
            #colorBtn:hover {
                background: #2a3055;
                border-color: #4060a0;
            }
            #dirLabel {
                color: #606880;
                font-size: 12px;
                font-family: "Consolas", monospace;
            }

            /* 좌측 패널 */
            #leftPanel {
                background: #12141c;
                border-right: 1px solid #1e2030;
            }
            #panelTitle {
                color: #5060a0;
                font-size: 11px;
                font-weight: 700;
                font-family: "Consolas", monospace;
                letter-spacing: 2px;
                text-transform: uppercase;
                padding: 4px 2px;
            }
            #fileList {
                background: #12141c;
                border: none;
                color: #8090b0;
                font-size: 11px;
            }
            #fileList::item {
                background: #1a1d28;
                border: 1px solid #22253a;
                border-radius: 8px;
                padding: 4px;
                margin: 2px;
                color: #7080a8;
            }
            #fileList::item:hover {
                background: #1e2238;
                border-color: #3040a0;
                color: #a0b0d8;
            }
            #fileList::item:selected {
                background: #1a2850;
                border: 1px solid #4070e0;
                color: #c0d8ff;
            }
            #countLabel {
                color: #404860;
                font-size: 11px;
                font-family: "Consolas", monospace;
                padding: 2px;
            }

            /* 우측 패널 */
            #rightPanel {
                background: #0d0f14;
            }
            #infoBar {
                background: #161820;
                border-bottom: 1px solid #1e2030;
                color: #6070a0;
                font-size: 12px;
                font-family: "Consolas", monospace;
            }

            /* 하단 컨트롤 바 */
            #ctrlBar {
                background: #101218;
                border-top: 1px solid #1e2030;
            }
            #tipLabel {
                color: #404870;
                font-size: 11px;
            }
            #tipLabel b {
                color: #5060a0;
            }

            /* 상태바 */
            QStatusBar {
                background: #0c0e12;
                color: #404870;
                font-size: 11px;
                font-family: "Consolas", monospace;
                border-top: 1px solid #181a24;
            }

            /* 스플리터 핸들 */
            QSplitter::handle {
                background: #1e2030;
            }
            QSplitter::handle:hover {
                background: #3040a0;
            }


            /* 아이콘 슬라이더 */
            #iconSlider {
                height: 14px;
            }
            #iconSlider::groove:horizontal {
                background: #1e2135;
                height: 4px;
                border-radius: 2px;
                border: 1px solid #2a2d3e;
            }
            #iconSlider::handle:horizontal {
                background: #4070e0;
                width: 14px;
                height: 14px;
                margin: -5px 0;
                border-radius: 7px;
            }
            #iconSlider::handle:horizontal:hover {
                background: #60a0ff;
            }
            #iconSlider::sub-page:horizontal {
                background: #2a4090;
                height: 4px;
                border-radius: 2px;
            }
            /* 스크롤바 */
            QScrollBar:vertical {
                background: #12141c;
                width: 6px;
                border: none;
            }
            QScrollBar::handle:vertical {
                background: #2a2d3e;
                border-radius: 3px;
            }
            QScrollBar::handle:vertical:hover {
                background: #3040a0;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0;
            }
        """)

    def closeEvent(self, event):
        self.vtk_widget.GetRenderWindow().Finalize()
        self.interactor.TerminateApp()
        super().closeEvent(event)


# ─────────────────────────────────────────────
#  엔트리 포인트
# ─────────────────────────────────────────────
def main():
    # 실행 디렉토리 결정
    if len(sys.argv) > 1:
        directory = sys.argv[1]
    else:
        directory = os.getcwd()

    app = QApplication(sys.argv)
    app.setApplicationName("STL Viewer")
    app.setStyle("Fusion")

    # Fusion 다크 팔레트
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(13, 15, 20))
    palette.setColor(QPalette.WindowText, QColor(160, 168, 192))
    palette.setColor(QPalette.Base, QColor(18, 20, 28))
    palette.setColor(QPalette.AlternateBase, QColor(22, 24, 32))
    palette.setColor(QPalette.ToolTipBase, QColor(22, 24, 32))
    palette.setColor(QPalette.ToolTipText, QColor(160, 168, 192))
    palette.setColor(QPalette.Text, QColor(160, 168, 192))
    palette.setColor(QPalette.Button, QColor(26, 28, 40))
    palette.setColor(QPalette.ButtonText, QColor(140, 150, 180))
    palette.setColor(QPalette.BrightText, QColor(200, 215, 255))
    palette.setColor(QPalette.Highlight, QColor(40, 80, 180))
    palette.setColor(QPalette.HighlightedText, QColor(220, 230, 255))
    app.setPalette(palette)

    viewer = STLViewer(directory)
    viewer.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
