"""Unit tests for Meditrust role and patient-access authorization.

Run from the backend directory with:
    python -m unittest discover -s tests -v
"""
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from fastapi import FastAPI, HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.testclient import TestClient

from services.auth_service import get_user_by_id
from services.clinical_workflow import router as clinical_workflow_router
from services.authorization import (
    get_current_user,
    normalize_role,
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

    def test_missing_role_does_not_default_to_patient(self):
        self.assertEqual(normalize_role(None), "")
        self.assertEqual(normalize_role("   "), "")

    def test_role_outside_allowlist_is_forbidden(self):
        with self.assertRaises(HTTPException) as raised:
            require_role({"role": "admin"}, "medico")
        self.assertEqual(raised.exception.status_code, 403)

    def test_unknown_role_is_forbidden(self):
        with self.assertRaises(HTTPException) as raised:
            require_role({"role": "superuser"}, "superuser")
        self.assertEqual(raised.exception.status_code, 403)

    def test_missing_role_is_forbidden(self):
        with self.assertRaises(HTTPException) as raised:
            require_role({}, "embarazada")
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
        query = database["doctor_patient_assignments"].last_query
        self.assertEqual(query["doctor_id"], "doctor-1")
        self.assertEqual(
            query["$or"][1],
            {"status": {"$exists": False}, "active": True},
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

    def test_missing_bearer_credentials_returns_401(self):
        with self.assertRaises(HTTPException) as raised:
            get_current_user(None)
        self.assertEqual(raised.exception.status_code, 401)

    def test_non_dictionary_token_payload_returns_401(self):
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials="token"
        )
        with patch("services.authorization.decode_token", return_value=["bad"]):
            with self.assertRaises(HTTPException) as raised:
                get_current_user(credentials)
        self.assertEqual(raised.exception.status_code, 401)

    def test_token_without_user_id_returns_401(self):
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials="token"
        )
        with patch("services.authorization.decode_token", return_value={"role": "admin"}):
            with self.assertRaises(HTTPException) as raised:
                get_current_user(credentials)
        self.assertEqual(raised.exception.status_code, 401)

    def test_invalid_mongodb_id_is_treated_as_not_found(self):
        with patch("services.auth_service.get_db") as get_db:
            self.assertIsNone(get_user_by_id("not-an-object-id"))
            get_db.assert_not_called()

    def test_authenticated_user_with_unknown_role_is_forbidden(self):
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials="token"
        )
        with patch("services.authorization.decode_token", return_value={"id": "507f1f77bcf86cd799439011"}), patch(
            "services.authorization.get_user_by_id",
            return_value={"_id": "507f1f77bcf86cd799439011", "role": "superuser"},
        ):
            with self.assertRaises(HTTPException) as raised:
                get_current_user(credentials)
        self.assertEqual(raised.exception.status_code, 403)

    def test_authenticated_user_receives_normalized_role(self):
        credentials = HTTPAuthorizationCredentials(
            scheme="Bearer", credentials="token"
        )
        user = {"_id": "507f1f77bcf86cd799439011", "role": " MEDICO "}
        with patch("services.authorization.decode_token", return_value={"id": "507f1f77bcf86cd799439011"}), patch(
            "services.authorization.get_user_by_id", return_value=user
        ):
            result = get_current_user(credentials)
        self.assertEqual(result["role"], "medico")




class ClinicalRoutePermissionTests(unittest.TestCase):
    def _client_for(self, role):
        app = FastAPI()
        app.include_router(clinical_workflow_router)
        app.dependency_overrides[get_current_user] = lambda: {
            "_id": "507f1f77bcf86cd799439011",
            "role": role,
        }
        return TestClient(app)

    def test_patient_cannot_create_doctor_linking_code(self):
        response = self._client_for("embarazada").post("/doctor/linking-codes")
        self.assertEqual(response.status_code, 403)

    def test_doctor_cannot_redeem_patient_linking_code(self):
        response = self._client_for("medico").post(
            "/patient/link", json={"code": "ABC234"}
        )
        self.assertEqual(response.status_code, 403)

    def test_patient_cannot_list_doctor_patients(self):
        response = self._client_for("embarazada").get("/doctor/patients")
        self.assertEqual(response.status_code, 403)

    def test_doctor_cannot_list_patient_relationships(self):
        response = self._client_for("medico").get("/patient/relationships")
        self.assertEqual(response.status_code, 403)

    def test_admin_cannot_access_doctor_patient_workflow(self):
        response = self._client_for("admin").get("/doctor/patients")
        self.assertEqual(response.status_code, 403)

    def test_missing_token_is_401_at_clinical_api_boundary(self):
        app = FastAPI()
        app.include_router(clinical_workflow_router)
        response = TestClient(app).get("/doctor/patients")
        self.assertEqual(response.status_code, 401)

    def test_doctor_cannot_read_unassigned_patient_detail(self):
        client = self._client_for("medico")
        database = SimpleNamespace(doctor_patient_assignments=FakeCollection())
        with patch("services.clinical_workflow.get_db", return_value=database):
            response = client.get("/doctor/patients/507f1f77bcf86cd799439012")
        self.assertEqual(response.status_code, 403)

if __name__ == "__main__":
    unittest.main()
