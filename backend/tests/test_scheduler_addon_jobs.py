import os
import uuid
import unittest

os.environ.setdefault("DATA_PATH", f"/tmp/aethera-test-data-{uuid.uuid4()}")

from app.core.scheduler import TaskScheduler
from app.addons.registry import AddonDescriptor, AddonJobSpec, addon_service


def noop():
    return


def dummy_jobs():
    return [
        AddonJobSpec(
            id="dummy_jobs.job",
            name="Dummy Job",
            trigger="interval",
            interval_seconds=60,
            handler=noop,
            max_instances=1,
        )
    ]


class TestSchedulerAddonJobs(unittest.TestCase):
    def test_register_addon_jobs_calls_add_job(self):
        addon_service.register(AddonDescriptor(name="dummy_jobs", scheduled_jobs=dummy_jobs))
        scheduler = TaskScheduler()
        calls = []

        def add_job(*args, **kwargs):
            calls.append(kwargs.get("id"))

        scheduler.scheduler.add_job = add_job
        scheduler._register_addon_jobs()

        self.assertIn("dummy_jobs.job", calls)
