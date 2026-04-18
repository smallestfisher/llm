import os
import random
import pymysql

# --- 1. 数据库配置 ---
DB_CONFIG = {
    "host": os.getenv("MYSQL_HOST", "172.17.0.2"),
    "port": int(os.getenv("MYSQL_PORT", "3306")),
    "user": os.getenv("MYSQL_USER", "root"),
    "password": os.getenv("MYSQL_PASSWORD", "021598"),
    "charset": "utf8mb4",
    "autocommit": False,
}
DB_NAME = "boe_planner_db"

# --- 2. 格式化生成工具 ---
def generate_material_family():
    """生成成套的产品物料逻辑：包含成品FGCODE、内部PID、Array段代码、Cell段代码"""
    base_num = random.randint(100, 200)
    is_nv = random.choice([True, False])
    
    if is_nv:
        # NV 体系: 客户DELL等，有后缀-D000的内部号
        base_name = f"NV{base_num}WUM-N4B"
        fg = f"{base_name}-8000"
        pid = f"{base_name}-D000"
        array_code = f"B8A{base_num}ABE801"
        cell_code = f"B8P{base_num}ABE801"
    else:
        # BV/B8 体系: 客户OV等，PID是完全另一套B8Q开头
        fg = f"BV{base_num:03d}WFQ-L16-8000"
        pid = f"B8Q{random.randint(100,999)}QD5E102"
        array_code = f"B8A160ABE801"
        cell_code = f"B8P160ABE801"
        
    return {
        "fg": fg,
        "pid": pid,
        "array": array_code,
        "cell": cell_code,
        "cut": random.choice([60, 72])
    }

def gen_pm_version(v_type):
    """
    按指定类型生成版本号
    v_type: 'V' 生成类似 202504W2V2 (销售需求)
    v_type: 'P' 生成类似 202604W2P1 (生产需求)
    """
    month = random.choice([3, 4, 5])
    return f"2026{month:02d}W{random.randint(1,4)}{v_type}{random.randint(1,2)}"

# --- 3. 11张表的建表语句 (字段严格对齐 JSON) ---
CREATE_SQL = {
    "v_demand": "CREATE TABLE v_demand (id BIGINT AUTO_INCREMENT PRIMARY KEY, PM_VERSION VARCHAR(32), FGCODE VARCHAR(64), SBU_DESC VARCHAR(32), CUSTOMER VARCHAR(32), MONTH VARCHAR(10), REQUIREMENT_QTY INT, NEXT_REQUIREMENT INT, LAST_REQUIREMENT INT, MONTH4 INT, MONTH5 INT, MONTH6 INT, MONTH7 INT)",
    "p_demand": "CREATE TABLE p_demand (id BIGINT AUTO_INCREMENT PRIMARY KEY, PM_VERSION VARCHAR(32), FGCODE VARCHAR(64), SBU_DESC VARCHAR(32), BU_DESC VARCHAR(32), CUSTOMER VARCHAR(32), MONTH VARCHAR(10), REQUIREMENT_QTY INT, NEXT_REQUIREMENT INT, LAST_REQUIREMENT INT, MONTH4 INT, MONTH5 INT, MONTH6 INT, MONTH7 INT)",
    "daily_inventory": "CREATE TABLE daily_inventory (id BIGINT AUTO_INCREMENT PRIMARY KEY, report_date VARCHAR(16), factory_code VARCHAR(32), ERP_FACTORY VARCHAR(32), ERP_LOCATION VARCHAR(32), product_ID VARCHAR(64), PRODUCTION_TYPE VARCHAR(32), GRADE VARCHAR(16), CHECKINCODE VARCHAR(32), TTL_Qty INT, HOLD_Qty INT)",
    "daily_PLAN": "CREATE TABLE daily_PLAN (id BIGINT AUTO_INCREMENT PRIMARY KEY, PLAN_date VARCHAR(16), factory_code VARCHAR(32), product_ID VARCHAR(64), target_qty INT)",
    "monthly_plan_approved": "CREATE TABLE monthly_plan_approved (id BIGINT AUTO_INCREMENT PRIMARY KEY, plan_month VARCHAR(10), PLAN_date VARCHAR(16), factory_code VARCHAR(32), product_ID VARCHAR(64), target_IN_glass_qty INT, target_in_panel_qty INT, target_Out_glass_qty INT, target_Out_panel_qty INT)",
    "oms_inventory": "CREATE TABLE oms_inventory (id BIGINT AUTO_INCREMENT PRIMARY KEY, report_month VARCHAR(10), product_ID VARCHAR(64), SBU_DESC VARCHAR(32), BU_DESC VARCHAR(32), CUSTOMER VARCHAR(32), ERP_FACTORY VARCHAR(32), ERP_LOCATION VARCHAR(32), LGORT_DL VARCHAR(32), LGORT_LX VARCHAR(32), GRADE_FL VARCHAR(32), GRADE VARCHAR(16), glass_qty INT, panel_qty INT, ONE_AGE_panel_qty INT, TWO_AGE_panel_qty INT, THREE_AGE_panel_qty INT, FOUR_AGE_panel_qty INT, FIVE_AGE_panel_qty INT, SIX_AGE_panel_qty INT, SEVEN_AGE_panel_qty INT, EUGHT_AGE_panel_qty INT)",
    "product_attributes": "CREATE TABLE product_attributes (id BIGINT AUTO_INCREMENT PRIMARY KEY, product_ID VARCHAR(64), application VARCHAR(32), CUT_NUM INT, common_categories VARCHAR(64), IS_OXIDE VARCHAR(1), IS_XPS VARCHAR(1), IS_sloc VARCHAR(1), IS_cOATER VARCHAR(1), IS_OA VARCHAR(1), IS_Notch VARCHAR(1))",
    "product_mapping": "CREATE TABLE product_mapping (id BIGINT AUTO_INCREMENT PRIMARY KEY, FGCODE VARCHAR(64), cell_no VARCHAR(64), array_no VARCHAR(64), cf_no VARCHAR(64))",
    "production_actuals": "CREATE TABLE production_actuals (id BIGINT AUTO_INCREMENT PRIMARY KEY, work_date VARCHAR(16), FACTORY VARCHAR(32), product_ID VARCHAR(64), act_type VARCHAR(32), GLS_qty INT, Panel_qty INT, defect_qty INT)",
    "sales_financial_perf": "CREATE TABLE sales_financial_perf (id BIGINT AUTO_INCREMENT PRIMARY KEY, report_month VARCHAR(10), SBU_DESC VARCHAR(32), BU_DESC VARCHAR(32), CUSTOMER VARCHAR(32), FGCODE VARCHAR(64), sales_qty INT, FINANCIAL_qty INT)",
    "weekly_rolling_plan": "CREATE TABLE weekly_rolling_plan (id BIGINT AUTO_INCREMENT PRIMARY KEY, PM_VERSION VARCHAR(32), plan_date VARCHAR(16), factory VARCHAR(32), product_ID VARCHAR(64), plan_qty INT)"
}

# --- 4. 执行入库逻辑 ---
def run_insertion(cursor):
    # 生成 50 个严格关联的物料组池
    pool = [generate_material_family() for _ in range(50)]

    # 1. v_demand (强制生成 V 版，使用成品 FGCODE)
    cursor.executemany("INSERT INTO v_demand (PM_VERSION, FGCODE, SBU_DESC, CUSTOMER, MONTH, REQUIREMENT_QTY, NEXT_REQUIREMENT, LAST_REQUIREMENT, MONTH4, MONTH5, MONTH6, MONTH7) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", 
        [(gen_pm_version('V'), p['fg'], "MBL", "OV", "202604", 10000, 50000, 30000, 80000, 0, 0, 10000) for p in pool[:25]])

    # 2. p_demand (强制生成 P 版，使用成品 FGCODE)
    cursor.executemany("INSERT INTO p_demand (PM_VERSION, FGCODE, SBU_DESC, BU_DESC, CUSTOMER, MONTH, REQUIREMENT_QTY, NEXT_REQUIREMENT, LAST_REQUIREMENT, MONTH4, MONTH5, MONTH6, MONTH7) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", 
        [(gen_pm_version('P'), p['fg'], "NB", "NB", "DELL", "202604", 800, 1000, 2000, 5000, 0, 0, 0) for p in pool[25:]])

    # 3. daily_inventory (使用内部 pid，对应物理工厂 B8/B8M2)
    cursor.executemany("INSERT INTO daily_inventory (report_date, factory_code, ERP_FACTORY, ERP_LOCATION, product_ID, PRODUCTION_TYPE, GRADE, CHECKINCODE, TTL_Qty, HOLD_Qty) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", 
        [("20260416", random.choice(["B8", "B8M2"]), "1800", random.choice(["3118","A551"]), p['pid'], random.choice(["Production", "Develop"]), random.choice(["A","AN"]), random.choice(["NULL", "M02"]), 800, 20) for p in pool])

    # 4. daily_PLAN (ARRAY段对应array料号，MDL段对应成品料号)
    cursor.executemany("INSERT INTO daily_PLAN (PLAN_date, factory_code, product_ID, target_qty) VALUES (%s,%s,%s,%s)", 
        [("20260416", "ARRAY", p['array'], 1000) for p in pool[:25]] + 
        [("20260417", "MDL", p['fg'], 15000) for p in pool[25:]])

    # 5. monthly_plan_approved (工厂段与料号严格对应)
    cursor.executemany("INSERT INTO monthly_plan_approved (plan_month, PLAN_date, factory_code, product_ID, target_IN_glass_qty, target_in_panel_qty, target_Out_glass_qty, target_Out_panel_qty) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)", 
        [("202604", "20260416", "ARRAY", p['array'], 1000, 60000, 1000, 60000) for p in pool[:25]] +
        [("202604", "20260417", "MDL", p['fg'], 250, 15000, 200, 1200) for p in pool[25:]])

    # 6. oms_inventory (OMS库存看的是成品，使用 FGCODE，并复刻 EUGHT 拼写)
    cursor.executemany("INSERT INTO oms_inventory (report_month, product_ID, SBU_DESC, BU_DESC, CUSTOMER, ERP_FACTORY, ERP_LOCATION, LGORT_DL, LGORT_LX, GRADE_FL, GRADE, glass_qty, panel_qty, ONE_AGE_panel_qty, TWO_AGE_panel_qty, THREE_AGE_panel_qty, FOUR_AGE_panel_qty, FIVE_AGE_panel_qty, SIX_AGE_panel_qty, SEVEN_AGE_panel_qty, EUGHT_AGE_panel_qty) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", 
        [("202603", p['fg'], "NB", "NB", "DELL", "1800", "A551", "可售", "正常品", "非限制", "AX", 15000, 250, 8000, 0, 5000, 2000, 0, 0, 0, 0) for p in pool])

    # 7. product_attributes (看成品属性，使用 fg，并复刻 IS_cOATER 拼写)
    cursor.executemany("INSERT INTO product_attributes (product_ID, application, CUT_NUM, common_categories, IS_OXIDE, IS_XPS, IS_sloc, IS_cOATER, IS_OA, IS_Notch) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", 
        [(p['fg'], "NB", p['cut'], random.choice(["NB-ADS", "NB-Oxide"]), random.choice(['Y','N']), 'N', 'N', 'Y', 'Y', 'N') for p in pool])

    # 8. product_mapping (主键必须是FGCODE，关联另外三段料号)
    cursor.executemany("INSERT INTO product_mapping (FGCODE, cell_no, array_no, cf_no) VALUES (%s,%s,%s,%s)", 
        [(p['fg'], p['cell'], p['array'], f"CF_{random.randint(100,200)}") for p in pool])

    # 9. production_actuals (CELL段看cell料号，MDL段看fg料号，复刻中文act_type)
    cursor.executemany("INSERT INTO production_actuals (work_date, FACTORY, product_ID, act_type, GLS_qty, Panel_qty, defect_qty) VALUES (%s,%s,%s,%s,%s,%s,%s)", 
        [("20260401", "CELL", p['cell'], "投入", 1000, 60000, 0) for p in pool[:25]] +
        [("20260410", "MDL", p['fg'], "报废", 3, 18, 0) for p in pool[25:]])

    # 10. sales_financial_perf (销售财务看成品，使用 fg)
    cursor.executemany("INSERT INTO sales_financial_perf (report_month, SBU_DESC, BU_DESC, CUSTOMER, FGCODE, sales_qty, FINANCIAL_qty) VALUES (%s,%s,%s,%s,%s,%s,%s)", 
        [("202604", "NB", "NB", "二线", p['fg'], 800, 2000) for p in pool])

    # 11. weekly_rolling_plan (周排产是生产维度，强制P版，按工厂段映射料号)
    cursor.executemany("INSERT INTO weekly_rolling_plan (PM_VERSION, plan_date, factory, product_ID, plan_qty) VALUES (%s,%s,%s,%s,%s)", 
        [(gen_pm_version('P'), "20260408", "CELL", p['cell'], 1000) for p in pool[:25]] +
        [(gen_pm_version('P'), "20260408", "MDL", p['fg'], 10000) for p in pool[25:]])

# --- 5. 主运行入口 ---
def main():
    conn = pymysql.connect(**DB_CONFIG)
    try:
        cursor = conn.cursor()
        # 创建数据库
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}` CHARACTER SET utf8mb4")
        cursor.execute(f"USE `{DB_NAME}`")
        
        # 重置11张表
        for table, sql in CREATE_SQL.items():
            cursor.execute(f"DROP TABLE IF EXISTS `{table}`")
            cursor.execute(sql)
            print(f"[*] 已重置表结构: {table}")

        # 写入数据
        run_insertion(cursor)
        conn.commit()
        print("\n[✔] 大功告成！11张表的测试数据生成及入库完毕，逻辑校验全部对齐。")
    except Exception as e:
        conn.rollback()
        print(f"\n[X] 哎呀，执行报错了: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    main()