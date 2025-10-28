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


def thread_loop():
    # Task code here
    print("Hello world")


# Remember to not put any top-level executable code (that is, in this scope)
