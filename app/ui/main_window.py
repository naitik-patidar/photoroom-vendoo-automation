"""
Main Window for the PhotoRoom + Vendoo Automation App.
"""

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QLineEdit, QPushButton, QTableView, QTextEdit, 
    QLabel, QHeaderView, QMessageBox
)
from PySide6.QtCore import Qt, QTimer

from app.config.settings import Settings
from app.database.db import Database
from app.database.job_repo import JobRepository
from app.ai.command_interpreter import CommandInterpreter
from app.ai.schemas import CommandType
from app.workflow.orchestrator import WorkflowOrchestrator

from app.ui.styles import DARK_THEME_STYLESHEET
from app.ui.models import JobTableModel
from app.ui.threads import WorkflowWorkerThread


class MainWindow(QMainWindow):
    def __init__(
        self, 
        settings: Settings, 
        db: Database,
        job_repo: JobRepository,
        orchestrator: WorkflowOrchestrator,
        interpreter: CommandInterpreter
    ):
        super().__init__()
        
        self.settings = settings
        self.db = db
        self.job_repo = job_repo
        self.orchestrator = orchestrator
        self.interpreter = interpreter
        
        self.active_threads = []
        
        self._init_ui()
        
        # Auto-refresh table
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.refresh_table)
        self.refresh_timer.start(5000) # 5 seconds
        
    def _init_ui(self):
        self.setWindowTitle("PhotoRoom + Vendoo Automation")
        self.resize(900, 600)
        self.setStyleSheet(DARK_THEME_STYLESHEET)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(15)
        
        # --- Header ---
        header = QLabel("AI Workflow Command")
        header.setObjectName("headerLabel")
        main_layout.addWidget(header)
        
        # --- Command Input Bar ---
        input_layout = QHBoxLayout()
        self.command_input = QLineEdit()
        self.command_input.setPlaceholderText('e.g. process "shoe.jpg" brand Nike price $49.99')
        self.command_input.returnPressed.connect(self.on_submit_command)
        input_layout.addWidget(self.command_input)
        
        self.submit_btn = QPushButton("Run Command")
        self.submit_btn.setObjectName("accentButton")
        self.submit_btn.setCursor(Qt.PointingHandCursor)
        self.submit_btn.clicked.connect(self.on_submit_command)
        input_layout.addWidget(self.submit_btn)
        
        main_layout.addLayout(input_layout)
        
        # --- Table View ---
        table_label = QLabel("Recent Jobs")
        table_label.setObjectName("headerLabel")
        main_layout.addWidget(table_label)
        
        self.table_view = QTableView()
        self.table_model = JobTableModel(self.job_repo)
        self.table_view.setModel(self.table_model)
        
        # Table styling
        self.table_view.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table_view.setSelectionBehavior(QTableView.SelectRows)
        self.table_view.setAlternatingRowColors(True)
        self.table_view.verticalHeader().setVisible(False)
        main_layout.addWidget(self.table_view, stretch=2)
        
        # --- Log Output ---
        log_label = QLabel("Workflow Logs")
        log_label.setObjectName("headerLabel")
        main_layout.addWidget(log_label)
        
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        main_layout.addWidget(self.log_output, stretch=1)
        
        self.append_log("System initialized. Ready for commands.")
        
    def append_log(self, message: str):
        self.log_output.append(message)
        # Scroll to bottom
        scrollbar = self.log_output.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
        
    def refresh_table(self):
        self.table_model.refresh()
        
    def on_submit_command(self):
        text = self.command_input.text().strip()
        if not text:
            return
            
        self.command_input.clear()
        self.append_log(f"> {text}")
        
        try:
            # 1. Interpret
            intent = self.interpreter.interpret(text)
            self.append_log(f"Intent recognized: {intent.command_type.value}")
            
            # 2. Queue Job(s)
            job_ids = []
            if intent.command_type == CommandType.PROCESS_IMAGE:
                job = self.job_repo.create(intent.command.image_path)
                job_ids.append(job.job_id)
            elif intent.command_type == CommandType.BATCH_PROCESS:
                # We expect the user input to pass a folder. The mock command interpreter
                # handles it by just setting command.folder_path
                # In a real batch, we would scan the folder for images.
                import glob
                import os
                folder = intent.command.folder_path
                if not os.path.exists(folder):
                    self.append_log(f"Error: Folder not found: {folder}")
                    return
                # Get all JPG/PNG
                for ext in ('*.jpg', '*.jpeg', '*.png'):
                    for img_path in glob.glob(os.path.join(folder, ext)):
                        job = self.job_repo.create(img_path)
                        job_ids.append(job.job_id)
                        
                if not job_ids:
                    self.append_log(f"No images found in {folder}")
                    return
            elif intent.command_type == CommandType.RETRY:
                count = self.orchestrator.retry_failed_jobs()
                self.append_log(f"Queued {count} failed jobs for retry.")
                self.refresh_table()
                return
            else:
                self.append_log("Command type not fully supported in UI yet.")
                return
                
            self.refresh_table()
            
            # 3. Start Thread
            thread = WorkflowWorkerThread(
                self.orchestrator, 
                intent.command_type, 
                intent.command,
                job_ids
            )
            thread.log_message.connect(self.append_log)
            thread.job_completed.connect(self.on_job_completed)
            thread.job_failed.connect(self.on_job_failed)
            thread.batch_completed.connect(self.on_batch_completed)
            
            # Keep a reference to prevent garbage collection
            self.active_threads.append(thread)
            thread.finished.connect(lambda: self.active_threads.remove(thread) if thread in self.active_threads else None)
            
            thread.start()
            
        except Exception as e:
            self.append_log(f"Error: {str(e)}")
            QMessageBox.critical(self, "Error", f"Failed to process command:\n{str(e)}")
            
    def on_job_completed(self, status):
        self.refresh_table()
        
    def on_job_failed(self, job_id, err):
        self.refresh_table()
        
    def on_batch_completed(self, results):
        self.refresh_table()
