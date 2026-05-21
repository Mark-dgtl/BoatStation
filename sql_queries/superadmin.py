GET_DASHBOARD_STATS = """
SELECT
    (SELECT COUNT(*) FROM Client) AS total_clients,
    (SELECT COUNT(*) FROM Instructor) AS total_instructors,
    (SELECT COUNT(*) FROM Administrator) AS total_admins,
    (SELECT COUNT(*) FROM Users) AS total_users,
    (SELECT COUNT(*) FROM Vessel) AS total_vessels,
    (SELECT COUNT(*) FROM Rent WHERE return_time IS NULL) AS active_rentals,
    (SELECT COUNT(*) FROM RentalRequest WHERE status = 'pending') AS pending_requests,
    (SELECT COUNT(*) FROM RentalRequest WHERE status = 'instructor_confirmed') AS awaiting_admin;
"""

GET_ALL_USERS = """
SELECT u.id, u.login, r.name as role_name,
       COALESCE(c.surname, i.surname, a.user_id::TEXT) as display_name
FROM Users u
JOIN Role r ON u.role_id = r.id
LEFT JOIN Client c ON u.id = c.user_id
LEFT JOIN Instructor i ON u.id = i.user_id
LEFT JOIN Administrator a ON u.id = a.user_id
ORDER BY u.login;
"""

GET_ROLE_ID_BY_NAME = "SELECT id FROM Role WHERE name = %s;"

UPDATE_USER_ROLE = "UPDATE Users SET role_id = %s WHERE id = %s;"

GET_ADMIN_BY_USER_ID = "SELECT user_id FROM Administrator WHERE user_id = %s;"

DELETE_ADMIN_BY_USER_ID = "DELETE FROM Administrator WHERE user_id = %s;"

DELETE_USER_BY_ID = "DELETE FROM Users WHERE id = %s;"
