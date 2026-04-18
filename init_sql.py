import os
import random
from datetime import datetime, timedelta

import pymysql


DB_CONFIG = {
    "host": os.getenv("MYSQL_HOST", "172.17.0.2"),
    "port": int(os.getenv("MYSQL_PORT", "3306")),
    "user": os.getenv("MYSQL_USER", "root"),
    "password": os.getenv("MYSQL_PASSWORD", "021598"),
    "charset": "utf8mb4",
    "autocommit": False,
}
DB_NAME = os.getenv("MYSQL_DB", "boe_planner_db")


FACTORIES = ["B4_BJ", "B7_CD", "B11_MY", "B17_WH", "B20_BJ"]
ERP_FACTORIES = ["BJ01", "CD01", "MY01", "WH01"]
ERP_LOCATIONS = ["FG01", "FG02", "HOLD01", "OMS01"]
CUSTOMERS = ["Apple", "Samsung", "Huawei", "Honor", "Lenovo", "Dell"]
SBU_LIST = ["Mobile", "IT", "TV"]
BU_LIST = ["BU_A", "BU_B", "BU_C"]
APPLICATIONS = ["Mobile", "TV", "IT", "Vehicle"]
COMMON_CATEGORIES = ["HighRunner", "Value", "Flagship", "Project"]
VERSION_POOL = ["2026W01", "2026W02", "2026W03", "2026W04"]
GRADES = ["A", "B", "C"]
PRODUCTION_TYPES = ["MP", "NPI"]


def random_day(start: datetime, end: datetime) -> datetime:
    return start + timedelta(days=random.randint(0, max((end - start).days, 1)))


def month_str(base: datetime, offset: int = 0) -> str:
    year = base.year + ((base.month - 1 + offset) // 12)
    month = ((base.month - 1 + offset) % 12) + 1
    return f"{year:04d}-{month:02d}"


def pm_version_anchor_month(pm_version: str) -> datetime:
    """
    将 PM_VERSION(如 2026W03) 映射到对应周所在月份的月初日期。
    若格式异常，回退到当前月。
    """
    try:
        year = int(pm_version[:4])
        week = int(pm_version[5:7])
        if pm_version[4] != "W":
            raise ValueError("invalid pm version format")
        # 业务侧版本周通常按版本年份内周序解释，避免 ISO 周跨年导致落到前一年。
        anchor_day = datetime(year, 1, 1) + timedelta(days=(week - 1) * 7)
        return datetime(anchor_day.year, anchor_day.month, 1)
    except Exception:
        now = datetime.now()
        return datetime(now.year, now.month, 1)


def month_for_pm_version(pm_version: str) -> str:
    """
    业务规则：
    MONTH 与 PM_VERSION 不必相同；
    MONTH 在 PM_VERSION 对应时间往前 6 个月到当月内都视为合理范围。
    """
    anchor = pm_version_anchor_month(pm_version)
    return month_str(anchor, random.randint(-6, 0))


def build_product_catalog(size: int = 120) -> list[dict]:
    catalog: list[dict] = []
    for idx in range(1, size + 1):
        family = random.choice(["OLED", "LCD", "OXIDE", "XPS"])
        product_id = f"PANEL_{family}_{idx:04d}"
        catalog.append(
            {
                "product_ID": product_id,
                "FGCODE": product_id,
                "cell_no": f"CELL_{idx:04d}",
                "array_no": f"ARRAY_{idx:04d}",
                "cf_no": f"CF_{idx:04d}",
                "application": random.choice(APPLICATIONS),
                "cut_num": random.choice([2, 4, 6, 8, 12]),
                "common_categories": random.choice(COMMON_CATEGORIES),
                "is_oxide": 1 if family == "OXIDE" else 0,
                "is_xps": 1 if family == "XPS" else 0,
                "is_sloc": random.choice([0, 1]),
                "is_coater": random.choice([0, 1]),
                "is_oa": random.choice([0, 1]),
                "is_notch": random.choice([0, 1]),
            }
        )
    return catalog


CREATE_SQL = {
    "v_demand": """
        CREATE TABLE IF NOT EXISTS `v_demand` (
          `id` BIGINT AUTO_INCREMENT,
          `PM_VERSION` VARCHAR(20) NOT NULL,
          `FGCODE` VARCHAR(64) NOT NULL,
          `SBU_DESC` VARCHAR(64) NOT NULL,
          `CUSTOMER` VARCHAR(64) NOT NULL,
          `MONTH` VARCHAR(7) NOT NULL,
          `REQUIREMENT_QTY` INT NOT NULL,
          `NEXT_REQUIREMENT` INT NOT NULL,
          `LAST_REQUIREMENT` INT NOT NULL,
          `MONTH4` INT NOT NULL,
          `MONTH5` INT NOT NULL,
          `MONTH6` INT NOT NULL,
          `MONTH7` INT NOT NULL,
          PRIMARY KEY (`id`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    "p_demand": """
        CREATE TABLE IF NOT EXISTS `p_demand` (
          `id` BIGINT AUTO_INCREMENT,
          `PM_VERSION` VARCHAR(20) NOT NULL,
          `FGCODE` VARCHAR(64) NOT NULL,
          `SBU_DESC` VARCHAR(64) NOT NULL,
          `BU_DESC` VARCHAR(64) NOT NULL,
          `CUSTOMER` VARCHAR(64) NOT NULL,
          `MONTH` VARCHAR(7) NOT NULL,
          `REQUIREMENT_QTY` INT NOT NULL,
          `NEXT_REQUIREMENT` INT NOT NULL,
          `LAST_REQUIREMENT` INT NOT NULL,
          `MONTH4` INT NOT NULL,
          `MONTH5` INT NOT NULL,
          `MONTH6` INT NOT NULL,
          `MONTH7` INT NOT NULL,
          PRIMARY KEY (`id`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    "daily_inventory": """
        CREATE TABLE IF NOT EXISTS `daily_inventory` (
          `id` BIGINT AUTO_INCREMENT,
          `report_date` DATE NOT NULL,
          `factory_code` VARCHAR(32) NOT NULL,
          `ERP_FACTORY` VARCHAR(32) NOT NULL,
          `ERP_LOCATION` VARCHAR(32) NOT NULL,
          `product_ID` VARCHAR(64) NOT NULL,
          `PRODUCTION_TYPE` VARCHAR(32) NOT NULL,
          `GRADE` VARCHAR(8) NOT NULL,
          `CHECKINCODE` VARCHAR(32) NOT NULL,
          `TTL_Qty` INT NOT NULL,
          `HOLD_Qty` INT NOT NULL,
          PRIMARY KEY (`id`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    "daily_PLAN": """
        CREATE TABLE IF NOT EXISTS `daily_PLAN` (
          `id` BIGINT AUTO_INCREMENT,
          `PLAN_date` DATE NOT NULL,
          `factory_code` VARCHAR(32) NOT NULL,
          `product_ID` VARCHAR(64) NOT NULL,
          `target_qty` INT NOT NULL,
          PRIMARY KEY (`id`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    "monthly_plan_approved": """
        CREATE TABLE IF NOT EXISTS `monthly_plan_approved` (
          `id` BIGINT AUTO_INCREMENT,
          `plan_month` VARCHAR(7) NOT NULL,
          `PLAN_date` DATE NOT NULL,
          `factory_code` VARCHAR(32) NOT NULL,
          `product_ID` VARCHAR(64) NOT NULL,
          `target_IN_glass_qty` INT NOT NULL,
          `target_in_panel_qty` INT NOT NULL,
          `target_Out_glass_qty` INT NOT NULL,
          `target_Out_panel_qty` INT NOT NULL,
          PRIMARY KEY (`id`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    "oms_inventory": """
        CREATE TABLE IF NOT EXISTS `oms_inventory` (
          `id` BIGINT AUTO_INCREMENT,
          `report_month` VARCHAR(7) NOT NULL,
          `product_ID` VARCHAR(64) NOT NULL,
          `SBU_DESC` VARCHAR(64) NOT NULL,
          `BU_DESC` VARCHAR(64) NOT NULL,
          `CUSTOMER` VARCHAR(64) NOT NULL,
          `ERP_FACTORY` VARCHAR(32) NOT NULL,
          `ERP_LOCATION` VARCHAR(32) NOT NULL,
          `LGORT_DL` VARCHAR(32) NOT NULL,
          `LGORT_LX` VARCHAR(32) NOT NULL,
          `GRADE_FL` VARCHAR(32) NOT NULL,
          `GRADE` VARCHAR(8) NOT NULL,
          `glass_qty` INT NOT NULL,
          `panel_qty` INT NOT NULL,
          `ONE_AGE_panel_qty` INT NOT NULL,
          `TWO_AGE_panel_qty` INT NOT NULL,
          `THREE_AGE_panel_qty` INT NOT NULL,
          `FOUR_AGE_panel_qty` INT NOT NULL,
          `FIVE_AGE_panel_qty` INT NOT NULL,
          `SIX_AGE_panel_qty` INT NOT NULL,
          `SEVEN_AGE_panel_qty` INT NOT NULL,
          `EUGHT_AGE_panel_qty` INT NOT NULL,
          PRIMARY KEY (`id`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    "product_attributes": """
        CREATE TABLE IF NOT EXISTS `product_attributes` (
          `id` BIGINT AUTO_INCREMENT,
          `product_ID` VARCHAR(64) NOT NULL,
          `application` VARCHAR(32) NOT NULL,
          `CUT_NUM` INT NOT NULL,
          `common_categories` VARCHAR(64) NOT NULL,
          `IS_OXIDE` TINYINT(1) NOT NULL,
          `IS_XPS` TINYINT(1) NOT NULL,
          `IS_sloc` TINYINT(1) NOT NULL,
          `IS_cOATER` TINYINT(1) NOT NULL,
          `IS_OA` TINYINT(1) NOT NULL,
          `IS_Notch` TINYINT(1) NOT NULL,
          PRIMARY KEY (`id`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    "product_mapping": """
        CREATE TABLE IF NOT EXISTS `product_mapping` (
          `id` BIGINT AUTO_INCREMENT,
          `FGCODE` VARCHAR(64) NOT NULL,
          `Cell No` VARCHAR(64) NOT NULL,
          `Array No` VARCHAR(64) NOT NULL,
          `CF No` VARCHAR(64) NOT NULL,
          PRIMARY KEY (`id`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    "production_actuals": """
        CREATE TABLE IF NOT EXISTS `production_actuals` (
          `id` BIGINT AUTO_INCREMENT,
          `work_date` DATE NOT NULL,
          `FACTORY` VARCHAR(32) NOT NULL,
          `product_ID` VARCHAR(64) NOT NULL,
          `act_type` VARCHAR(16) NOT NULL,
          `GLS_qty` INT NOT NULL,
          `Panel_qty` INT NOT NULL,
          `defect_qty` INT NOT NULL,
          PRIMARY KEY (`id`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    "sales_financial_perf": """
        CREATE TABLE IF NOT EXISTS `sales_financial_perf` (
          `id` BIGINT AUTO_INCREMENT,
          `report_month` VARCHAR(7) NOT NULL,
          `SBU_DESC` VARCHAR(64) NOT NULL,
          `BU_DESC` VARCHAR(64) NOT NULL,
          `CUSTOMER` VARCHAR(64) NOT NULL,
          `FGCODE` VARCHAR(64) NOT NULL,
          `sales_qty` INT NOT NULL,
          `FINANCIAL_qty` INT NOT NULL,
          PRIMARY KEY (`id`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
    "weekly_rolling_plan": """
        CREATE TABLE IF NOT EXISTS `weekly_rolling_plan` (
          `id` BIGINT AUTO_INCREMENT,
          `PM_VERSION` VARCHAR(20) NOT NULL,
          `plan_date` DATE NOT NULL,
          `factory` VARCHAR(32) NOT NULL,
          `product_ID` VARCHAR(64) NOT NULL,
          `plan_qty` INT NOT NULL,
          PRIMARY KEY (`id`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """,
}


DROP_ORDER = [
    "sales_financial_perf",
    "production_actuals",
    "product_mapping",
    "product_attributes",
    "oms_inventory",
    "monthly_plan_approved",
    "daily_PLAN",
    "daily_inventory",
    "weekly_rolling_plan",
    "p_demand",
    "v_demand",
]


def insert_product_attributes(cursor, catalog: list[dict]) -> None:
    data = [
        (
            item["product_ID"],
            item["application"],
            item["cut_num"],
            item["common_categories"],
            item["is_oxide"],
            item["is_xps"],
            item["is_sloc"],
            item["is_coater"],
            item["is_oa"],
            item["is_notch"],
        )
        for item in catalog
    ]
    cursor.executemany(
        """
        INSERT INTO `product_attributes`
        (`product_ID`, `application`, `CUT_NUM`, `common_categories`, `IS_OXIDE`, `IS_XPS`, `IS_sloc`, `IS_cOATER`, `IS_OA`, `IS_Notch`)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        data,
    )


def insert_product_mapping(cursor, catalog: list[dict]) -> None:
    data = [(item["FGCODE"], item["cell_no"], item["array_no"], item["cf_no"]) for item in catalog]
    cursor.executemany(
        """
        INSERT INTO `product_mapping` (`FGCODE`, `Cell No`, `Array No`, `CF No`)
        VALUES (%s, %s, %s, %s)
        """,
        data,
    )


def insert_v_demand(cursor, catalog: list[dict], start_dt: datetime, end_dt: datetime, rows: int = 600) -> None:
    data = []
    for _ in range(rows):
        base_qty = random.randint(1000, 50000)
        product = random.choice(catalog)
        pm_version = random.choice(VERSION_POOL)
        data.append(
            (
                pm_version,
                product["FGCODE"],
                random.choice(SBU_LIST),
                random.choice(CUSTOMERS),
                month_for_pm_version(pm_version),
                base_qty,
                int(base_qty * random.uniform(0.8, 1.2)),
                int(base_qty * random.uniform(0.8, 1.2)),
                int(base_qty * random.uniform(0.8, 1.2)),
                int(base_qty * random.uniform(0.8, 1.2)),
                int(base_qty * random.uniform(0.8, 1.2)),
                int(base_qty * random.uniform(0.8, 1.2)),
            )
        )
    cursor.executemany(
        """
        INSERT INTO `v_demand`
        (`PM_VERSION`, `FGCODE`, `SBU_DESC`, `CUSTOMER`, `MONTH`, `REQUIREMENT_QTY`, `NEXT_REQUIREMENT`, `LAST_REQUIREMENT`, `MONTH4`, `MONTH5`, `MONTH6`, `MONTH7`)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        data,
    )


def insert_p_demand(cursor, catalog: list[dict], start_dt: datetime, end_dt: datetime, rows: int = 600) -> None:
    data = []
    for _ in range(rows):
        base_qty = random.randint(1000, 50000)
        product = random.choice(catalog)
        pm_version = random.choice(VERSION_POOL)
        data.append(
            (
                pm_version,
                product["FGCODE"],
                random.choice(SBU_LIST),
                random.choice(BU_LIST),
                random.choice(CUSTOMERS),
                month_for_pm_version(pm_version),
                int(base_qty * random.uniform(0.8, 1.0)),
                int(base_qty * random.uniform(0.8, 1.0)),
                int(base_qty * random.uniform(0.8, 1.0)),
                int(base_qty * random.uniform(0.8, 1.0)),
                int(base_qty * random.uniform(0.8, 1.0)),
                int(base_qty * random.uniform(0.8, 1.0)),
                int(base_qty * random.uniform(0.8, 1.0)),
            )
        )
    cursor.executemany(
        """
        INSERT INTO `p_demand`
        (`PM_VERSION`, `FGCODE`, `SBU_DESC`, `BU_DESC`, `CUSTOMER`, `MONTH`, `REQUIREMENT_QTY`, `NEXT_REQUIREMENT`, `LAST_REQUIREMENT`, `MONTH4`, `MONTH5`, `MONTH6`, `MONTH7`)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        data,
    )


def insert_daily_inventory(cursor, catalog: list[dict], start_dt: datetime, end_dt: datetime, rows: int = 700) -> None:
    data = []
    for _ in range(rows):
        dt = random_day(start_dt, end_dt)
        product = random.choice(catalog)
        ttl_qty = random.randint(500, 30000)
        hold_qty = random.randint(0, int(ttl_qty * 0.2))
        data.append(
            (
                dt.strftime("%Y-%m-%d"),
                random.choice(FACTORIES),
                random.choice(ERP_FACTORIES),
                random.choice(ERP_LOCATIONS),
                product["product_ID"],
                random.choice(PRODUCTION_TYPES),
                random.choice(GRADES),
                f"CI{random.randint(1000, 9999)}",
                ttl_qty,
                hold_qty,
            )
        )
    cursor.executemany(
        """
        INSERT INTO `daily_inventory`
        (`report_date`, `factory_code`, `ERP_FACTORY`, `ERP_LOCATION`, `product_ID`, `PRODUCTION_TYPE`, `GRADE`, `CHECKINCODE`, `TTL_Qty`, `HOLD_Qty`)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        data,
    )


def insert_daily_plan(cursor, catalog: list[dict], start_dt: datetime, end_dt: datetime, rows: int = 700) -> None:
    data = []
    for _ in range(rows):
        dt = random_day(start_dt, end_dt)
        product = random.choice(catalog)
        data.append((dt.strftime("%Y-%m-%d"), random.choice(FACTORIES), product["product_ID"], random.randint(1000, 25000)))
    cursor.executemany(
        """
        INSERT INTO `daily_PLAN` (`PLAN_date`, `factory_code`, `product_ID`, `target_qty`)
        VALUES (%s, %s, %s, %s)
        """,
        data,
    )


def insert_monthly_plan_approved(cursor, catalog: list[dict], start_dt: datetime, end_dt: datetime, rows: int = 500) -> None:
    data = []
    for _ in range(rows):
        dt = random_day(start_dt, end_dt)
        product = random.choice(catalog)
        in_glass = random.randint(1000, 10000)
        in_panel = in_glass * product["cut_num"]
        out_glass = int(in_glass * random.uniform(0.85, 0.98))
        out_panel = out_glass * product["cut_num"]
        data.append(
            (
                dt.strftime("%Y-%m"),
                dt.strftime("%Y-%m-%d"),
                random.choice(FACTORIES),
                product["product_ID"],
                in_glass,
                in_panel,
                out_glass,
                out_panel,
            )
        )
    cursor.executemany(
        """
        INSERT INTO `monthly_plan_approved`
        (`plan_month`, `PLAN_date`, `factory_code`, `product_ID`, `target_IN_glass_qty`, `target_in_panel_qty`, `target_Out_glass_qty`, `target_Out_panel_qty`)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """,
        data,
    )


def insert_oms_inventory(cursor, catalog: list[dict], start_dt: datetime, end_dt: datetime, rows: int = 500) -> None:
    data = []
    for _ in range(rows):
        dt = random_day(start_dt, end_dt)
        product = random.choice(catalog)
        panel_qty = random.randint(1000, 40000)
        age_buckets = [random.randint(0, max(panel_qty // 4, 1)) for _ in range(8)]
        data.append(
            (
                dt.strftime("%Y-%m"),
                product["product_ID"],
                random.choice(SBU_LIST),
                random.choice(BU_LIST),
                random.choice(CUSTOMERS),
                random.choice(ERP_FACTORIES),
                random.choice(ERP_LOCATIONS),
                random.choice(["FG", "HUB", "TRANSIT"]),
                random.choice(["GOOD", "HOLD"]),
                random.choice(["A_CLASS", "B_CLASS"]),
                random.choice(GRADES),
                random.randint(100, 8000),
                panel_qty,
                *age_buckets,
            )
        )
    cursor.executemany(
        """
        INSERT INTO `oms_inventory`
        (`report_month`, `product_ID`, `SBU_DESC`, `BU_DESC`, `CUSTOMER`, `ERP_FACTORY`, `ERP_LOCATION`, `LGORT_DL`, `LGORT_LX`, `GRADE_FL`, `GRADE`, `glass_qty`, `panel_qty`, `ONE_AGE_panel_qty`, `TWO_AGE_panel_qty`, `THREE_AGE_panel_qty`, `FOUR_AGE_panel_qty`, `FIVE_AGE_panel_qty`, `SIX_AGE_panel_qty`, `SEVEN_AGE_panel_qty`, `EUGHT_AGE_panel_qty`)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        data,
    )


def insert_production_actuals(cursor, catalog: list[dict], start_dt: datetime, end_dt: datetime, rows: int = 800) -> None:
    data = []
    for _ in range(rows):
        dt = random_day(start_dt, end_dt)
        product = random.choice(catalog)
        act_type = random.choice(["IN", "OUT", "SCRAP"])
        gls_qty = random.randint(100, 2000)
        panel_qty = gls_qty * product["cut_num"]
        defect_qty = 0 if act_type != "SCRAP" else random.randint(1, max(gls_qty // 10, 1))
        data.append((dt.strftime("%Y-%m-%d"), random.choice(FACTORIES), product["product_ID"], act_type, gls_qty, panel_qty, defect_qty))
    cursor.executemany(
        """
        INSERT INTO `production_actuals`
        (`work_date`, `FACTORY`, `product_ID`, `act_type`, `GLS_qty`, `Panel_qty`, `defect_qty`)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        data,
    )


def insert_sales_financial_perf(cursor, catalog: list[dict], start_dt: datetime, end_dt: datetime, rows: int = 500) -> None:
    data = []
    for _ in range(rows):
        dt = random_day(start_dt, end_dt)
        product = random.choice(catalog)
        data.append(
            (
                dt.strftime("%Y-%m"),
                random.choice(SBU_LIST),
                random.choice(BU_LIST),
                random.choice(CUSTOMERS),
                product["FGCODE"],
                random.randint(500, 50000),
                random.randint(500, 50000),
            )
        )
    cursor.executemany(
        """
        INSERT INTO `sales_financial_perf`
        (`report_month`, `SBU_DESC`, `BU_DESC`, `CUSTOMER`, `FGCODE`, `sales_qty`, `FINANCIAL_qty`)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        data,
    )


def insert_weekly_rolling_plan(cursor, catalog: list[dict], start_dt: datetime, end_dt: datetime, rows: int = 500) -> None:
    data = []
    for _ in range(rows):
        dt = random_day(start_dt, end_dt)
        product = random.choice(catalog)
        data.append((random.choice(VERSION_POOL), dt.strftime("%Y-%m-%d"), random.choice(FACTORIES), product["product_ID"], random.randint(1000, 20000)))
    cursor.executemany(
        """
        INSERT INTO `weekly_rolling_plan`
        (`PM_VERSION`, `plan_date`, `factory`, `product_ID`, `plan_qty`)
        VALUES (%s, %s, %s, %s, %s)
        """,
        data,
    )


def run_db_insertion() -> None:
    print(f"[*] 正在连接 MySQL: {DB_CONFIG['host']}:{DB_CONFIG['port']} ...")
    conn = None
    cursor = None
    try:
        conn = pymysql.connect(**DB_CONFIG)
        cursor = conn.cursor()
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}` DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci")
        cursor.execute(f"USE `{DB_NAME}`")
        print(f"[*] 成功进入数据库: {DB_NAME}")

        for table_name in DROP_ORDER:
            cursor.execute(f"DROP TABLE IF EXISTS `{table_name}`")

        for table_name in DROP_ORDER[::-1]:
            print(f"[*] 创建表: {table_name}")
            cursor.execute(CREATE_SQL[table_name])

        end_dt = datetime.now()
        start_dt = end_dt - timedelta(days=180)
        catalog = build_product_catalog()

        print("[*] 写入 product_attributes ...")
        insert_product_attributes(cursor, catalog)
        print("[*] 写入 product_mapping ...")
        insert_product_mapping(cursor, catalog)
        print("[*] 写入 v_demand ...")
        insert_v_demand(cursor, catalog, start_dt, end_dt)
        print("[*] 写入 p_demand ...")
        insert_p_demand(cursor, catalog, start_dt, end_dt)
        print("[*] 写入 daily_inventory ...")
        insert_daily_inventory(cursor, catalog, start_dt, end_dt)
        print("[*] 写入 daily_PLAN ...")
        insert_daily_plan(cursor, catalog, start_dt, end_dt)
        print("[*] 写入 monthly_plan_approved ...")
        insert_monthly_plan_approved(cursor, catalog, start_dt, end_dt)
        print("[*] 写入 oms_inventory ...")
        insert_oms_inventory(cursor, catalog, start_dt, end_dt)
        print("[*] 写入 production_actuals ...")
        insert_production_actuals(cursor, catalog, start_dt, end_dt)
        print("[*] 写入 sales_financial_perf ...")
        insert_sales_financial_perf(cursor, catalog, start_dt, end_dt)
        print("[*] 写入 weekly_rolling_plan ...")
        insert_weekly_rolling_plan(cursor, catalog, start_dt, end_dt)

        conn.commit()
        print("[✔] 已同步创建并写入 11 张当前版本业务表。")
    except Exception as exc:
        if conn is not None and conn.open:
            conn.rollback()
        print(f"[X] 执行出现错误: {exc}")
        raise
    finally:
        if cursor is not None:
            cursor.close()
        if conn is not None and conn.open:
            conn.close()


if __name__ == "__main__":
    run_db_insertion()
