GET_DASHBOARD_STATS = """
SELECT
    (SELECT COUNT(*) FROM Rent WHERE return_time IS NULL) AS active_rentals,
    (SELECT COUNT(*) FROM RentalRequest WHERE status = 'pending') AS pending_requests,
    (SELECT COUNT(*) FROM v_available_vessels) AS free_vessels,
    (SELECT COUNT(*) FROM Vessel) AS total_vessels;
"""

GET_ACTIVE_RENTALS = "SELECT * FROM v_current_rentals;"

GET_VESSELS_GROUPED = "SELECT * FROM v_vessels_full_info ORDER BY status_name, name;"

GET_ALL_REPAIR_LOGS = """
SELECT
    tcl.id, tcl.changed_at, tcl.vessel_id,
    v.name AS vessel_name,
    ttc.name AS condition_name
FROM Tech_condition_log tcl
JOIN Vessel v ON tcl.vessel_id = v.id
JOIN Type_tech_condition ttc ON tcl.type_condition_id = ttc.id
ORDER BY tcl.changed_at DESC;
"""

GET_REPAIR_LOGS = """
SELECT
    tcl.id,
    v.name AS vessel_name,
    v.number AS vessel_number,
    ttc.name AS condition_name,
    tcl.changed_at
FROM Tech_condition_log tcl
JOIN Vessel v ON tcl.vessel_id = v.id
JOIN Type_tech_condition ttc ON tcl.type_condition_id = ttc.id
ORDER BY tcl.changed_at DESC;
"""
