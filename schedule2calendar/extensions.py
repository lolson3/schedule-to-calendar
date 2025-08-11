from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_session import Session

csrf = CSRFProtect()
limiter = Limiter(key_func = get_remote_address)
session_ext = Session()