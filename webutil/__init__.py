from flask import Flask
from webutil.core import TmpStorage

# Initialize a temporary storage for uploaded data:
TMP_STORAGE = TmpStorage(ttl_minutes=5)

# Initialize the web application:
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 8 * 1024 * 1024  # max file size (8MB)

# This import is needed to register the view functions:
import webutil.views
