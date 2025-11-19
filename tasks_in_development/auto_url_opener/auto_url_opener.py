import webbrowser

# Note: This path is Windows-specific. For Linux, just use the default browser
# chrome_command = "C:/Program Files/Google/Chrome/Application/chrome.exe %s"


def thread_loop(stop_event):
    """
    Opens a URL in the default browser.

    Args:
        stop_event: threading.Event() that signals when to stop
    """
    url = "http://google.com"

    # Open URL in default browser
    webbrowser.open(url)
    print(f"Opened URL: {url}")

    # Task completes immediately after opening the URL


# Remember to not put any top-level executable code (that is, in this scope)
