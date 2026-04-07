import pymysql
import random
from datetime import datetime, timedelta

# ==========================================
# 1. 数据库连接配置 (请根据你的本地环境修改)
# ==========================================
DB_CONFIG = {
    'host': '172.17.0.2',
    'port': 3306,
    'user': 'root',
    'password': '021598', # <-- 修改为你的MySQL密码
    'charset': 'utf8mb4'
}
DB_NAME = 'boe_planner_db' # 将要创建的数据库名称

# ==========================================
# 2. BOE 业务基础主数据定义 (纯英文/代码化)
# ==========================================
FACTORIES = ['B4_BJ', 'B7_CD', 'B11_MY', 'B17_WH', 'B20_BJ'] 
CUSTOMERS = ['Apple', 'Samsung', 'Huawei', 'Honor', 'Hisense', 'Lenovo', 'Dell']
TECH_TYPES = ['OLED_Flex', 'OLED_Rigid', 'LCD_IPS', 'LCD_VA', 'Mini_LED']
RESOLUTIONS = ['FHD', '2K', '4K', '8K']
SIZES = ['6.1', '6.7', '14.0', '27.0', '65.0', '75.0', '86.0']
PROCESSES = ['Array', 'Cell', 'Module']
WAREHOUSES = ['RAW', 'WIP', 'FG', 'VMI']
APPS = ['Mobile', 'IT', 'TV', 'Vehicle', 'Wearable']
LIFECYCLES = ['NPI', 'MP', 'EOL']
PD_STATUSES = ['Accepted', 'Partial', 'Cancelled']
ADJUST_REASONS = ['Normal', 'Catch_up', 'Material_Delay', 'EQP_Down', 'None']
GLASS_SIZES = ['Gen_6', 'Gen_8_5', 'Gen_10_5']

# 预生成产品料号池
PRODUCT_CODES = []
for i in range(1, 1050):
    tech = random.choice(TECH_TYPES)
    size = random.choice(SIZES)
    res = random.choice(RESOLUTIONS)
    PRODUCT_CODES.append(f"BOE_{tech}_{size.replace('.','_')}_{res}_{i:04d}")

def random_date(start_date, end_date):
    time_between_dates = end_date - start_date
    days_between_dates = max(time_between_dates.days, 1)
    random_number_of_days = random.randrange(days_between_dates + 1)
    return start_date + timedelta(days=random_number_of_days)

# 默认生成最近一年的数据
end_dt = datetime.now()
start_dt = end_dt - timedelta(days=365)

def run_db_insertion():
    print(f"[*] 正在连接 MySQL 8.0: {DB_CONFIG['host']}:{DB_CONFIG['port']} ...")
    try:
        # 连接数据库服务
        conn = pymysql.connect(**DB_CONFIG)
        cursor = conn.cursor()

        # 确保数据库存在 (MySQL 8.0 规范字符集)
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_NAME} DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci")
        cursor.execute(f"USE {DB_NAME}")
        print(f"[*] 成功连接并进入数据库: {DB_NAME}")

        # ==========================================
        # 0. 清空旧数据（确保重跑后为最新数据）
        # ==========================================
        table_order = [
            "v_demand",
            "p_demand",
            "monthly_plan_approved",
            "weekly_rolling_plan",
            "daily_schedule",
            "work_in_progress",
            "daily_inventory",
            "oms_inventory",
            "production_actuals",
            "product_mapping",
            "product_attributes",
            "sales_financial_perf",
        ]
        for t in table_order:
            try:
                cursor.execute(f"TRUNCATE TABLE `{t}`")
            except Exception:
                # 表不存在时忽略，后续会创建
                pass

        # ==========================================
        # 1. v_demand (V版需求)
        # ==========================================
        print("[*] 正在创建并写入数据: v_demand ...", end="")
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS `v_demand` (
          `id` BIGINT AUTO_INCREMENT COMMENT '主键ID',
          `demand_no` VARCHAR(50) NOT NULL COMMENT 'V版需求编号',
          `customer_name` VARCHAR(50) COMMENT '客户名称',
          `product_code` VARCHAR(50) NOT NULL COMMENT '面板料号',
          `forecast_month` VARCHAR(10) NOT NULL COMMENT '预测需求月份(YYYY-MM)',
          `forecast_qty` INT NOT NULL COMMENT '客户预测数量(PCS)',
          `create_time` DATETIME COMMENT '录入时间',
          PRIMARY KEY (`id`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='V版需求表';
        """)
        cursor.execute("TRUNCATE TABLE `v_demand`") # 保证可重复运行
        data = []
        for i in range(1200):
            dt = random_date(start_dt, end_dt)
            data.append((f"VD_{dt.strftime('%Y%m')}_{i:04d}", random.choice(CUSTOMERS), random.choice(PRODUCT_CODES), dt.strftime('%Y-%m'), random.randint(1000, 500000), dt.strftime('%Y-%m-%d %H:%M:%S')))
        cursor.executemany("INSERT INTO `v_demand` (`demand_no`, `customer_name`, `product_code`, `forecast_month`, `forecast_qty`, `create_time`) VALUES (%s, %s, %s, %s, %s, %s)", data)
        print(" OK (1200 rows)")

        # ==========================================
        # 2. p_demand (P版需求)
        # ==========================================
        print("[*] 正在创建并写入数据: p_demand ...", end="")
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS `p_demand` (
          `id` BIGINT AUTO_INCREMENT COMMENT '主键ID',
          `p_demand_no` VARCHAR(50) NOT NULL COMMENT 'P版需求单号',
          `v_demand_no` VARCHAR(50) COMMENT '关联的V版需求单号',
          `product_code` VARCHAR(50) NOT NULL COMMENT '面板料号',
          `commit_month` VARCHAR(10) NOT NULL COMMENT '承诺交货月份',
          `commit_qty` INT NOT NULL COMMENT '承诺产能(PCS)',
          `status` VARCHAR(20) COMMENT '状态(Accepted/Partial/Cancelled)',
          PRIMARY KEY (`id`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='P版需求表';
        """)
        cursor.execute("TRUNCATE TABLE `p_demand`")
        data = []
        for i in range(1200):
            dt = random_date(start_dt, end_dt)
            data.append((f"PD_{dt.strftime('%Y%m')}_{i:04d}", f"VD_{dt.strftime('%Y%m')}_{i:04d}", random.choice(PRODUCT_CODES), dt.strftime('%Y-%m'), random.randint(800, 480000), random.choice(PD_STATUSES)))
        cursor.executemany("INSERT INTO `p_demand` (`p_demand_no`, `v_demand_no`, `product_code`, `commit_month`, `commit_qty`, `status`) VALUES (%s, %s, %s, %s, %s, %s)", data)
        print(" OK (1200 rows)")

        # ==========================================
        # 3. monthly_plan_approved (审批版月计划)
        # ==========================================
        print("[*] 正在创建并写入数据: monthly_plan_approved ...", end="")
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS `monthly_plan_approved` (
          `id` BIGINT AUTO_INCREMENT COMMENT '主键ID',
          `plan_month` VARCHAR(10) NOT NULL COMMENT '计划月份',
          `factory_code` VARCHAR(50) COMMENT '生产厂区',
          `product_code` VARCHAR(50) NOT NULL COMMENT '面板料号',
          `target_glass_qty` INT COMMENT '目标投片量',
          `target_panel_qty` INT NOT NULL COMMENT '目标产出量',
          `version` VARCHAR(10) COMMENT '版本号',
          PRIMARY KEY (`id`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='审批版月计划';
        """)
        cursor.execute("TRUNCATE TABLE `monthly_plan_approved`")
        data = []
        for i in range(1050):
            dt = random_date(start_dt, end_dt)
            glass = random.randint(1000, 50000)
            panel = glass * random.choice([2, 6, 18, 60, 200])
            data.append((dt.strftime('%Y-%m'), random.choice(FACTORIES), random.choice(PRODUCT_CODES), glass, panel, 'V1.0'))
        cursor.executemany("INSERT INTO `monthly_plan_approved` (`plan_month`, `factory_code`, `product_code`, `target_glass_qty`, `target_panel_qty`, `version`) VALUES (%s, %s, %s, %s, %s, %s)", data)
        print(" OK (1050 rows)")

        # ==========================================
        # 4. weekly_rolling_plan (周别月计划)
        # ==========================================
        print("[*] 正在创建并写入数据: weekly_rolling_plan ...", end="")
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS `weekly_rolling_plan` (
          `id` BIGINT AUTO_INCREMENT COMMENT '主键ID',
          `plan_month` VARCHAR(10) NOT NULL COMMENT '所属月份',
          `week_no` INT NOT NULL COMMENT '周别(1-52)',
          `factory_code` VARCHAR(50) COMMENT '厂区',
          `product_code` VARCHAR(50) NOT NULL COMMENT '料号',
          `planned_qty` INT NOT NULL COMMENT '本周计划产出(PCS)',
          `adjust_reason` VARCHAR(50) COMMENT '调整原因',
          PRIMARY KEY (`id`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='周别月计划';
        """)
        cursor.execute("TRUNCATE TABLE `weekly_rolling_plan`")
        data = []
        for i in range(1200):
            dt = random_date(start_dt, end_dt)
            week = dt.isocalendar()[1]
            data.append((dt.strftime('%Y-%m'), week, random.choice(FACTORIES), random.choice(PRODUCT_CODES), random.randint(10000, 100000), random.choice(ADJUST_REASONS)))
        cursor.executemany("INSERT INTO `weekly_rolling_plan` (`plan_month`, `week_no`, `factory_code`, `product_code`, `planned_qty`, `adjust_reason`) VALUES (%s, %s, %s, %s, %s, %s)", data)
        print(" OK (1200 rows)")

        # ==========================================
        # 5. daily_schedule (Daily计划)
        # ==========================================
        print("[*] 正在创建并写入数据: daily_schedule ...", end="")
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS `daily_schedule` (
          `id` BIGINT AUTO_INCREMENT COMMENT '主键ID',
          `work_date` DATE NOT NULL COMMENT '生产日期',
          `factory_code` VARCHAR(50) COMMENT '厂区',
          `line_code` VARCHAR(50) COMMENT '产线/机台',
          `product_code` VARCHAR(50) NOT NULL COMMENT '料号',
          `shift` VARCHAR(10) COMMENT '班次(Day/Night)',
          `target_qty` INT NOT NULL COMMENT '当日排产数量',
          PRIMARY KEY (`id`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Daily计划';
        """)
        cursor.execute("TRUNCATE TABLE `daily_schedule`")
        data = []
        for i in range(1500):
            dt = random_date(start_dt, end_dt).strftime('%Y-%m-%d')
            line = f"{random.choice(PROCESSES)}_L{random.randint(1,5)}"
            data.append((dt, random.choice(FACTORIES), line, random.choice(PRODUCT_CODES), random.choice(['Day', 'Night']), random.randint(1000, 20000)))
        cursor.executemany("INSERT INTO `daily_schedule` (`work_date`, `factory_code`, `line_code`, `product_code`, `shift`, `target_qty`) VALUES (%s, %s, %s, %s, %s, %s)", data)
        print(" OK (1500 rows)")

        # ==========================================
        # 6. work_in_progress (WIP表)
        # ==========================================
        print("[*] 正在创建并写入数据: work_in_progress ...", end="")
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS `work_in_progress` (
          `id` BIGINT AUTO_INCREMENT COMMENT '主键ID',
          `lot_id` VARCHAR(50) NOT NULL COMMENT '批次号',
          `factory_code` VARCHAR(50) COMMENT '厂区',
          `product_code` VARCHAR(50) NOT NULL COMMENT '料号',
          `current_process` VARCHAR(50) COMMENT '当前所在工序',
          `wip_qty` INT NOT NULL COMMENT '滞留数量',
          `hold_flag` TINYINT(1) COMMENT '是否冻结(0/1)',
          `update_time` DATETIME COMMENT '更新时间',
          PRIMARY KEY (`id`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='WIP表';
        """)
        cursor.execute("TRUNCATE TABLE `work_in_progress`")
        data = []
        for i in range(1200):
            dt = random_date(start_dt, end_dt).strftime('%Y-%m-%d %H:%M:%S')
            data.append((f"LOT_{random.randint(100000,999999)}", random.choice(FACTORIES), random.choice(PRODUCT_CODES), random.choice(PROCESSES), random.randint(100, 5000), random.choice([0,0,0,1]), dt))
        cursor.executemany("INSERT INTO `work_in_progress` (`lot_id`, `factory_code`, `product_code`, `current_process`, `wip_qty`, `hold_flag`, `update_time`) VALUES (%s, %s, %s, %s, %s, %s, %s)", data)
        print(" OK (1200 rows)")

        # ==========================================
        # 7. daily_inventory (Daily库存)
        # ==========================================
        print("[*] 正在创建并写入数据: daily_inventory ...", end="")
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS `daily_inventory` (
          `id` BIGINT AUTO_INCREMENT COMMENT '主键ID',
          `report_date` DATE NOT NULL COMMENT '库存快照日期',
          `factory_code` VARCHAR(50) COMMENT '厂区',
          `warehouse_code` VARCHAR(50) COMMENT '仓库类型',
          `product_code` VARCHAR(50) NOT NULL COMMENT '物料号',
          `available_qty` INT NOT NULL COMMENT '可用库存量',
          `safety_stock` INT COMMENT '安全库存水位',
          PRIMARY KEY (`id`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Daily库存表';
        """)
        cursor.execute("TRUNCATE TABLE `daily_inventory`")
        data = []
        for i in range(1200):
            dt = random_date(start_dt, end_dt).strftime('%Y-%m-%d')
            data.append((dt, random.choice(FACTORIES), random.choice(WAREHOUSES), random.choice(PRODUCT_CODES), random.randint(0, 100000), random.randint(5000, 20000)))
        cursor.executemany("INSERT INTO `daily_inventory` (`report_date`, `factory_code`, `warehouse_code`, `product_code`, `available_qty`, `safety_stock`) VALUES (%s, %s, %s, %s, %s, %s)", data)
        print(" OK (1200 rows)")

        # ==========================================
        # 8. oms_inventory (OMS全渠道库存表)
        # ==========================================
        print("[*] 正在创建并写入数据: oms_inventory ...", end="")
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS `oms_inventory` (
          `id` BIGINT AUTO_INCREMENT COMMENT '主键ID',
          `report_date` DATE NOT NULL COMMENT '统计日期',
          `product_code` VARCHAR(50) NOT NULL COMMENT '面板料号',
          `customer_name` VARCHAR(50) COMMENT '对应客户',
          `in_transit_qty` INT COMMENT '在途库存',
          `hub_qty` INT COMMENT '海外HUB仓库存',
          `customer_hub_qty` INT COMMENT '客户自身库存',
          PRIMARY KEY (`id`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='OMS全渠道库存';
        """)
        cursor.execute("TRUNCATE TABLE `oms_inventory`")
        data = []
        for i in range(1100):
            dt = random_date(start_dt, end_dt).strftime('%Y-%m-%d')
            data.append((dt, random.choice(PRODUCT_CODES), random.choice(CUSTOMERS), random.randint(10000, 50000), random.randint(50000, 200000), random.randint(0, 100000)))
        cursor.executemany("INSERT INTO `oms_inventory` (`report_date`, `product_code`, `customer_name`, `in_transit_qty`, `hub_qty`, `customer_hub_qty`) VALUES (%s, %s, %s, %s, %s, %s)", data)
        print(" OK (1100 rows)")

        # ==========================================
        # 9. production_actuals (生产实绩表)
        # ==========================================
        print("[*] 正在创建并写入数据: production_actuals ...", end="")
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS `production_actuals` (
          `id` BIGINT AUTO_INCREMENT COMMENT '主键ID',
          `work_date` DATE NOT NULL COMMENT '生产日期',
          `line_code` VARCHAR(50) COMMENT '产线编号',
          `product_code` VARCHAR(50) NOT NULL COMMENT '料号',
          `input_qty` INT NOT NULL COMMENT '投料数',
          `output_qty` INT NOT NULL COMMENT '良品产出数',
          `defect_qty` INT NOT NULL COMMENT '不良品数',
          `yield_rate` DECIMAL(5,2) NOT NULL COMMENT '良率(%)',
          PRIMARY KEY (`id`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='生产实绩表';
        """)
        cursor.execute("TRUNCATE TABLE `production_actuals`")
        data = []
        for i in range(1500):
            dt = random_date(start_dt, end_dt).strftime('%Y-%m-%d')
            input_q = random.randint(5000, 20000)
            yield_r = random.uniform(85.0, 99.8)
            output_q = int(input_q * (yield_r / 100))
            defect_q = input_q - output_q
            line = f"{random.choice(PROCESSES)}_L{random.randint(1,5)}"
            data.append((dt, line, random.choice(PRODUCT_CODES), input_q, output_q, defect_q, round(yield_r, 2)))
        cursor.executemany("INSERT INTO `production_actuals` (`work_date`, `line_code`, `product_code`, `input_qty`, `output_qty`, `defect_qty`, `yield_rate`) VALUES (%s, %s, %s, %s, %s, %s, %s)", data)
        print(" OK (1500 rows)")

        # ==========================================
        # 10. product_mapping (产品匹配表)
        # ==========================================
        print("[*] 正在创建并写入数据: product_mapping ...", end="")
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS `product_mapping` (
          `id` BIGINT AUTO_INCREMENT COMMENT '主键ID',
          `product_code` VARCHAR(50) NOT NULL COMMENT '成品料号',
          `glass_substrate_size` VARCHAR(50) COMMENT '基板世代',
          `cut_efficiency` INT NOT NULL COMMENT '切片数',
          `preferred_factory` VARCHAR(50) COMMENT '主选厂区',
          `alternative_factory` VARCHAR(50) COMMENT '备选代工厂区',
          PRIMARY KEY (`id`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='产品匹配表';
        """)
        cursor.execute("TRUNCATE TABLE `product_mapping`")
        data = []
        for code in PRODUCT_CODES:
            data.append((code, random.choice(GLASS_SIZES), random.choice([2, 6, 18, 32, 65, 200]), random.choice(FACTORIES), random.choice(FACTORIES)))
        cursor.executemany("INSERT INTO `product_mapping` (`product_code`, `glass_substrate_size`, `cut_efficiency`, `preferred_factory`, `alternative_factory`) VALUES (%s, %s, %s, %s, %s)", data)
        print(f" OK ({len(PRODUCT_CODES)} rows)")

        # ==========================================
        # 11. product_attributes (产品特性表)
        # ==========================================
        print("[*] 正在创建并写入数据: product_attributes ...", end="")
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS `product_attributes` (
          `id` BIGINT AUTO_INCREMENT COMMENT '主键ID',
          `product_code` VARCHAR(50) NOT NULL COMMENT '产品料号',
          `tech_family` VARCHAR(50) COMMENT '技术平台',
          `application` VARCHAR(50) COMMENT '应用领域',
          `std_lead_time_days` INT COMMENT '标准生产周期',
          `moq` INT COMMENT '最小起投量',
          `life_cycle` VARCHAR(20) COMMENT '生命周期(NPI/MP/EOL)',
          PRIMARY KEY (`id`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='产品特性表';
        """)
        cursor.execute("TRUNCATE TABLE `product_attributes`")
        data = []
        for code in PRODUCT_CODES:
            data.append((code, random.choice(TECH_TYPES), random.choice(APPS), random.randint(15, 45), random.choice([1000, 5000, 10000]), random.choice(LIFECYCLES)))
        cursor.executemany("INSERT INTO `product_attributes` (`product_code`, `tech_family`, `application`, `std_lead_time_days`, `moq`, `life_cycle`) VALUES (%s, %s, %s, %s, %s, %s)", data)
        print(f" OK ({len(PRODUCT_CODES)} rows)")

        # ==========================================
        # 12. sales_financial_perf (销售&财务业绩)
        # ==========================================
        print("[*] 正在创建并写入数据: sales_financial_perf ...", end="")
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS `sales_financial_perf` (
          `id` BIGINT AUTO_INCREMENT COMMENT '主键ID',
          `report_month` VARCHAR(10) NOT NULL COMMENT '结算月份(YYYY-MM)',
          `product_code` VARCHAR(50) NOT NULL COMMENT '产品料号',
          `sales_qty` INT NOT NULL COMMENT '当月实际销量',
          `unit_price_usd` DECIMAL(10,2) COMMENT '平均美金单价(ASP)',
          `revenue_usd` DECIMAL(15,2) COMMENT '总营收(USD)',
          `gross_margin_pct` DECIMAL(5,2) COMMENT '毛利率(%)',
          PRIMARY KEY (`id`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='销售与财务业绩表';
        """)
        cursor.execute("TRUNCATE TABLE `sales_financial_perf`")
        data = []
        for i in range(1200):
            dt = random_date(start_dt, end_dt)
            qty = random.randint(5000, 200000)
            price = round(random.uniform(15.0, 350.0), 2)
            data.append((dt.strftime('%Y-%m'), random.choice(PRODUCT_CODES), qty, price, round(qty * price, 2), round(random.uniform(-5.0, 35.0), 2)))
        cursor.executemany("INSERT INTO `sales_financial_perf` (`report_month`, `product_code`, `sales_qty`, `unit_price_usd`, `revenue_usd`, `gross_margin_pct`) VALUES (%s, %s, %s, %s, %s, %s)", data)
        print(" OK (1200 rows)")

        # 提交事务
        conn.commit()
        print("\n[✔] 完美！12张表全部创建完毕并成功写入数据。")

    except Exception as e:
        if 'conn' in locals() and conn.open:
            conn.rollback()
        print(f"\n[X] 执行出现错误: {e}")
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals() and conn.open:
            conn.close()

if __name__ == '__main__':
    run_db_insertion()
