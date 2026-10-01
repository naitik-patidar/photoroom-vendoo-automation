"""
Application-wide constants.
"""

# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------
APP_NAME = "PhotoRoom-Vendoo Automation"
APP_VERSION = "0.1.0"

# ---------------------------------------------------------------------------
# Image Formats
# ---------------------------------------------------------------------------
SUPPORTED_INPUT_FORMATS = {".jpg", ".jpeg", ".png", ".webp", ".heic"}
SUPPORTED_OUTPUT_FORMATS = {".png", ".jpg", ".jpeg", ".webp"}
DEFAULT_OUTPUT_FORMAT = ".png"

# Maximum input image file size (25 MB)
MAX_IMAGE_FILE_SIZE_BYTES = 25 * 1024 * 1024

# ---------------------------------------------------------------------------
# PhotoRoom API
# ---------------------------------------------------------------------------
PHOTOROOM_API_BASE_URL = "https://sdk.photoroom.com"
PHOTOROOM_SEGMENT_ENDPOINT = "/v1/segment"
PHOTOROOM_EDIT_ENDPOINT = "/v2/edit"

# Timeouts (seconds)
PHOTOROOM_CONNECT_TIMEOUT = 10
PHOTOROOM_READ_TIMEOUT = 60

# ---------------------------------------------------------------------------
# Job Statuses
# ---------------------------------------------------------------------------
class JobStatus:
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    PHOTOROOM_PROCESSING = "PHOTOROOM_PROCESSING"
    PHOTOROOM_COMPLETE = "PHOTOROOM_COMPLETE"
    LISTING_GENERATED = "LISTING_GENERATED"
    VENDOO_PENDING = "VENDOO_PENDING"
    VENDOO_COMPLETE = "VENDOO_COMPLETE"
    CROSSLISTING = "CROSSLISTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    RETRYING = "RETRYING"

    ALL = {
        QUEUED, PROCESSING, PHOTOROOM_PROCESSING, PHOTOROOM_COMPLETE,
        LISTING_GENERATED, VENDOO_PENDING, VENDOO_COMPLETE,
        CROSSLISTING, COMPLETED, FAILED, RETRYING,
    }

# ---------------------------------------------------------------------------
# Retry Policy
# ---------------------------------------------------------------------------
MAX_RETRY_COUNT = 3
RETRY_BASE_DELAY_SECONDS = 2.0  # exponential backoff base
RETRY_MAX_DELAY_SECONDS = 60.0

# ---------------------------------------------------------------------------
# Batch Processing
# ---------------------------------------------------------------------------
MAX_BATCH_SIZE = 100  # maximum images per batch
BATCH_CONCURRENCY = 3  # concurrent jobs in a batch

# ---------------------------------------------------------------------------
# File Naming
# ---------------------------------------------------------------------------
ORIGINAL_SUFFIX = "_original"
PROCESSED_SUFFIX = "_processed"
