from datetime import date
from app import create_app
from app.services.journal_service import create_journal_draft, post_journal

app = create_app()

with app.app_context():
    batch_id = create_journal_draft(
        branch_id=1,  # BADILI na branch_id yako halisi
        journal_date=date.today(),
        source_module="MANUAL_JOURNAL",
        reference_no="MJ-001",
        narration="First real manual journal",
        lines=[
            {
                "gl_account_id": 2,  # BADILI na account id halisi ya debit
                "description": "Debit line",
                "debit_amount": 1000.00,
                "credit_amount": 0.00,
            },
            {
                "gl_account_id": 22,  # BADILI na account id halisi ya credit
                "description": "Credit line",
                "debit_amount": 0.00,
                "credit_amount": 1000.00,
            },
        ],
    )

    post_journal(batch_id)
    print(f"Journal posted successfully. Batch ID: {batch_id}")