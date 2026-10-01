"""
PySide6 Data Models for the UI.
"""

from typing import List, Any
from PySide6.QtCore import QAbstractTableModel, Qt, QModelIndex
from app.database.job_repo import JobRepository
from app.database.models import Job


class JobTableModel(QAbstractTableModel):
    """
    Model for displaying jobs in a QTableView.
    """
    
    HEADERS = ["Job ID", "Status", "PhotoRoom", "Listing", "Vendoo", "Created"]
    
    def __init__(self, job_repo: JobRepository):
        super().__init__()
        self.job_repo = job_repo
        self.jobs: List[Job] = []
        self.refresh()
        
    def refresh(self):
        """Fetch latest jobs from database."""
        self.beginResetModel()
        # In a real app we might paginate or limit, but we'll fetch all for this prototype
        all_jobs = self.job_repo.get_all()
        # Sort by newest first
        self.jobs = sorted(all_jobs, key=lambda x: x.created_at, reverse=True)
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self.jobs)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(self.HEADERS)
        
    def data(self, index: QModelIndex, role: int = Qt.DisplayRole) -> Any:
        if not index.isValid() or not (0 <= index.row() < len(self.jobs)):
            return None
            
        job = self.jobs[index.row()]
        col = index.column()
        
        if role == Qt.DisplayRole:
            if col == 0:
                return job.job_id[:8]  # Short ID
            elif col == 1:
                return job.status
            elif col == 2:
                return job.photoroom_status
            elif col == 3:
                return job.listing_status
            elif col == 4:
                return job.vendoo_status
            elif col == 5:
                # Format ISO datetime
                try:
                    return job.created_at.split('T')[1][:8] # HH:MM:SS
                except:
                    return job.created_at
                    
        # Optional: Add color coding or icons for statuses (Qt.BackgroundRole, Qt.DecorationRole)
        
        return None

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole) -> Any:
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            if 0 <= section < len(self.HEADERS):
                return self.HEADERS[section]
        return None
