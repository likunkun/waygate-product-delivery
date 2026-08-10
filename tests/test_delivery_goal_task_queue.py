import unittest

from product_delivery_agent.delivery_goal import planned_tasks_from_coverage


class PlannedTasksFromCoverageTests(unittest.TestCase):
    def test_expands_compound_and_range_task_references_in_numeric_order(self):
        state = {
            "test_coverage_audit": {
                "rows": [
                    {"task": "TASK-003,TASK-007"},
                    {"task": "TASK-002,TASK-003,TASK-004"},
                    {"task": "TASK-002..TASK-009"},
                ]
            }
        }

        tasks = planned_tasks_from_coverage(state)

        self.assertEqual(
            [task["task_id"] for task in tasks],
            [
                "TASK-002",
                "TASK-003",
                "TASK-004",
                "TASK-005",
                "TASK-006",
                "TASK-007",
                "TASK-008",
                "TASK-009",
            ],
        )
        self.assertTrue(all("," not in task["task_id"] for task in tasks))
        self.assertTrue(all(".." not in task["task_id"] for task in tasks))

    def test_preserves_nonstandard_coverage_reference_as_one_task(self):
        state = {
            "test_coverage_audit": {
                "rows": [
                    {"task": "CUSTOM-MIGRATION,LEGACY-CHECK"},
                    {"task": "TASK-003"},
                ]
            }
        }

        tasks = planned_tasks_from_coverage(state)

        self.assertEqual(
            [task["task_id"] for task in tasks],
            ["TASK-003", "CUSTOM-MIGRATION,LEGACY-CHECK"],
        )


if __name__ == "__main__":
    unittest.main()
