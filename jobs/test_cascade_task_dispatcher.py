import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from jobs.cascade_task_dispatcher import CascadeTaskDispatcher


class CascadeTaskDispatcherTests(unittest.TestCase):
    @patch.object(CascadeTaskDispatcher, "notify_children_new_task")
    @patch.object(CascadeTaskDispatcher, "create_pending_allocation")
    @patch("jobs.cascade_task_dispatcher.DB.get_session")
    def test_dispatch_task_to_children_defaults_to_all_feeds_when_mps_id_empty(
        self,
        get_session_mock,
        create_pending_allocation_mock,
        notify_children_new_task_mock,
    ):
        session = MagicMock()
        query = session.query.return_value
        query.all.return_value = [
            SimpleNamespace(id="mp-a", mp_name="公众号A"),
            SimpleNamespace(id="mp-b", mp_name="公众号B"),
            SimpleNamespace(id="mp-disabled", mp_name="已禁用公众号"),
        ]
        query.filter.return_value.all.return_value = [
            SimpleNamespace(id="mp-a", mp_name="公众号A"),
            SimpleNamespace(id="mp-b", mp_name="公众号B"),
        ]
        get_session_mock.return_value = session

        dispatcher = CascadeTaskDispatcher()
        create_pending_allocation_mock.side_effect = [
            SimpleNamespace(id="alloc-1"),
            SimpleNamespace(id="alloc-2"),
        ]
        task = SimpleNamespace(id="task-1", name="welink", mps_id="[]")

        result = dispatcher.dispatch_task_to_children(task, "run-1", feeds_per_allocation=1)

        self.assertTrue(result)
        self.assertEqual(create_pending_allocation_mock.call_count, 2)
        first_batch = create_pending_allocation_mock.call_args_list[0][0][1]
        second_batch = create_pending_allocation_mock.call_args_list[1][0][1]
        self.assertEqual([feed.id for feed in first_batch], ["mp-a"])
        self.assertEqual([feed.id for feed in second_batch], ["mp-b"])
        query.filter.assert_called_once()
        notify_children_new_task_mock.assert_called_once_with("alloc-1", 2)


if __name__ == "__main__":
    unittest.main()
