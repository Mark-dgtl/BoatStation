CHECK_CLIENT_ACTIVE_RENTAL = "SELECT id FROM Rent WHERE client_id = %s AND return_time IS NULL;"

# Пересечение с незакрытой арендой: конец периода — desired_end заявки или +24 ч от start_time.
CHECK_CLIENT_RENTAL_PERIOD_OVERLAP = """
SELECT r.id
FROM Rent r
LEFT JOIN RentalRequest rr ON r.request_id = rr.id
WHERE r.client_id = %s
  AND r.return_time IS NULL
  AND %s < COALESCE(rr.desired_end, r.start_time + interval '24 hours')
  AND %s > r.start_time
LIMIT 1;
"""

CHECK_VESSEL_AVAILABILITY = """
SELECT EXISTS (
    SELECT 1 FROM Rent
    WHERE vessel_id = %s
      AND return_time IS NOT NULL
      AND start_time < %s
      AND return_time > %s
) OR EXISTS (
    SELECT 1 FROM Rent
    WHERE vessel_id = %s
      AND return_time IS NULL
      AND start_time < %s
) AS is_taken;
"""

GET_INSTRUCTORS_WITH_PENDING_LOAD = """
SELECT
    i.id,
    i.surname,
    i.position,
    COUNT(rr.id) FILTER (WHERE rr.status = 'pending')::int AS pending_count
FROM Instructor i
LEFT JOIN Instruction ins ON ins.instructor_id = i.id
LEFT JOIN RentalRequest rr ON rr.instruction_id = ins.id AND rr.status = 'pending'
GROUP BY i.id, i.surname, i.position
ORDER BY i.surname;
"""

GET_INSTRUCTOR_BY_ID = "SELECT id FROM Instructor WHERE id = %s;"

GET_FIRST_INSTRUCTOR = "SELECT id FROM Instructor ORDER BY id LIMIT 1;"

GET_INSTRUCTION_BY_INSTRUCTOR = (
    "SELECT id FROM Instruction WHERE instructor_id = %s ORDER BY id LIMIT 1;"
)

INSERT_INSTRUCTION = """
INSERT INTO Instruction (instructor_id, type_instruction_id, time_conducted)
VALUES (%s, 1, NULL)
RETURNING id;
"""

MARK_INSTRUCTION_CONDUCTED = """
UPDATE Instruction
SET time_conducted = NOW()
WHERE id = %s AND instructor_id = %s
RETURNING id;
"""

GET_INSTRUCTION_BY_ID = "SELECT * FROM Instruction WHERE id = %s;"

GET_INSTRUCTIONS_FOR_INSTRUCTOR = """
SELECT * FROM Instruction
WHERE instructor_id = %s
ORDER BY time_conducted DESC, id DESC;
"""

GET_ALL_INSTRUCTIONS = """
SELECT
    i.id,
    i.time_conducted,
    ins.surname AS instructor_surname,
    ti.name AS type_instruction_name,
    c.id AS client_id,
    c.surname AS client_surname
FROM Instruction i
JOIN Instructor ins ON i.instructor_id = ins.id
JOIN Type_instruction ti ON i.type_instruction_id = ti.id
LEFT JOIN Rent r ON i.id = r.instruction_id
LEFT JOIN Client c ON r.client_id = c.id
ORDER BY i.id DESC;
"""

INSERT_RENT = """
INSERT INTO Rent (client_id, instruction_id, vessel_id, water_body_id, start_time, return_time)
VALUES (%s, %s, %s, %s, %s, %s)
RETURNING id, client_id, instruction_id, vessel_id, water_body_id, start_time, return_time;
"""

UPDATE_RENT_RETURN_TIME = """
UPDATE public.rent
SET return_time = %s
WHERE id = %s AND return_time IS NULL
RETURNING vessel_id
"""

SET_VESSEL_STATUS_FREE = "UPDATE public.vessel SET current_status_id = 1 WHERE id = %s"

SET_VESSEL_STATUS_RENTED = "UPDATE public.vessel SET current_status_id = 2 WHERE id = %s"

ACTIVE_RENTAL_BY_CLIENT_USER = (
    "SELECT id FROM Rent WHERE client_id = (SELECT id FROM Client WHERE user_id = %s) "
    "AND return_time IS NULL;"
)

CONDUCTED_INSTRUCTIONS_BY_USER = (
    "SELECT id FROM Instruction WHERE instructor_id = (SELECT id FROM Instructor WHERE user_id = %s);"
)
