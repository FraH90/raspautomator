def setup():
    # Initialization code here
    
    # Specify task timeout
    timeout = 5

    # Schedule configuration for periodic execution
    schedule = {
        "enabled": False,  # Set to True for scheduled execution
        "days_of_week": ["Monday", "Wednesday", "Friday"],  # Days to run the task
        "time_of_day": "11:35"  # Time to run the task (24-hour format)
    }

    return timeout, schedule


def thread_loop(stop_event):
    """
    Task code here.

    Args:
        stop_event: threading.Event() that signals when to stop
    """
    print("Hello world, this is a test routine!")


# Remember to not put any top-level executable code (that is, in this scope)
