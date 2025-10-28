Executor.py should execute all the "tasks" in the root folder
It acts as a launcher which calls the scripts with the attributes above and execute them; 
their execution can be interrupted (killed) by writing a .terminate file which terminate the task execution (this behaviour is coded into the task itself actually)

A task could be a simple .py file in the root folder, or a task.py file inside a sub-folder that lives into the root folder


- vlc
- yt-dlp


yt-dlp:
sudo apt install pipx
pipx install yt-dlp