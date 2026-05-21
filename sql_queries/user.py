GET_USER_BY_ID = (
    "SELECT u.id, u.login, r.name as role_name "
    "FROM Users u JOIN Role r ON u.role_id = r.id WHERE u.id = %s;"
)

GET_USER_BY_ID_WITH_ROLE = """
SELECT u.id, u.login, u.role_id, r.name as role_name
FROM Users u
JOIN Role r ON u.role_id = r.id
WHERE u.id = %s;
"""
