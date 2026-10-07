from __future__ import annotations

import json
import logging
import webbrowser
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Qt, Signal, Slot
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QFrame, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QMainWindow, QMessageBox, QPlainTextEdit,
    QPushButton, QScrollArea, QSizePolicy, QSplitter, QStackedWidget, QVBoxLayout,
    QWidget,
)

from app.core.config import AppConfig
from app.data.catalog import CATALOG
from app.services.downloads import DownloadService
from app.services.installer import InstallerService
from app.services.uninstaller import UninstallerService
from app.services.winscript import WinScriptService
from app.ui.theme import apply_theme

LOGGER = logging.getLogger(__name__)


class WorkerSignals(QObject):
    message = Signal(str)
    result = Signal(object)
    error = Signal(str)
    finished = Signal()


class Worker(QRunnable):
    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self.fn, self.args, self.kwargs = fn, args, kwargs
        self.signals = WorkerSignals()

    @Slot()
    def run(self):
        try:
            self.signals.result.emit(self.fn(*self.args, emit=self.signals.message.emit, **self.kwargs))
        except Exception as exc:
            LOGGER.exception("Worker failure")
            self.signals.error.emit(str(exc))
        finally:
            self.signals.finished.emit()


class MainWindow(QMainWindow):
    def __init__(self, config: AppConfig):
        super().__init__()
        self.config = config
        self.pool = QThreadPool.globalInstance()
        self.downloader = DownloadService(config.paths.cache)
        self.installer = InstallerService(self.downloader)
        self.winscript = WinScriptService(config.paths.cache, config.paths.scripts)
        self.uninstaller = UninstallerService()
        self.log_widgets = []
        self.setWindowTitle("GS Installer · bancada operacional")
        self.resize(1280, 780)
        self._build()
        apply_theme(self._app(), config.theme)

    def _app(self):
        from PySide6.QtWidgets import QApplication
        return QApplication.instance()

    def _build(self):
        root = QWidget()
        layout = QHBoxLayout(root)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(16)
        layout.addWidget(self._rail())
        self.stack = QStackedWidget()
        self.stack.addWidget(self._install_page())
        self.stack.addWidget(self._clean_page())
        self.stack.addWidget(self._uninstall_page())
        layout.addWidget(self.stack, 1)
        self.setCentralWidget(root)

    def _rail(self):
        rail = QFrame(objectName="rail")
        rail.setFixedWidth(220)
        box = QVBoxLayout(rail)
        box.setContentsMargins(18, 22, 18, 18)
        brand = QLabel("GS INSTALLER", objectName="brand")
        box.addWidget(brand)
        box.addWidget(QLabel("BANCADA OPERACIONAL", objectName="eyebrow"))
        box.addSpacing(28)
        for index, (label, detail) in enumerate((("Instalar", "Catálogo oficial"), ("Limpar", "WinScript offline"), ("Desinstalar", "Varredura profunda"))):
            button = QPushButton(f"{label}\n{detail}")
            button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            button.clicked.connect(lambda checked=False, i=index: self.stack.setCurrentIndex(i))
            box.addWidget(button)
            box.addSpacing(5)
        box.addStretch()
        settings = QPushButton("Configuração")
        settings.clicked.connect(self._settings)
        box.addWidget(settings)
        return rail

    def _page_header(self, title: str, subtitle: str):
        wrapper = QWidget()
        box = QVBoxLayout(wrapper)
        box.setContentsMargins(0, 0, 0, 12)
        title_label = QLabel(title)
        title_label.setStyleSheet("font-size: 24pt; font-weight: 700;")
        box.addWidget(title_label)
        box.addWidget(QLabel(subtitle, objectName="muted"))
        return wrapper

    def _activity(self):
        log = QPlainTextEdit()
        log.setReadOnly(True)
        log.setPlaceholderText("A atividade da bancada aparecerá aqui…")
        log.setMinimumHeight(150)
        self.log_widgets.append(log)
        return log

    def _install_page(self):
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.addWidget(self._page_header("Instalar em lote", "Selecione aplicações. A ferramenta procura no caminho local e depois consulta releases oficiais quando há um provider seguro."))
        controls = QHBoxLayout()
        self.install_search = QLineEdit()
        self.install_search.setPlaceholderText("Buscar programa…")
        self.install_search.textChanged.connect(self._refresh_install_list)
        controls.addWidget(self.install_search, 1)
        self.category = QComboBox()
        self.category.addItem("Todas as categorias")
        self.category.addItems(sorted({item.category for item in CATALOG}))
        self.category.currentTextChanged.connect(self._refresh_install_list)
        controls.addWidget(self.category)
        select_all = QPushButton("Selecionar visíveis")
        select_all.clicked.connect(lambda: self._set_all(self.install_list, True))
        controls.addWidget(select_all)
        outer.addLayout(controls)
        splitter = QSplitter()
        self.install_list = QListWidget()
        self.install_list.itemChanged.connect(lambda _: self._update_count())
        splitter.addWidget(self.install_list)
        outer.addWidget(splitter, 1)
        action = QHBoxLayout()
        self.install_count = QLabel("0 selecionados", objectName="muted")
        action.addWidget(self.install_count)
        action.addStretch()
        install = QPushButton("Instalar selecionados", objectName="primary")
        install.clicked.connect(self._run_install)
        action.addWidget(install)
        outer.addLayout(action)
        outer.addWidget(QLabel("ATIVIDADE", objectName="eyebrow"))
        outer.addWidget(self._activity())
        self._refresh_install_list()
        return page

    def _refresh_install_list(self):
        if not hasattr(self, "install_list"):
            return
        query = self.install_search.text().lower()
        category = self.category.currentText()
        self.install_list.blockSignals(True)
        self.install_list.clear()
        for item in CATALOG:
            if query not in item.name.lower() and query not in item.category.lower():
                continue
            if category != "Todas as categorias" and category != item.category:
                continue
            row = QListWidgetItem(f"{item.name}   ·   {item.category}")
            row.setData(32, item.slug)
            row.setToolTip(f"Fonte oficial: {item.official_url}")
            row.setFlags(row.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            row.setCheckState(Qt.CheckState.Checked if item.slug in self.config.selected_installers else Qt.CheckState.Unchecked)
            self.install_list.addItem(row)
        self.install_list.blockSignals(False)
        self._update_count()

    def _update_count(self):
        if hasattr(self, "install_count"):
            self.install_count.setText(f"{len(self._checked(self.install_list))} selecionados")

    @staticmethod
    def _checked(widget):
        return [widget.item(i) for i in range(widget.count()) if widget.item(i).checkState() == Qt.CheckState.Checked]

    @staticmethod
    def _set_all(widget, checked):
        for i in range(widget.count()):
            widget.item(i).setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)

    def _run_install(self):
        items = {item.slug: item for item in CATALOG}
        selected = [items[row.data(32)] for row in self._checked(self.install_list)]
        if not selected:
            QMessageBox.information(self, "Nada selecionado", "Marque pelo menos um programa para instalar.")
            return
        self.config.selected_installers = [item.slug for item in selected]
        self.config.save()
        self._append("— início da instalação em lote —")
        worker = Worker(self._install_batch, selected)
        worker.signals.message.connect(self._append)
        self.pool.start(worker)

    def _install_batch(self, selected, emit):
        results = []
        for item in selected:
            results.append(self.installer.install(item, Path(self.config.installer_path), emit))
        emit(f"Lote finalizado: {sum(results)}/{len(results)} concluídos")
        return results

    def _clean_page(self):
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.addWidget(self._page_header("Limpar com WinScript", "Scripts ficam em cache depois do primeiro download. Pré-visualize o conteúdo antes de executar qualquer mudança."))
        toolbar = QHBoxLayout()
        refresh = QPushButton("Atualizar scripts oficiais")
        refresh.clicked.connect(self._load_scripts)
        toolbar.addWidget(refresh)
        toolbar.addStretch()
        run = QPushButton("Executar selecionados", objectName="primary")
        run.clicked.connect(self._run_scripts)
        toolbar.addWidget(run)
        outer.addLayout(toolbar)
        split = QSplitter()
        self.script_list = QListWidget()
        self.script_list.currentItemChanged.connect(self._preview_script)
        split.addWidget(self.script_list)
        self.script_preview = QPlainTextEdit()
        self.script_preview.setReadOnly(True)
        self.script_preview.setPlaceholderText("Selecione um script para visualizar o que ele faz.")
        split.addWidget(self.script_preview)
        outer.addWidget(split, 1)
        outer.addWidget(QLabel("ATIVIDADE", objectName="eyebrow"))
        outer.addWidget(self._activity())
        self._populate_scripts(self.winscript.list_scripts())
        return page

    def _load_scripts(self):
        worker = Worker(self.winscript.ensure_available)
        worker.signals.message.connect(self._append)
        worker.signals.result.connect(self._populate_scripts)
        worker.signals.error.connect(lambda error: self._append(f"WinScript indisponível: {error}"))
        self.pool.start(worker)

    def _populate_scripts(self, scripts):
        self.script_list.clear()
        if not scripts:
            empty = QListWidgetItem("Nenhum script em cache — clique em 'Atualizar scripts oficiais'")
            empty.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.script_list.addItem(empty)
            return
        for script in scripts:
            row = QListWidgetItem(script.stem.replace("_", " "))
            row.setData(32, str(script))
            row.setCheckState(Qt.CheckState.Checked if str(script) in self.config.selected_cleanup_scripts else Qt.CheckState.Unchecked)
            self.script_list.addItem(row)

    def _preview_script(self, current, previous):
        if current:
            self.script_preview.setPlainText(self.winscript.preview(Path(current.data(32))))

    def _run_scripts(self):
        selected = [Path(row.data(32)) for row in self._checked(self.script_list)]
        if not selected:
            QMessageBox.information(self, "Nada selecionado", "Marque pelo menos um script.")
            return
        answer = QMessageBox.warning(self, "Confirmar limpeza", "Os scripts selecionados podem alterar configurações do Windows. Você revisou a prévia e deseja continuar?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if answer != QMessageBox.Yes:
            return
        self.config.selected_cleanup_scripts = [str(p) for p in selected]
        self.config.save()
        worker = Worker(self._scripts_batch, selected)
        worker.signals.message.connect(self._append)
        self.pool.start(worker)

    def _scripts_batch(self, selected, emit):
        results = [self.winscript.execute(script, emit) for script in selected]
        emit(f"Limpeza finalizada: {sum(results)}/{len(results)} scripts concluídos")
        return results

    def _uninstall_page(self):
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.addWidget(self._page_header("Desinstalar profundamente", "O desinstalador oficial é executado primeiro. Residuais são exibidos antes de qualquer remoção forçada."))
        toolbar = QHBoxLayout()
        refresh = QPushButton("Ler programas instalados")
        refresh.clicked.connect(self._load_programs)
        toolbar.addWidget(refresh)
        self.force_remove = QCheckBox("Desinstalação forçada")
        toolbar.addWidget(self.force_remove)
        toolbar.addStretch()
        remove = QPushButton("Desinstalar selecionados", objectName="danger")
        remove.clicked.connect(self._run_uninstall)
        toolbar.addWidget(remove)
        outer.addLayout(toolbar)
        self.program_list = QListWidget()
        outer.addWidget(self.program_list, 1)
        outer.addWidget(QLabel("ATIVIDADE", objectName="eyebrow"))
        outer.addWidget(self._activity())
        self._load_programs()
        return page

    def _load_programs(self):
        self.program_list.clear()
        programs = self.uninstaller.list_programs()
        for program in programs:
            row = QListWidgetItem(f"{program.name}   ·   {program.version or 'versão desconhecida'}   ·   {program.publisher or 'fabricante desconhecido'}")
            row.setData(32, program)
            row.setCheckState(Qt.CheckState.Unchecked)
            self.program_list.addItem(row)
        self._append(f"{len(programs)} programas encontrados no registro de desinstalação")

    def _run_uninstall(self):
        selected = [row.data(32) for row in self._checked(self.program_list)]
        if not selected:
            QMessageBox.information(self, "Nada selecionado", "Marque pelo menos um programa.")
            return
        warning = "Isso executará os desinstaladores e listará residuais."
        if self.force_remove.isChecked():
            warning += " A remoção forçada apagará diretórios residuais aprovados."
        if QMessageBox.warning(self, "Confirmar desinstalação", warning, QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
            return
        worker = Worker(self._uninstall_batch, selected, self.force_remove.isChecked())
        worker.signals.message.connect(self._append)
        self.pool.start(worker)

    def _uninstall_batch(self, selected, force, emit):
        removed = []
        for program in selected:
            removed.extend(self.uninstaller.uninstall(program, force, emit))
        emit(f"Relatório final: {len(removed)} caminhos removidos; candidatos não forçados permanecem para revisão.")
        return removed

    def _settings(self):
        path, _ = QFileDialog.getExistingDirectory(self, "Escolha a pasta local de instaladores", self.config.installer_path), ""
        if path:
            self.config.installer_path = path
            self.config.save()
            self._append(f"Pasta local configurada: {path}")

    def _append(self, message: str):
        for log in self.log_widgets:
            log.appendPlainText(message)

    def closeEvent(self, event):
        self.config.save()
        super().closeEvent(event)
