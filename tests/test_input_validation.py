from __future__ import annotations

import unittest

from pydantic import ValidationError

from app.schemas.auth import LoginRequest, PasswordResetRequest, RegisterRequest, UserRoleUpdateRequest
from app.schemas.chat import CancelRunRequest, SendMessageRequest


class InputValidationTestCase(unittest.TestCase):
    def test_register_requires_min_username_length(self):
        with self.assertRaises(ValidationError):
            RegisterRequest(username='ab', password='12345678')

    def test_login_requires_min_password_length(self):
        with self.assertRaises(ValidationError):
            LoginRequest(username='validuser', password='123')

    def test_password_reset_requires_strong_length(self):
        with self.assertRaises(ValidationError):
            PasswordResetRequest(new_password='short')

    def test_send_message_rejects_blank_question(self):
        with self.assertRaises(ValidationError):
            SendMessageRequest(question='   ')

    def test_cancel_run_rejects_blank_run_id(self):
        with self.assertRaises(ValidationError):
            CancelRunRequest(run_id='  ')

    def test_roles_must_not_be_empty(self):
        with self.assertRaises(ValidationError):
            UserRoleUpdateRequest(roles=[])


if __name__ == '__main__':
    unittest.main()
