from __future__ import annotations

import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import Message, Run, Thread, Turn, User
from app.services.run_service import RunService


class RunServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine('sqlite:///:memory:')
        Base.metadata.create_all(bind=self.engine)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self.db = self.SessionLocal()
        self.run_service = RunService()

        user = User(username='tester', password_hash='hashed')
        self.db.add(user)
        self.db.flush()

        self.thread = Thread(owner_id=user.id, title='新对话')
        self.db.add(self.thread)
        self.db.flush()

        user_message = Message(thread_id=self.thread.id, role='user', content='原问题')
        self.db.add(user_message)
        self.db.flush()

        self.turn = Turn(thread_id=self.thread.id, sequence=1, status='completed', user_message_id=user_message.id)
        self.db.add(self.turn)
        self.db.flush()

        user_message.turn_id = self.turn.id

        self.original_assistant = Message(thread_id=self.thread.id, turn_id=self.turn.id, role='assistant', content='原答案')
        self.db.add(self.original_assistant)
        self.db.flush()

        self.turn.latest_assistant_message_id = self.original_assistant.id
        self.db.commit()

    def tearDown(self) -> None:
        self.db.close()
        self.engine.dispose()

    def test_regenerate_start_keeps_original_assistant_message(self):
        turn, run = self.run_service.start_regenerate_run(self.db, self.thread, self.original_assistant.id)

        self.assertIsNotNone(run)
        self.assertEqual(turn.id, self.turn.id)
        self.assertEqual(turn.status, 'pending')

        preserved = self.db.query(Message).filter(Message.id == self.original_assistant.id).first()
        self.assertIsNotNone(preserved)
        self.assertEqual(turn.latest_assistant_message_id, self.original_assistant.id)

    def test_complete_run_replaces_previous_assistant_message(self):
        turn, run = self.run_service.start_regenerate_run(self.db, self.thread, self.original_assistant.id)

        new_assistant = self.run_service.complete_run(self.db, run, turn, '新答案', {'route': {'route': 'inventory'}})

        self.assertEqual(turn.latest_assistant_message_id, new_assistant.id)
        old_message = self.db.query(Message).filter(Message.id == self.original_assistant.id).first()
        self.assertIsNone(old_message)

        assistants = self.db.query(Message).filter(Message.turn_id == turn.id, Message.role == 'assistant').all()
        self.assertEqual(len(assistants), 1)
        self.assertEqual(assistants[0].content, '新答案')

    def test_fail_run_preserves_completed_turn_when_previous_answer_exists(self):
        run = Run(thread_id=self.thread.id, turn_id=self.turn.id, kind='regenerate', status='running')
        self.db.add(run)
        self.db.flush()

        self.run_service.fail_run(self.db, run, self.turn, 'workflow failed')

        self.assertEqual(run.status, 'failed')
        self.assertEqual(self.turn.status, 'completed')

    def test_cancel_run_preserves_completed_turn_when_previous_answer_exists(self):
        run = Run(thread_id=self.thread.id, turn_id=self.turn.id, kind='regenerate', status='running')
        self.db.add(run)
        self.db.flush()

        self.run_service.cancel_run(self.db, run, self.turn)

        self.assertEqual(run.status, 'cancelled')
        self.assertEqual(self.turn.status, 'completed')


if __name__ == '__main__':
    unittest.main()
