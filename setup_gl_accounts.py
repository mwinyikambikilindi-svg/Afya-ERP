from sqlalchemy import text
from app import create_app
import app.extensions as ext

app = create_app()

data = [
    # CURRENT ASSETS - group 1100
    ("1100", "1110", "Cash on Hand", True, False, False),
    ("1100", "1120", "Bank - Operating Account", True, False, False),
    ("1100", "1130", "Petty Cash", True, False, False),
    ("1100", "1210", "NHIF Receivable", False, True, True),
    ("1100", "1220", "CHIF/ZHIF Receivable", False, True, True),
    ("1100", "1230", "Student Fees Receivable", False, True, True),
    ("1100", "1240", "Other Receivables", False, True, True),
    ("1100", "1310", "Drugs Inventory", False, True, True),
    ("1100", "1320", "Medical Supplies Inventory", False, True, True),
    ("1100", "1330", "Medical Reagents Inventory", False, True, True),
    ("1100", "1410", "Prepayments", True, False, False),

    # NON CURRENT ASSETS - group 1200
    ("1200", "1510", "Buildings", True, False, False),
    ("1200", "1520", "Medical Equipment", True, False, False),
    ("1200", "1530", "Furniture and Fittings", True, False, False),
    ("1200", "1540", "Motor Vehicles", True, False, False),
    ("1200", "1590", "Accumulated Depreciation", False, False, True),

    # CURRENT LIABILITIES - group 2100
    ("2100", "2110", "Trade Payables", False, True, True),
    ("2100", "2120", "Accrued Expenses", True, False, False),
    ("2100", "2130", "Payroll Payable", True, False, False),
    ("2100", "2140", "Statutory Payables", True, False, False),

    # EQUITY - group 3100
    ("3100", "3110", "Capital Fund", True, False, False),
    ("3100", "3120", "Retained Surplus", True, False, False),

    # OPERATING INCOME - group 4100
    ("4100", "4110", "Government Grants Income", True, False, False),
    ("4100", "4120", "User Fees - Cash Income", True, False, False),
    ("4100", "4130", "NHIF Revenue", True, False, False),
    ("4100", "4140", "CHIF/ZHIF Revenue", True, False, False),
    ("4100", "4150", "Church Contributions Income", True, False, False),
    ("4100", "4160", "College Fees Income", True, False, False),
    ("4100", "4170", "Medical Examination Fees Income", True, False, False),
    ("4100", "4180", "Mortuary Fees Income", True, False, False),
    ("4100", "4190", "Community Pharmacy Profit Share", True, False, False),

    # NON OPERATING INCOME - group 4200
    ("4200", "4210", "Bank Interest Income", True, False, False),

    # DIRECT COSTS - group 5100
    ("5100", "5110", "Drugs Expense", True, False, False),
    ("5100", "5120", "Medical Supplies Expense", True, False, False),
    ("5100", "5130", "Medical Reagents Expense", True, False, False),

    # ADMINISTRATIVE EXPENSES - group 5200
    ("5200", "5210", "Salaries and Wages", True, False, False),
    ("5200", "5220", "Staff Incentives", True, False, False),
    ("5200", "5230", "Staff Treatment Expense", True, False, False),
    ("5200", "5240", "Utilities Expense", True, False, False),
    ("5200", "5250", "Repairs and Maintenance", True, False, False),
    ("5200", "5260", "Office Consumables Expense", True, False, False),

    # FINANCE AND OTHER EXPENSES - group 5300
    ("5300", "5310", "Bank Charges Expense", True, False, False),
    ("5300", "5320", "Depreciation Expense", False, False, True),
    ("5300", "5330", "Expected Credit Loss Expense", False, False, True),
]

sql = text("""
    INSERT INTO gl_accounts (
        account_group_id,
        parent_id,
        code,
        name,
        account_type,
        allow_manual_posting,
        requires_subledger,
        requires_cost_center,
        requires_department,
        is_control_account,
        is_active
    )
    VALUES (
        (SELECT id FROM account_groups WHERE code = :group_code),
        NULL,
        :code,
        :name,
        'posting',
        :allow_manual_posting,
        :requires_subledger,
        FALSE,
        FALSE,
        :is_control_account,
        TRUE
    )
    ON CONFLICT (code) DO NOTHING
""")

with app.app_context():
    with ext.engine.connect() as conn:
        for group_code, code, name, allow_manual_posting, requires_subledger, is_control_account in data:
            conn.execute(
                sql,
                {
                    "group_code": group_code,
                    "code": code,
                    "name": name,
                    "allow_manual_posting": allow_manual_posting,
                    "requires_subledger": requires_subledger,
                    "is_control_account": is_control_account,
                }
            )
        conn.commit()

print("GL accounts inserted successfully.")