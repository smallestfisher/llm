# Application Services

Current service boundaries:

- `auth_service.py`
  authentication and user creation/login helpers
- `admin_service.py`
  user status and password management
- `audit_service.py`
  audit-log write wrapper
- `chat_service.py`
  route snapshot and chat-history shaping
- `chat_execution_service.py`
  background run execution orchestration
- `run_service.py`
  run lifecycle mutations
- `thread_service.py`
  canonical thread/turn/message/run persistence helpers
- `thread_query_service.py`
  thread detail and summary shaping for API responses
- `user_admin_query_service.py`
  admin-side user and audit list views
