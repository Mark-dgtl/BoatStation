GET_INSTRUCTOR_BY_USER_ID = """
SELECT i.id, i.surname, i.position, u.login
FROM Instructor i
JOIN Users u ON i.user_id = u.id
WHERE u.id = %s;
"""

GET_UPCOMING_INSTRUCTIONS = "SELECT * FROM v_upcoming_instructions WHERE instructor_id = %s;"

GET_CONDUCTED_INSTRUCTIONS = """
SELECT * FROM v_instructor_instructions
WHERE instructor_id = %s AND time_conducted IS NOT NULL;
"""

GET_INSTRUCTOR_DETAILS_BY_USER_ID = "SELECT surname, position FROM Instructor WHERE user_id = %s;"

DELETE_INSTRUCTOR_BY_USER_ID = "DELETE FROM Instructor WHERE user_id = %s;"
