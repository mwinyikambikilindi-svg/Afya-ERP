ENTERPRISE SHELL PACK

This pack changes the UI direction to a MUSE-inspired enterprise shell:
- Government-style top banner
- Dense left sidebar with icons
- Compact forms and buttons
- Workspace-style content frame
- Popup mini-windows (modal entry) for key forms

Files included:
- app/templates/base.html
- app/static/css/app.css
- app/static/js/app_ui.js
- app/templates/dashboard.html
- app/templates/manual_journal_form.html
- app/templates/cash_receipt_form.html
- app/templates/cash_payment_form.html
- app/templates/student_setup.html
- app/templates/fixed_assets.html

How to use:
1. Backup your current app/templates and app/static folders.
2. Replace the files above with the pack versions.
3. Run python run.py
4. Review:
   - /
   - /manual-journal
   - /cash-receipts/new
   - /cash-payments/new
   - /students
   - /fixed-assets

Notes:
- The shell applies globally through base.html and app.css.
- The popup mini-window behavior is implemented on the five highest-traffic entry screens in this pack.
- Other templates will inherit the new enterprise shell immediately even if they remain full-page for now.
