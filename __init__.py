"""
SQLAlchemy model registry.
Only model imports belong here.
"""

from .account_group import AccountGroup
from .accounting_period import AccountingPeriod
from .academic_year import AcademicYear
from .asset_acquisition import AssetAcquisition
from .asset_category import AssetCategory
from .asset_custodian import AssetCustodian
from .asset_depreciation_line import AssetDepreciationLine
from .asset_depreciation_run import AssetDepreciationRun
from .asset_disposal import AssetDisposal
from .asset_location import AssetLocation
from .asset_maintenance import AssetMaintenance
from .branch import Branch
from .cash_payment import CashPayment
from .cash_payment_line import CashPaymentLine
from .cash_receipt import CashReceipt
from .cash_receipt_line import CashReceiptLine
from .fee_item import FeeItem
from .fee_structure import FeeStructure
from .fee_structure_line import FeeStructureLine
from .fiscal_year import FiscalYear
from .fixed_asset import FixedAsset
from .gl_account import GLAccount
from .intake import Intake
from .journal_batch import JournalBatch
from .journal_line import JournalLine
from .payer import Payer
from .payer_type import PayerType
from .program import Program
from .role import Role
from .semester import Semester
from .student import Student
from .student_credit_note import StudentCreditNote
from .student_ecl_line import StudentECLLine
from .student_ecl_run import StudentECLRun
from .student_enrollment import StudentEnrollment
from .student_invoice import StudentInvoice
from .student_invoice_line import StudentInvoiceLine
from .student_payment import StudentPayment
from .student_payment_allocation import StudentPaymentAllocation
from .student_refund import StudentRefund
from .student_revenue_recognition_line import StudentRevenueRecognitionLine
from .student_revenue_recognition_run import StudentRevenueRecognitionRun
from .student_waiver import StudentWaiver
from .supplier import Supplier
from .supplier_category import SupplierCategory
from .user import User
from .nhif_claim_batch import NHIFClaimBatch
from .nhif_claim import NHIFClaim
from .nhif_collection import NHIFCollection
from .nhif_rejection import NHIFRejection
from .nhif_import_batch import NHIFImportBatch
from .nhif_claim_batch import NHIFClaimBatch
from .nhif_claim import NHIFClaim
from .nhif_collection import NHIFCollection
from .nhif_rejection import NHIFRejection


try:
    from .audit_log import AuditLog  # noqa: F401
except Exception:
    AuditLog = None

try:
    from .year_end_closing import YearEndClosing  # noqa: F401
except Exception:
    YearEndClosing = None
