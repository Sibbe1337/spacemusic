import pytest

# Adjust the import path according to your project structure
# This assumes that celery_app is defined in services.docgen.tasks
from services.docgen.tasks import celery_app as docgen_celery_app

def test_generate_termsheet_task_registered():
    """Test that the generate_termsheet Celery task is registered."""
    # The name used in the decorator @celery_app.task(name=...)
    expected_task_name = "services.docgen.tasks.generate_termsheet"
    assert expected_task_name in docgen_celery_app.tasks, f"Task {expected_task_name} not found in registered Celery tasks: {list(docgen_celery_app.tasks.keys())}" 