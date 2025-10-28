def setup():
    # Initialization code here
    
    # Specify task timeout
    timeout = 15

    # Schedule configuration for periodic execution
    schedule = {
        "enabled": True,  # Set to True for scheduled execution
        "days_of_week": ["Monday", "Wednesday", "Friday"],  # Days to run the task
        "time_of_day": "12:44"  # Time to run the task (24-hour format)
    }

    return timeout, schedule


def thread_loop():
    # Task code here
    print("Hello man")


# Remember to not put any top-level executable code (that is, in this scope)
