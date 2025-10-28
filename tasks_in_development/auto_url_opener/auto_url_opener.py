import webbrowser
import sys

chrome_command = "C:/Program Files/Google/Chrome/Application/chrome.exe %s"
url = "http://google.com"


webbrowser.get(chrome_command).open(url)