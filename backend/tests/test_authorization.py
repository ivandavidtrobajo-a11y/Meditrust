"""Unit tests for Meditrust role and patient-access authorization.

Run from the backend directory with:
    python -m unittest discover -s tests -v
"""
import unittest
from fastapi import HTTPException

from services.authorization import (
    require_active_patient_assignment,
    require_active_user,
    require_patient_access,
    require_role,
)


class FakeCollection:
    def __init__(self, result=None):
        self.result = result
        self.last_query = None

    def find_one(self, query, projection=None):
        self.last_query = query
        return self.result


class FakeDatabase:
    def __init__(self, assignment=None):
        self.collections = {
            "doctor_patient_assignments": FakeCollection(assignment)
        }

    def __getitem__(self, name):
        return self.collections[name]


class AuthorizationTests(unittest.TestCase):
    def test_role_is_normalized_before_comparison(self):
        user = {"role": "  MEDICO  "}
        self.assertIs(require_role(user, "medico"), user)

    def test_role_outside_allowlist_is_forbidden(self):
        with self.assertRaises(HTTPException) as raised:
            require_role({"role": "admin"}, "medico")
        self.assertEqual(raised.exception.status_code, 403)

    def test_unknown_role_is_forbidden(self):
        with self.assertRaises(HTTPException) as raised:
            require_role({"role": "superuser"}, "superuser")
        self.assertEqual(raised.exception.status_code, 403)

    def test_patient_can_access_own_records(self):
        patient = {"_id": "patient-1", "role": "embarazada"}
        self.assertIs(require_patient_access(patient, "patient-1"), patient)

    def test_patient_cannot_access_another_patients_records(self):
        with self.assertRaises(HTTPException) as raised:
            require_patient_access(
                {"_id": "patient-1", "role": "embarazada"},
                "patient-2",
            )
        self.assertEqual(raised.exception.status_code, 403)

    def test_doctor_can_access_patient_with_active_assignment(self):
        doctor = {"_id": "doctor-1", "role": "medico"}
        database = FakeDatabase({"status": "active"})
        self.assertIs(
            require_patient_access(doctor, "patient-1", database),
            doctor,
        )
        self.assertEqual(
            database["doctor_patient_assignments"].last_query["doctor_id"],
            "doctor-1",
        )

    def test_doctor_cannot_access_patient_without_assignment(self):
        with self.assertRaises(HTTPException) as raised:
            require_patient_access(
                {"_id": "doctor-1", "role": "medico"},
                "patient-1",
                FakeDatabase(),
            )
        self.assertEqual(raised.exception.status_code, 403)

    def test_admin_cannot_access_patient_clinical_records(self):
        with self.assertRaises(HTTPException) as raised:
            require_patient_access(
                {"_id": "admin-1", "role": "admin"},
                "patient-1",
                FakeDatabase({"status": "active"}),
            )
        self.assertEqual(raised.exception.status_code, 403)

    def test_inactive_user_is_forbidden(self):
        with self.assertRaises(HTTPException) as raised:
            require_active_user({"is_active": False})
        self.assertEqual(raised.exception.status_code, 403)

    def test_legacy_user_without_active_flag_remains_active(self):
        user = {"role": "medico"}
        self.assertIs(require_active_user(user), user)

    def test_patient_upload_requires_active_assignment(self):
        database = FakeDatabase({"status": "active"})
        self.assertIsNone(
            require_active_patient_assignment("patient-1", database)
        )

    def test_patient_upload_is_denied_without_active_assignment(self):
        with self.assertRaises(HTTPException) as raised:
            require_active_patient_assignment("patient-1", FakeDatabase())
        self.assertEqual(raised.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main()
