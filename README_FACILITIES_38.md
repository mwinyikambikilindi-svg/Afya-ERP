# Facilities 38 Full Pack

This pack adds:
1. PMU facilities master CSV (38 facilities)
2. Facility management service
3. Facility routes for list / add / edit / delete
4. Simple templates for facility management

## Suggested sidebar link
- `/facilities`

## Important
- This pack assumes your `facilities` table already exists.
- It works with common columns:
  - `id`
  - `facility_id` OR `code`
  - `name`
  - optional: `facility_type`, `region`, `district`, `is_active`
- The service is schema-aware where possible.

## Routes
- `/facilities`
- `/facilities/new`
- `/facilities/<int:facility_pk>/edit`
- `/facilities/<int:facility_pk>/delete`
- `/facilities/seed-pmu-38`
