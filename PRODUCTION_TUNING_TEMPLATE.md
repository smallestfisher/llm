# Production Tuning Template

用于将当前 `router + skills + composer` 架构适配到真实生产库字段。

填写原则：
- 先填真实数据库结构，再改代码
- 先改 `tables.json`，再改 router / skill / prompt
- 一张表一张表确认，不要靠记忆补字段

---

## 1. 环境信息

### 基础连接
- 环境名称:
- 数据库类型:
- Host:
- Port:
- Database / Schema:
- 账号权限范围:
- 是否只读:

### 运行参数
- `DB_URI`:
- `LOCAL_DB_URI`:
- `OPENAI_BASE_URL`:
- `LLM_MODEL`:

### 风险说明
- 是否存在视图:
- 是否存在分区表:
- 是否存在历史表:
- 是否存在字段同名异义:
- 是否存在敏感字段:

---

## 2. 业务域划分

### Production Domain
- 涉及表:
- 核心指标:
- 核心过滤条件:
- 常见业务问法:

### Inventory Domain
- 涉及表:
- 核心指标:
- 核心过滤条件:
- 常见业务问法:

### Cross Domain
- 常见跨域组合:
- 共享维度:
- 共享过滤条件:
- 汇总输出要求:

### Generic / Fallback
- 兜底表范围:
- 禁止访问表:
- 允许回答范围:

---

## 3. 表清单

每张表复制一份以下模板。

### 表名: `<table_name>`
- 中文名称:
- 所属域:
- 表类型: 明细表 / 汇总表 / 维表 / 视图
- 用途说明:
- 主键:
- 唯一键:
- 时间字段:
- 月份字段:
- 默认排序字段:
- 数据量级:
- 是否需要默认 LIMIT:
- 备注:

#### 常用过滤字段
- 

#### 常用分组字段
- 

#### 常用聚合字段
- 

#### 真实关联关系
- `<field>` -> `<target_table>.<target_field>`

#### 禁止或谨慎事项
- 

---

## 4. 字段清单

每张表逐字段填写。

### 表名: `<table_name>`

| 字段名 | 中文含义 | 类型 | 示例值 | 可空 | 可筛选 | 可分组 | 可聚合 | 业务别名/黑话 | 备注 |
|---|---|---|---|---|---|---|---|---|---|
|  |  |  |  |  |  |  |  |  |  |

---

## 5. 时间口径

### 日级
- 使用字段:
- 时区:
- 是否自然日:
- 是否业务日:

### 周级
- 使用字段:
- 周定义:
- 是否跨月:

### 月级
- 使用字段:
- 格式:
- 是否自然月:
- 是否财务月:

### 最新值判定
- 按哪个字段:
- 是否需要分组后取最新:
- 典型 SQL 约束:

### 最近 N 天
- 是否允许自然语言直接映射:
- 需要额外业务转换吗:

---

## 6. 关系与 Join 规则

### 主关联键
- `product_code`:
- `factory_code`:
- `line_code`:
- `customer_name`:
- 其他:

### 必须带条件的 Join
- 

### 容易错的 Join
- 

### 应禁止的 Join
- 

---

## 7. Router 调优清单

对应代码：
- [core/router/intent_router.py](/home/y/llm/llm/core/router/intent_router.py)
- [core/router/filter_extractor.py](/home/y/llm/llm/core/router/filter_extractor.py)

### Production 关键词
- 

### Inventory 关键词
- 

### Cross-domain 信号词
- 

### 黑话 / 缩写 / 别名
- 

### 公共过滤器
- 最近 N 天:
- 最新:
- 日期范围:
- 月份范围:
- 版本号:
- 工厂:
- 产品:
- 客户:

---

## 8. Skill 调优清单

### Production Skill
对应代码：
- [core/skills/production/skill.py](/home/y/llm/llm/core/skills/production/skill.py)

- 默认主表:
- 辅助表:
- 常见 group by:
- 常见 metric:
- 重点 SQL 规则:
- 回答口径:

### Inventory Skill
对应代码：
- [core/skills/inventory/skill.py](/home/y/llm/llm/core/skills/inventory/skill.py)

- 默认主表:
- 辅助表:
- 常见 group by:
- 常见 metric:
- 重点 SQL 规则:
- 回答口径:

### Generic Skill
对应代码：
- [core/skills/generic/skill.py](/home/y/llm/llm/core/skills/generic/skill.py)

- 兜底范围:
- 禁止范围:
- 默认收敛策略:

---

## 9. Prompt 调优清单

对应代码：
- [core/skills/prompting.py](/home/y/llm/llm/core/skills/prompting.py)

### Guard Prompt
- 哪些问题必须拒绝:
- 哪些边界问题允许放行:

### Text2SQL Prompt
- 必须强调的表:
- 必须强调的字段:
- 必须强调的 join:
- 必须禁止的模式:

### Reflect Prompt
- 常见报错类型:
- 对应修复策略:

### Answer Prompt
- 业务上最关心的结论:
- 需要避免的表达:

---

## 10. `tables.json` 更新记录

对应代码：
- [core/config/tables.json](/home/y/llm/llm/core/config/tables.json)

### 已确认表
- [ ] `<table_name>`
- [ ] `<table_name>`

### 已确认 relationships
- [ ] `<table_name>.<field> -> <target_table>.<field>`

### 已确认时间字段
- [ ] `<table_name>.<date_col/month_col>`

---

## 11. 测试样例

对应文件：
- [tests/goldens.json](/home/y/llm/llm/tests/goldens.json)

### 单域问句
```json
{
  "question": "",
  "expected_route": "",
  "expected_skill": "",
  "expected_field": ""
}
```

### 跨域问句
```json
{
  "question": "",
  "expected_route": "cross_domain",
  "expected_field": ""
}
```

### 歧义问句
```json
{
  "question": "",
  "expected_route": "general",
  "expected_skill": "generic_skill"
}
```

---

## 12. 联调记录

### 本地静态校验
- [ ] `python3 -m compileall app.py core tests`
- [ ] `python3 -m unittest discover -s tests -p 'test_*.py'`

### 回归评测
- [ ] `python3 tests/eval_runner.py`

### 实库联调
- [ ] 单域生产查询通过
- [ ] 单域库存查询通过
- [ ] 跨域查询通过
- [ ] 审计日志正常
- [ ] 聊天历史正常

### 已知问题
- 

### 下一步动作
- 
