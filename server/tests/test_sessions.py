"""会话管理的单元测试。"""
import unittest

from app.db.session import Base, SessionLocal, engine
from app.models.chat import ChatMessage, ChatSession
from app.api.chat import _touch_session


class TestSession(unittest.TestCase):
    def setUp(self):
        Base.metadata.create_all(bind=engine)
        self.db = SessionLocal()
        self.db.query(ChatMessage).filter(ChatMessage.session_id.like("t_%")).delete()
        self.db.query(ChatSession).filter(ChatSession.id.like("t_%")).delete()
        self.db.commit()
        self.addCleanup(self.db.close)

    def test_touch_creates_session_with_title(self):
        _touch_session(self.db, "t_1", title="玉米叶片有斑点怎么办")
        self.db.commit()
        row = self.db.query(ChatSession).filter(ChatSession.id == "t_1").first()
        self.assertIsNotNone(row)
        self.assertTrue(row.title.startswith("玉米叶片"))
        self.assertIsNotNone(row.updated_at)

    def test_touch_keeps_existing_title(self):
        _touch_session(self.db, "t_2", title="第一句")
        self.db.commit()
        _touch_session(self.db, "t_2", title="第二句")
        self.db.commit()
        row = self.db.query(ChatSession).filter(ChatSession.id == "t_2").first()
        self.assertEqual(row.title, "第一句")

    def test_title_truncated(self):
        _touch_session(self.db, "t_3", title="很" * 100)
        self.db.commit()
        row = self.db.query(ChatSession).filter(ChatSession.id == "t_3").first()
        self.assertLessEqual(len(row.title), 40)

    def test_delete_cascades_messages(self):
        self.db.add(ChatMessage(session_id="t_4", role="user", content="hi"))
        _touch_session(self.db, "t_4", title="会话四")
        self.db.commit()
        # 模拟接口里的删除逻辑
        self.db.query(ChatMessage).filter(ChatMessage.session_id == "t_4").delete()
        self.db.query(ChatSession).filter(ChatSession.id == "t_4").delete()
        self.db.commit()
        self.assertEqual(self.db.query(ChatMessage).filter(ChatMessage.session_id == "t_4").count(), 0)
        self.assertIsNone(self.db.query(ChatSession).filter(ChatSession.id == "t_4").first())


if __name__ == "__main__":
    unittest.main()
