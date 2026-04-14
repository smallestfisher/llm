# 应用服务层说明

当前服务边界如下：

- `auth_service.py`
  - 认证、用户创建、登录辅助逻辑
- `admin_service.py`
  - 用户状态与密码管理
- `audit_service.py`
  - 审计日志写入封装
- `chat_service.py`
  - 路由快照与聊天历史整理
- `chat_execution_service.py`
  - 后台运行执行编排
- `run_service.py`
  - 运行生命周期状态变更
- `thread_service.py`
  - 线程 / 轮次 / 消息 / 运行的标准持久化辅助
- `thread_query_service.py`
  - 面向 API 响应的线程详情与摘要整理
- `user_admin_query_service.py`
  - 管理端用户列表与审计列表查询视图
