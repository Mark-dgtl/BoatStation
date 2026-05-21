RENTAL_REQUEST_ENRICHED_FROM = """
FROM RentalRequest rr
JOIN Client c ON rr.client_id = c.id
JOIN Vessel v ON rr.vessel_id = v.id
JOIN Type_vessel tv ON v.type_vessel_id = tv.id
JOIN Water_body wb ON rr.water_body_id = wb.id
LEFT JOIN Instruction i ON rr.instruction_id = i.id
LEFT JOIN Instructor inst ON i.instructor_id = inst.id
"""

RENTAL_REQUEST_ENRICHED_SELECT = """
SELECT
    rr.*,
    c.surname AS client_surname,
    v.name AS vessel_name,
    v.number AS vessel_number,
    tv.name AS type_name,
    wb.name AS water_body_name,
    inst.id AS assigned_instructor_id,
    inst.surname AS instructor_surname
""" + RENTAL_REQUEST_ENRICHED_FROM

PENDING_BY_CLIENT = (
    RENTAL_REQUEST_ENRICHED_SELECT
    + " WHERE rr.client_id = %s AND rr.status = 'pending' ORDER BY rr.desired_start;"
)

PENDING_ALL = (
    RENTAL_REQUEST_ENRICHED_SELECT
    + " WHERE rr.status IN ('pending', 'instructor_confirmed') ORDER BY rr.desired_start;"
)

BY_INSTRUCTOR_USER_PENDING = (
    RENTAL_REQUEST_ENRICHED_SELECT
    + """
WHERE inst.user_id = %s AND rr.status = 'pending'
ORDER BY rr.desired_start;
"""
)

GET_BY_ID = "SELECT * FROM RentalRequest WHERE id = %s;"

GET_RENT_BY_REQUEST_ID = "SELECT * FROM Rent WHERE request_id = %s;"

UPDATE_STATUS = "UPDATE RentalRequest SET status = %s WHERE id = %s RETURNING *;"

CREATE = """
INSERT INTO RentalRequest (client_id, vessel_id, water_body_id, desired_start, desired_end, status)
VALUES (%s, %s, %s, %s, %s, 'pending')
RETURNING id, client_id, vessel_id, water_body_id, instruction_id, desired_start, desired_end, status, created_at;
"""

CONFIRM_BY_INSTRUCTOR = """
UPDATE RentalRequest SET status = 'instructor_confirmed'
WHERE id = %s AND status = 'pending'
RETURNING *;
"""

FOR_INSTRUCTOR = """
SELECT rr.* FROM RentalRequest rr
JOIN Instruction i ON rr.instruction_id = i.id
WHERE rr.id = %s AND i.instructor_id = %s AND rr.status = 'pending';
"""

UPDATE_INSTRUCTION_ID = "UPDATE RentalRequest SET instruction_id = %s WHERE id = %s;"

ACTIVE_REQUESTS_BY_USER = (
    "SELECT id FROM RentalRequest WHERE client_id = (SELECT id FROM Client WHERE user_id = %s) "
    "AND status IN ('pending', 'instructor_confirmed');"
)
