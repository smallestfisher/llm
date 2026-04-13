import unittest
from fastapi.testclient import TestClient

from app import app
from core.auth_db import SessionLocal, User, ChatThread, append_chat_message, create_user


class ThreadDeleteRouteTestCase(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.db = SessionLocal()
        self.db.query(ChatThread).delete()
        self.db.query(User).delete()
        self.db.commit()

        self.user = create_user(self.db, "thread-delete-user", "password123", role_names=["user"])
        self.thread1 = ChatThread(owner_id=self.user.id, title="线程一")
        self.thread2 = ChatThread(owner_id=self.user.id, title="线程二")
        self.db.add_all([self.thread1, self.thread2])
        self.db.flush()
        append_chat_message(self.db, self.thread1, "user", "你好")
        append_chat_message(self.db, self.thread1, "assistant", "世界")
        self.db.commit()

        login_response = self.client.post(
            "/login",
            data={"username": "thread-delete-user", "password": "password123"},
            follow_redirects=False,
        )
        self.assertEqual(login_response.status_code, 303)

    def tearDown(self):
        self.db.close()

    def test_delete_thread_removes_messages_and_redirects(self):
        response = self.client.post(f"/threads/{self.thread1.public_id}/delete", follow_redirects=False)

        self.assertEqual(response.status_code, 303)
        self.assertEqual(response.headers["location"], f"/threads/{self.thread2.public_id}")

        db = SessionLocal()
        try:
            deleted_thread = db.query(ChatThread).filter(ChatThread.public_id == self.thread1.public_id).first()
            remaining_thread = db.query(ChatThread).filter(ChatThread.public_id == self.thread2.public_id).first()
            self.assertIsNone(deleted_thread)
            self.assertIsNotNone(remaining_thread)
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
