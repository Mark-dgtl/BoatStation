AUTHENTICATE_USER = (
    "SELECT u.id, u.login, r.name as role_name "
    "FROM Users u JOIN Role r ON u.role_id = r.id "
    "WHERE u.login = %s AND u.password_hash = %s"
)

GET_USER_BY_LOGIN = "SELECT id, login, role_id FROM Users WHERE login = %s"

GET_CLIENT_ROLE_ID = "SELECT id FROM Role WHERE name = 'client'"

INSERT_USER = """
INSERT INTO Users (login, password_hash, role_id)
VALUES (%s, %s, %s)
RETURNING id
"""

INSERT_CLIENT = """
INSERT INTO Client (surname, address, passport, user_id)
VALUES (%s, %s, %s, %s)
RETURNING id, surname, address, passport, user_id
"""
