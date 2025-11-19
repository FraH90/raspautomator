import time
import logging
import os

logger = logging.getLogger(__name__)


def thread_loop(stop_event):
    """
    Simple debug task that logs every second.
    This helps us understand if the task is actually running and if it can be terminated.

    Args:
        stop_event: threading.Event() that signals when the task should stop
    """
    logger.info("=" * 80)
    logger.info("DEBUG TASK STARTED - This task will log every second")
    logger.info("To terminate: touch debug_test.terminate in project root")
    logger.info("=" * 80)

    counter = 0

    # Get the project root (3 levels up from this file)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(os.path.dirname(script_dir))

    terminate_file = os.path.join(project_root, "debug_test.terminate")
    all_terminate_file = os.path.join(project_root, "all.terminate")

    logger.info(f"DEBUG: Script location: {__file__}")
    logger.info(f"DEBUG: Script dir: {script_dir}")
    logger.info(f"DEBUG: Calculated project root: {project_root}")
    logger.info(f"DEBUG: Looking for terminate file at: {terminate_file}")
    logger.info(f"DEBUG: Looking for all.terminate file at: {all_terminate_file}")

    while not stop_event.is_set():
        counter += 1
        logger.info(f"DEBUG TASK: Loop iteration {counter}")

        # Check if we can see the terminate file from within the task
        if os.path.exists(terminate_file):
            logger.info("=" * 80)
            logger.info("DEBUG TASK: I CAN SEE THE TERMINATE FILE!")
            logger.info("DEBUG TASK: Checking stop_event...")
            if stop_event.is_set():
                logger.info("DEBUG TASK: stop_event is SET! I will exit now!")
            logger.info("=" * 80)

        if os.path.exists(all_terminate_file):
            logger.info("=" * 80)
            logger.info("DEBUG TASK: I CAN SEE THE all.terminate FILE!")
            logger.info("=" * 80)

        time.sleep(1)

    logger.info("=" * 80)
    logger.info("DEBUG TASK: stop_event detected! Exiting gracefully...")
    logger.info("=" * 80)
