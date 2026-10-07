from __future__ import annotations

import logging
import threading
from collections import Counter
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Qt, Signal, Slot, QSize
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox, QComboBox, QFileDialog, QFormLayout, QFrame, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QMessageBox, QPlainTextEdit,
    QProgressBar, QPushButton, QSplitter, QTabWidget, QVBoxLayout, QWidget, QStyle,
)

from app.core.config import AppConfig
from app.data.catalog import CATALOG
from app.services.downloads import DownloadService
from app.services.installer import InstallerService
from app.services.uninstaller import UninstallerService
from app.services.winscript import WinScriptService
from app.ui.theme import apply_theme
from app.ui.icons import icon_for, icon_for_installed, icon_size

LOGGER = logging.getLogger(__name__)


class WorkerSignals(QObject):
    message = Signal(str)
    result = Signal(object)
    error = Signal(str)
    finished = Signal()
    progress = Signal(int, int)
    download_progress = Signal(int, int)


class Worker(QRunnable):
    def __init__(self, fn, *args, pass_progress=False, **kwargs):
        super().__init__()
        self.fn, self.args, self.kwargs = fn, args, kwargs
        self.pass_progress = pass_progress
        self.signals = WorkerSignals()

    @Slot()
    def run(self):
        try:
            call_kwargs = dict(self.kwargs, emit=self.signals.message.emit)
            if self.pass_progress:
                call_kwargs["progress"] = self.signals.progress.emit
                call_kwargs["download_progress"] = self.signals.download_progress.emit
            self.signals.result.emit(self.fn(*self.args, **call_kwargs))
        except Exception as exc:
            LOGGER.exception("Worker failure")
            self.signals.error.emit(str(exc))
        finally:
            self.signals.finished.emit()


class MainWindow(QMainWindow):
    """Four-tab operator workbench for install, cleanup, uninstall and settings."""

    CATEGORY_FILTERS = [
        ("Todas as categorias", None),
        ("Web Browsers", "Navegadores"),
        ("Messaging", "Mensageria"),
        ("Media", "Mídia"),
        ("Imaging", "Imaging"),
        ("Documents", "Documents"),
        ("Security", "Segurança / Limpeza"),
        ("Utilities", "Utilitários"),
        ("Developer Tools", "Desenvolvimento"),
        ("Compression", "Compression"),
        ("Online Storage", "Online Storage"),
        ("Other", "Outros"),
    ]

    def __init__(self, config: AppConfig):
        super().__init__()
        self.config = config
        self.pool = QThreadPool.globalInstance()
        self.downloader = DownloadService(config.paths.cache)
        self.installer = InstallerService(self.downloader)
        self.winscript = WinScriptService(config.paths.cache, config.paths.scripts)
        self.uninstaller = UninstallerService()
        self.log_widgets: list[QPlainTextEdit] = []
        self.setWindowTitle("NiniteTool · GS Installer")
        self.setMinimumSize(980, 680)
        self.resize(1220, 820)
        self._build()
        apply_theme(self._app(), config.theme)

    @staticmethod
    def _app():
        from PySide6.QtWidgets import QApplication
        return QApplication.instance()

    def _build(self):
        root = QWidget()
        layout = QHBoxLayout(root)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(16)
        layout.addWidget(self._rail())
        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.addTab(self._install_page(), "Instalar")
        self.tabs.addTab(self._clean_page(), "Limpeza")
        self.tabs.addTab(self._uninstall_page(), "Desinstalar")
        self.tabs.addTab(self._settings_page(), "Configurações")
        self.tabs.currentChanged.connect(self._set_active_nav)
        layout.addWidget(self.tabs, 1)
        self.setCentralWidget(root)

    def _rail(self):
        rail = QFrame(objectName="rail")
        rail.setFixedWidth(238)
        box = QVBoxLayout(rail)
        box.setContentsMargins(18, 22, 18, 18)
        brand = QLabel("GS INSTALLER", objectName="brand")
        box.addWidget(brand)
        box.addWidget(QLabel("BANCADA OPERACIONAL", objectName="eyebrow"))
        box.addSpacing(24)
        self.nav_buttons = []
        for index, (label, detail) in enumerate((("Instalar", "Catálogo oficial"), ("Limpeza", "WinScript offline"), ("Desinstalar", "Varredura profunda"), ("Configurações", "Preferências"))):
            button = QPushButton(f"{label}\n{detail}")
            button.setObjectName("nav")
            button.setProperty("active", index == 0)
            button.setIcon(QApplication.style().standardIcon((QStyle.StandardPixmap.SP_DirOpenIcon, QStyle.StandardPixmap.SP_BrowserReload, QStyle.StandardPixmap.SP_TrashIcon, QStyle.StandardPixmap.SP_FileDialogDetailedView)[index]))
            button.setIconSize(QSize(22, 22))
            self.nav_buttons.append(button)
            button.clicked.connect(lambda checked=False, i=index: self.tabs.setCurrentIndex(i))
            box.addWidget(button)
            box.addSpacing(5)
        box.addStretch()
        box.addWidget(QLabel("v0.1.0", objectName="muted"))
        return rail

    def _set_active_nav(self, index: int):
        for position, button in enumerate(getattr(self, "nav_buttons", [])):
            button.setProperty("active", position == index)
            button.style().unpolish(button)
            button.style().polish(button)

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
        log.setMinimumHeight(140)
        self.log_widgets.append(log)
        return log

    def _install_page(self):
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.addWidget(self._page_header("Instalar em lote", "Escolha programas por categoria. O instalador prioriza arquivos locais e fontes oficiais."))
        controls = QHBoxLayout()
        self.install_search = QLineEdit()
        self.install_search.setPlaceholderText("Buscar programa…")
        self.install_search.textChanged.connect(self._refresh_install_list)
        controls.addWidget(self.install_search, 1)
        self.category = QComboBox()
        for label, value in self.CATEGORY_FILTERS:
            self.category.addItem(label, value)
        self.category.currentIndexChanged.connect(self._refresh_install_list)
        controls.addWidget(self.category)
        select_category = QPushButton("Selecionar categoria")
        select_category.clicked.connect(lambda: self._set_all(self.install_list, True))
        controls.addWidget(select_category)
        clear_category = QPushButton("Limpar categoria")
        clear_category.clicked.connect(lambda: self._set_all(self.install_list, False))
        controls.addWidget(clear_category)
        outer.addLayout(controls)
        self.install_list = QListWidget()
        self.install_list.setIconSize(icon_size(52))
        self.install_list.setSpacing(8)
        self.install_list.setViewMode(QListWidget.ViewMode.IconMode)
        self.install_list.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.install_list.setGridSize(QSize(292, 112))
        self.install_list.itemChanged.connect(self._install_selection_changed)
        outer.addWidget(self.install_list, 1)
        action = QHBoxLayout()
        self.install_count = QLabel("0 selecionados", objectName="muted")
        action.addWidget(self.install_count)
        action.addStretch()
        self.install_button = QPushButton("Instalar selecionados", objectName="primary")
        self.install_button.clicked.connect(self._run_install)
        action.addWidget(self.install_button)
        outer.addLayout(action)
        progress_box = QVBoxLayout()
        progress_box.addWidget(QLabel("PROGRESSO GERAL", objectName="eyebrow"))
        self.install_progress = QProgressBar()
        self.install_progress.setRange(0, 1)
        self.install_progress.setValue(0)
        self.install_progress.setFormat("Aguardando seleção")
        progress_box.addWidget(self.install_progress)
        self.download_progress = QProgressBar()
        self.download_progress.setRange(0, 100)
        self.download_progress.setValue(0)
        self.download_progress.setFormat("Download: aguardando")
        progress_box.addWidget(self.download_progress)
        outer.addLayout(progress_box)
        outer.addWidget(QLabel("ATIVIDADE", objectName="eyebrow"))
        outer.addWidget(self._activity())
        self._refresh_install_list()
        return page

    def _refresh_install_list(self):
        if not hasattr(self, "install_list"):
            return
        query = self.install_search.text().lower()
        category = self.category.currentData()
        self.install_list.blockSignals(True)
        self.install_list.clear()
        for item in CATALOG:
            if query not in item.name.lower() and query not in item.category.lower():
                continue
            if category and category != item.category:
                continue
            label = next((name for name, value in self.CATEGORY_FILTERS if value == item.category), item.category)
            row = QListWidgetItem(f"{item.name}   ·   {label}")
            row.setData(Qt.ItemDataRole.UserRole, item.slug)
            row.setIcon(icon_for(item.slug))
            row.setSizeHint(QSize(274, 96))
            row.setToolTip(f"Fonte oficial: {item.official_url}")
            row.setFlags(row.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            row.setCheckState(Qt.CheckState.Checked if item.slug in self.config.selected_installers else Qt.CheckState.Unchecked)
            self.install_list.addItem(row)
        self.install_list.blockSignals(False)
        self._update_count()

    def _update_count(self):
        if hasattr(self, "install_count"):
            self.install_count.setText(f"{len(self._checked(self.install_list))} selecionados")

    def _install_selection_changed(self, _item):
        self._update_count()
        if not hasattr(self, "install_list"):
            return
        selected = set(self.config.selected_installers)
        for row in self._checked(self.install_list):
            selected.add(row.data(Qt.ItemDataRole.UserRole))
        for index in range(self.install_list.count()):
            row = self.install_list.item(index)
            if row.checkState() == Qt.CheckState.Unchecked:
                selected.discard(row.data(Qt.ItemDataRole.UserRole))
        self.config.selected_installers = sorted(selected)
        self.config.save()

    @staticmethod
    def _checked(widget):
        return [widget.item(i) for i in range(widget.count()) if widget.item(i).checkState() == Qt.CheckState.Checked]

    @staticmethod
    def _set_all(widget, checked):
        for i in range(widget.count()):
            widget.item(i).setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)

    def _run_install(self):
        items = {item.slug: item for item in CATALOG}
        selected = [items[row.data(Qt.ItemDataRole.UserRole)] for row in self._checked(self.install_list)]
        if not selected:
            QMessageBox.information(self, "Nada selecionado", "Marque pelo menos um programa para instalar.")
            return
        answer = QMessageBox.question(
            self,
            "Confirmar instalação",
            f"Deseja instalar {len(selected)} programa(s) em modo silencioso?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            return
        self.config.selected_installers = [item.slug for item in selected]
        self.config.save()
        self._append("— início da instalação em lote —")
        self.install_button.setEnabled(False)
        self.install_progress.setRange(0, len(selected))
        self.install_progress.setValue(0)
        self.install_progress.setFormat(f"0/{len(selected)} programas concluídos")
        self.download_progress.setValue(0)
        self.download_progress.setFormat("Download: aguardando")
        worker = Worker(self._install_batch, selected, pass_progress=True)
        worker.signals.message.connect(self._append)
        worker.signals.progress.connect(self._install_progress_changed)
        worker.signals.download_progress.connect(self._download_progress_changed)
        worker.signals.result.connect(self._install_finished)
        worker.signals.error.connect(lambda error: self._append(f"Falha no lote: {error}"))
        worker.signals.finished.connect(lambda: self.install_button.setEnabled(True))
        self.pool.start(worker)

    def _install_batch(self, selected, emit, progress, download_progress):
        results = self.installer.install_batch(
            selected,
            Path(self.config.installer_path),
            emit,
            progress,
            download_progress,
        )
        emit("Lote finalizado.")
        return results

    def _install_progress_changed(self, completed: int, total: int):
        self.install_progress.setValue(completed)
        self.install_progress.setFormat(f"{completed}/{total} programas concluídos")

    def _download_progress_changed(self, downloaded: int, total: int):
        if total > 0:
            percent = min(100, int(downloaded * 100 / total))
            self.download_progress.setValue(percent)
            self.download_progress.setFormat(f"Download: {percent}% ({downloaded:,}/{total:,} bytes)")
        else:
            self.download_progress.setFormat(f"Download: {downloaded:,} bytes")

    def _install_finished(self, results):
        counts = Counter(result.status.value for result in results)
        summary = f"Resumo: {counts.get('sucesso', 0)} sucesso(s), {counts.get('falha', 0)} falha(s), {counts.get('já instalado', 0)} já instalado(s)."
        self._append(summary)
        self.download_progress.setValue(0)
        self.download_progress.setFormat("Download: concluído")
        QMessageBox.information(self, "Instalação finalizada", summary)

    def _clean_page(self):
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.addWidget(self._page_header("Limpeza com WinScript", "Revise o script antes de executar. O conteúdo fica disponível offline após o primeiro download."))
        toolbar = QHBoxLayout()
        refresh = QPushButton("Atualizar scripts oficiais")
        refresh.clicked.connect(self._load_scripts)
        toolbar.addWidget(refresh)
        select = QPushButton("Selecionar tudo")
        select.clicked.connect(lambda: self._set_all(self.script_list, True))
        toolbar.addWidget(select)
        clear = QPushButton("Limpar seleção")
        clear.clicked.connect(lambda: self._set_all(self.script_list, False))
        toolbar.addWidget(clear)
        toolbar.addStretch()
        run = QPushButton("Executar selecionados", objectName="primary")
        run.clicked.connect(self._run_scripts)
        self.clean_run_button = run
        toolbar.addWidget(self.clean_run_button)
        self.clean_cancel_button = QPushButton("Cancelar")
        self.clean_cancel_button.setEnabled(False)
        self.clean_cancel_button.clicked.connect(self._cancel_scripts)
        toolbar.addWidget(self.clean_cancel_button)
        outer.addLayout(toolbar)
        split = QSplitter()
        self.script_list = QListWidget()
        self.script_list.setIconSize(icon_size(36))
        self.script_list.setSpacing(5)
        self.script_list.currentItemChanged.connect(self._preview_script)
        split.addWidget(self.script_list)
        self.script_preview = QPlainTextEdit()
        self.script_preview.setReadOnly(True)
        self.script_preview.setPlaceholderText("Selecione um script para visualizar o que ele faz.")
        split.addWidget(self.script_preview)
        outer.addWidget(split, 1)
        outer.addWidget(QLabel("PROGRESSO", objectName="eyebrow"))
        self.clean_progress = QProgressBar()
        self.clean_progress.setRange(0, 1)
        self.clean_progress.setValue(0)
        self.clean_progress.setFormat("Aguardando seleção")
        outer.addWidget(self.clean_progress)
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
            row = QListWidgetItem(f"{script.stem.replace('_', ' ')}   ·   {self.winscript.category_for(script)}")
            row.setData(Qt.ItemDataRole.UserRole, str(script))
            row.setIcon(icon_for("powershell"))
            row.setSizeHint(QSize(280, 60))
            row.setFlags(row.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            row.setCheckState(Qt.CheckState.Checked if str(script) in self.config.selected_cleanup_scripts else Qt.CheckState.Unchecked)
            self.script_list.addItem(row)

    def _preview_script(self, current, previous):
        if current and current.data(Qt.ItemDataRole.UserRole):
            self.script_preview.setPlainText(self.winscript.preview(Path(current.data(Qt.ItemDataRole.UserRole))))

    def _run_scripts(self):
        selected = [Path(row.data(Qt.ItemDataRole.UserRole)) for row in self._checked(self.script_list) if row.data(Qt.ItemDataRole.UserRole)]
        if not selected:
            QMessageBox.information(self, "Nada selecionado", "Marque pelo menos um script.")
            return
        answer = QMessageBox.warning(self, "Confirmar limpeza", "Os scripts podem alterar configurações do Windows. Você revisou a prévia?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if answer != QMessageBox.Yes:
            return
        self.config.selected_cleanup_scripts = [str(p) for p in selected]
        self.config.save()
        self.clean_cancel_event = threading.Event()
        self.clean_run_button.setEnabled(False)
        self.clean_cancel_button.setEnabled(True)
        self.clean_progress.setRange(0, len(selected))
        self.clean_progress.setValue(0)
        self.clean_progress.setFormat(f"0/{len(selected)} scripts concluídos")
        worker = Worker(self._scripts_batch, selected, pass_progress=True)
        worker.signals.message.connect(self._append)
        worker.signals.progress.connect(self._clean_progress_changed)
        worker.signals.download_progress.connect(lambda done, total: None)
        worker.signals.result.connect(self._scripts_finished)
        worker.signals.finished.connect(self._scripts_worker_finished)
        self.pool.start(worker)

    def _scripts_batch(self, selected, emit, progress, download_progress):
        results = self.winscript.execute_selected(selected, emit, progress=progress, cancel_event=self.clean_cancel_event)
        emit("Limpeza finalizada.")
        return results

    def _clean_progress_changed(self, completed: int, total: int):
        self.clean_progress.setValue(completed)
        self.clean_progress.setFormat(f"{completed}/{total} scripts concluídos")

    def _scripts_finished(self, results):
        counts = {status: sum(result.status == status for result in results) for status in ("sucesso", "falha", "cancelado")}
        self._append(f"Resumo da limpeza: {counts['sucesso']} sucesso(s), {counts['falha']} falha(s), {counts['cancelado']} cancelado(s).")

    def _scripts_worker_finished(self):
        self.clean_run_button.setEnabled(True)
        self.clean_cancel_button.setEnabled(False)

    def _cancel_scripts(self):
        if hasattr(self, "clean_cancel_event"):
            self.clean_cancel_event.set()
            self._append("Cancelamento solicitado; aguardando o script atual encerrar…")

    def _uninstall_page(self):
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.addWidget(self._page_header("Desinstalação profunda", "Execute o desinstalador oficial primeiro e revise residuais antes de qualquer remoção forçada."))
        toolbar = QHBoxLayout()
        self.uninstall_search = QLineEdit()
        self.uninstall_search.setPlaceholderText("Buscar programa instalado…")
        self.uninstall_search.textChanged.connect(self._filter_programs)
        toolbar.addWidget(self.uninstall_search, 1)
        refresh = QPushButton("Ler programas instalados")
        refresh.clicked.connect(self._load_programs)
        toolbar.addWidget(refresh)
        select = QPushButton("Selecionar tudo")
        select.clicked.connect(lambda: self._set_all(self.program_list, True))
        toolbar.addWidget(select)
        clear = QPushButton("Limpar seleção")
        clear.clicked.connect(lambda: self._set_all(self.program_list, False))
        toolbar.addWidget(clear)
        self.deep_remove = QCheckBox("Desinstalação profunda")
        toolbar.addWidget(self.deep_remove)
        self.deep_remove.setChecked(True)
        self.force_remove = QCheckBox("Forçar se o oficial falhar")
        toolbar.addWidget(self.force_remove)
        toolbar.addStretch()
        remove = QPushButton("Desinstalar selecionados", objectName="danger")
        remove.clicked.connect(self._run_uninstall)
        self.uninstall_button = remove
        toolbar.addWidget(remove)
        outer.addLayout(toolbar)
        self.program_list = QListWidget()
        self.program_list.setIconSize(icon_size(44))
        self.program_list.setSpacing(6)
        self.program_list.itemChanged.connect(self._uninstall_selection_changed)
        outer.addWidget(self.program_list, 1)
        self.uninstall_count = QLabel("0 selecionados", objectName="muted")
        outer.addWidget(self.uninstall_count)
        self.uninstall_progress = QProgressBar()
        self.uninstall_progress.setRange(0, 1)
        self.uninstall_progress.setValue(0)
        self.uninstall_progress.setFormat("Aguardando seleção")
        outer.addWidget(self.uninstall_progress)
        outer.addWidget(QLabel("RELATÓRIO / ATIVIDADE", objectName="eyebrow"))
        outer.addWidget(self._activity())
        self._load_programs()
        return page

    def _uninstall_selection_changed(self, _item):
        self.uninstall_count.setText(f"{len(self._checked(self.program_list))} selecionados")

    def _uninstall_progress_changed(self, completed: int, total: int):
        self.uninstall_progress.setRange(0, total)
        self.uninstall_progress.setValue(completed)
        self.uninstall_progress.setFormat(f"{completed}/{total} programas processados")

    def _load_programs(self):
        self.program_list.clear()
        for program in self.uninstaller.list_programs():
            size = f"{program.size_kb / 1024:.1f} MB" if program.size_kb else "tamanho desconhecido"
            row = QListWidgetItem(f"{program.name}   ·   {program.version or 'versão desconhecida'}   ·   {program.publisher or 'fabricante desconhecido'}   ·   {size}")
            row.setData(Qt.ItemDataRole.UserRole, program)
            row.setIcon(icon_for_installed(program.display_icon, program.name))
            row.setSizeHint(QSize(420, 68))
            row.setFlags(row.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            row.setCheckState(Qt.CheckState.Unchecked)
            self.program_list.addItem(row)
        self._append(f"{self.program_list.count()} programas encontrados no registro de desinstalação")

    def _filter_programs(self):
        if not hasattr(self, "program_list"):
            return
        query = self.uninstall_search.text().casefold()
        for index in range(self.program_list.count()):
            row = self.program_list.item(index)
            program = row.data(Qt.ItemDataRole.UserRole)
            haystack = f"{program.name} {program.publisher} {program.version}".casefold()
            row.setHidden(bool(query and query not in haystack))

    def _run_uninstall(self):
        selected = [row.data(Qt.ItemDataRole.UserRole) for row in self._checked(self.program_list) if not row.isHidden()]
        if not selected:
            QMessageBox.information(self, "Nada selecionado", "Marque pelo menos um programa.")
            return
        deep = self.deep_remove.isChecked()
        force = self.force_remove.isChecked()
        warning = "Isso executará os desinstaladores oficiais."
        if deep:
            warning += " A desinstalação profunda fará varredura e remoção de arquivos e chaves residuais."
        if force:
            warning += " O modo forçado continuará quando o desinstalador oficial falhar."
        if QMessageBox.warning(self, "Confirmar desinstalação", warning, QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
            return
        self.uninstall_button.setEnabled(False)
        self.uninstall_progress.setRange(0, len(selected))
        self.uninstall_progress.setValue(0)
        self.uninstall_progress.setFormat(f"0/{len(selected)} programas processados")
        worker = Worker(self._uninstall_batch, selected, deep, force, pass_progress=True)
        worker.signals.message.connect(self._append)
        worker.signals.progress.connect(self._uninstall_progress_changed)
        worker.signals.result.connect(self._uninstall_finished)
        worker.signals.error.connect(lambda error: self._append(f"Falha no lote: {error}"))
        worker.signals.finished.connect(lambda: self.uninstall_button.setEnabled(True))
        self.pool.start(worker)

    def _uninstall_batch(self, selected, deep, force, emit, progress, download_progress=None):
        reports = self.uninstaller.uninstall_many(selected, deep=deep, force=force, emit=emit, progress=progress)
        emit(f"Relatório final: {len(reports)} programa(s) processado(s).")
        return reports

    def _uninstall_finished(self, reports):
        protected = sum(report.protected for report in reports)
        files = sum(len(report.files_removed) for report in reports)
        registry = sum(len(report.registry_removed) for report in reports)
        self._append(f"Resíduos removidos: {files} arquivo(s), {registry} chave(s); protegidos ignorados: {protected}.")

    def _settings_page(self):
        page = QWidget()
        outer = QVBoxLayout(page)
        outer.addWidget(self._page_header("Configurações", "Preferências são salvas em config.json ao lado do executável para preservar o modo portátil."))
        form = QFormLayout()
        self.installer_path_edit = QLineEdit(self.config.installer_path)
        browse = QPushButton("Escolher pasta…")
        browse.clicked.connect(self._browse_installers)
        path_row = QHBoxLayout()
        path_row.addWidget(self.installer_path_edit, 1)
        path_row.addWidget(browse)
        form.addRow("Instaladores locais", path_row)
        self.theme_combo = QComboBox()
        self.theme_combo.addItem("Dark", "dark")
        self.theme_combo.addItem("Light", "light")
        self.theme_combo.setCurrentIndex(0 if self.config.theme == "dark" else 1)
        self.theme_combo.currentIndexChanged.connect(self._theme_changed)
        form.addRow("Tema", self.theme_combo)
        self.cache_checkbox = QCheckBox("Usar cache local após o primeiro download")
        self.cache_checkbox.setChecked(self.config.cache_enabled)
        form.addRow("Downloads", self.cache_checkbox)
        self.auto_updates_checkbox = QCheckBox("Verificar atualizações da ferramenta ao iniciar")
        self.auto_updates_checkbox.setChecked(self.config.auto_check_updates)
        form.addRow("Atualizações", self.auto_updates_checkbox)
        self.log_level_combo = QComboBox()
        self.log_level_combo.addItems(["DEBUG", "INFO", "WARNING", "ERROR"])
        self.log_level_combo.setCurrentText(self.config.log_level)
        form.addRow("Nível de log", self.log_level_combo)
        cache_label = QLabel(str(self.config.paths.cache))
        cache_label.setObjectName("muted")
        cache_label.setToolTip("Cache portátil usado para downloads e WinScript")
        form.addRow("Pasta de cache", cache_label)
        facilitator = QLabel("O caminho local é apenas um facilitador; a ferramenta também funciona baixando fontes oficiais.", objectName="muted")
        facilitator.setWordWrap(True)
        form.addRow("Nota", facilitator)
        outer.addLayout(form)
        save = QPushButton("Salvar configurações", objectName="primary")
        save.clicked.connect(self._save_settings)
        outer.addWidget(save)
        outer.addSpacing(20)
        outer.addWidget(QLabel("SOBRE", objectName="eyebrow"))
        outer.addWidget(QLabel("NiniteTool / GS Installer\nv0.1.0 · ferramenta portátil para Windows 10/11\nFontes de download: somente páginas oficiais e releases do GitHub."))
        outer.addStretch()
        return page

    def _browse_installers(self):
        path = QFileDialog.getExistingDirectory(self, "Escolha a pasta local de instaladores", self.installer_path_edit.text())
        if path:
            self.installer_path_edit.setText(path)

    def _save_settings(self):
        self.config.installer_path = self.installer_path_edit.text().strip() or self.config.installer_path
        self.config.theme = self.theme_combo.currentData()
        self.config.cache_enabled = self.cache_checkbox.isChecked()
        self.config.auto_check_updates = self.auto_updates_checkbox.isChecked()
        self.config.log_level = self.log_level_combo.currentText()
        valid, message = self.config.validate_installers_path(create=True)
        if not valid:
            QMessageBox.warning(self, "Caminho inválido", message)
            return
        self.config.save()
        logging.getLogger().setLevel(getattr(logging, self.config.log_level, logging.INFO))
        apply_theme(self._app(), self.config.theme)
        self._append(f"Configurações salvas. {message}")

    def _theme_changed(self):
        if hasattr(self, "theme_combo"):
            self.config.theme = self.theme_combo.currentData()
            apply_theme(self._app(), self.config.theme)
            self.config.save()

    def _append(self, message: str):
        stamped = f"{datetime.now():%H:%M:%S}  {message}"
        logging.getLogger("ui").info(message)
        for log in self.log_widgets:
            log.appendPlainText(stamped)

    def closeEvent(self, event):
        if hasattr(self, "installer_path_edit"):
            self.config.installer_path = self.installer_path_edit.text().strip() or self.config.installer_path
            self.config.theme = self.theme_combo.currentData()
            self.config.cache_enabled = self.cache_checkbox.isChecked()
            self.config.auto_check_updates = self.auto_updates_checkbox.isChecked()
            self.config.log_level = self.log_level_combo.currentText()
        self.config.save()
        super().closeEvent(event)
