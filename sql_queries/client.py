GET_CLIENT_BY_USER_ID = """
SELECT c.id, c.surname, c.address, c.passport, u.login
FROM Client c
JOIN Users u ON c.user_id = u.id
WHERE u.id = %s;
"""

UPDATE_CLIENT_PROFILE = """
UPDATE Client
SET surname = %s, address = %s, passport = %s
WHERE user_id = %s
RETURNING id, surname, address, passport;
"""

GET_RENTAL_HISTORY = "SELECT * FROM v_client_rental_history WHERE client_id = %s;"

GET_CURRENT_RENTAL = """
SELECT
    r.id, r.client_id, r.instruction_id, r.vessel_id, r.water_body_id,
    r.start_time, r.return_time,
    v.name AS vessel_name,
    tv.name AS vessel_type,
    wb.name AS water_body
FROM Rent r
JOIN Vessel v ON r.vessel_id = v.id
JOIN Type_vessel tv ON v.type_vessel_id = tv.id
JOIN Water_body wb ON r.water_body_id = wb.id
WHERE r.client_id = %s AND r.return_time IS NULL;
"""

GET_VESSELS_WITH_EQUIPMENT = """
SELECT
    vvi.id, vvi.name, vvi.number, vvi.type_name, vvi.status_name,
    COALESCE(array_agg(DISTINCT ve.rescue_equipment) FILTER (WHERE ve.rescue_equipment IS NOT NULL), '{}') AS equipment
FROM v_vessels_full_info vvi
LEFT JOIN v_vessel_equipment ve ON vvi.type_name = ve.vessel_type
GROUP BY vvi.id, vvi.name, vvi.number, vvi.type_name, vvi.status_name
ORDER BY vvi.name;
"""

GET_ALL_WATER_BODIES = "SELECT id, name FROM Water_body ORDER BY name;"

GET_WATER_BODIES_WITH_VESSEL_COUNT = """
SELECT wb.id, wb.name,
    (
        SELECT COUNT(*)::int
        FROM v_available_vessels av
        JOIN Vessel v ON av.id = v.id
        LEFT JOIN Swimming_danger sd
            ON v.type_vessel_id = sd.type_vessel_id AND sd.water_body_id = wb.id
        WHERE sd.is_dangerous IS DISTINCT FROM TRUE
    ) AS vessel_count
FROM Water_body wb
ORDER BY wb.name;
"""

GET_ALLOWED_WATER_BODIES_BY_VESSEL_TYPE = """
SELECT tv.name AS vessel_type, wb.id, wb.name
FROM Swimming_danger sd
JOIN Water_body wb ON sd.water_body_id = wb.id
JOIN Type_vessel tv ON sd.type_vessel_id = tv.id
WHERE sd.is_dangerous IS NOT TRUE
  AND NOT EXISTS (
    SELECT 1 FROM Swimming_danger sd2
    WHERE sd2.water_body_id = wb.id
      AND sd2.type_vessel_id = tv.id
      AND sd2.is_dangerous = TRUE
  )
GROUP BY tv.name, wb.id, wb.name
ORDER BY tv.name, wb.name;
"""

IS_VESSEL_WATER_BODY_ALLOWED = """
SELECT EXISTS (
    SELECT 1 FROM Swimming_danger sd
    WHERE sd.water_body_id = %s
      AND sd.type_vessel_id = (SELECT type_vessel_id FROM Vessel WHERE id = %s)
      AND sd.is_dangerous IS NOT TRUE
      AND NOT EXISTS (
        SELECT 1 FROM Swimming_danger sd2
        WHERE sd2.water_body_id = sd.water_body_id
          AND sd2.type_vessel_id = sd.type_vessel_id
          AND sd2.is_dangerous = TRUE
      )
) AS is_allowed;
"""

GET_AVAILABLE_VESSELS_FOR_WATER_BODY = """
SELECT
    av.id, av.name, av.number, av.type_name
FROM v_available_vessels av
JOIN Vessel v ON av.id = v.id
LEFT JOIN Swimming_danger sd ON v.type_vessel_id = sd.type_vessel_id AND sd.water_body_id = %s
WHERE sd.is_dangerous IS DISTINCT FROM TRUE;
"""

GET_RENTALS_BY_VESSEL_AND_DATE = """
SELECT start_time, return_time FROM Rent
WHERE vessel_id = %s AND DATE(start_time) = %s::DATE;
"""

GET_ALL_CLIENTS_FOR_FORM = """
SELECT c.id, c.surname, u.login
FROM Client c
JOIN Users u ON c.user_id = u.id
ORDER BY c.surname ASC;
"""

GET_CLIENT_DETAILS_BY_USER_ID = "SELECT surname, address, passport FROM Client WHERE user_id = %s;"

DELETE_CLIENT_BY_USER_ID = "DELETE FROM Client WHERE user_id = %s;"
