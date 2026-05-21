GET_ALL_VESSELS = "SELECT * FROM v_vessels_full_info ORDER BY name;"

GET_VESSEL_BY_ID = """
SELECT v.*,
       tv.name AS type_name,
       tsv.name AS status_name
FROM Vessel v
JOIN Type_vessel tv ON v.type_vessel_id = tv.id
JOIN Type_status_vessel tsv ON v.current_status_id = tsv.id
WHERE v.id = %s;
"""

GET_VESSEL_EXISTS = "SELECT id FROM Vessel WHERE id = %s;"

GET_VESSEL_BY_NUMBER_EXCLUDING = """
SELECT id FROM Vessel
WHERE number = %s AND id != %s;
"""

GET_VESSEL_BY_NUMBER = "SELECT id FROM Vessel WHERE number = %s;"

GET_ALL_VESSEL_TYPES = "SELECT id, name FROM Type_vessel ORDER BY name;"

GET_ALL_VESSEL_STATUSES = "SELECT id, name FROM Type_status_vessel ORDER BY name;"

INSERT_VESSEL = """
INSERT INTO Vessel (name, number, type_vessel_id, current_status_id)
VALUES (%s, %s, %s, %s)
RETURNING *;
"""
