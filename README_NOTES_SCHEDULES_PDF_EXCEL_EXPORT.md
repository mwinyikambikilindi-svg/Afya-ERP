# Notes Schedules + PDF/Excel Export Pack

This pack adds:
1. Notes schedules service helpers
2. Notes detail routes
3. Export hooks for Excel and printable HTML/PDF-ready views
4. Buttons/links on report pages for export actions

## Important
This pack is designed to sit on top of the existing `/reports/...` suite.

## What is included
- enhanced reporting service with note schedule functions
- report routes with:
  - notes detail pages
  - excel export endpoints
  - print-ready endpoints
- templates for:
  - notes landing page
  - note detail page
  - printable statement views

## Export strategy in this pack
- Excel export: returns `.xlsx` generated from report data
- PDF path: provided as print-ready HTML view for now, to preserve layout discipline safely.
  You can later add wkhtmltopdf / WeasyPrint if desired.

## Recommended next phase
- note-by-note PMU custom layouts
- official PDF styling matching your exact financial statement
