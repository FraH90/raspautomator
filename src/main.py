from orchestrator.orchestrator import Orchestrator
import os

# The current working directory is the one from where the python command is executed (and thus the one where the bat file resides)
# It doesn't matter where the python file source code resides!
ROOT_DIR = os.getcwd()
# The task folder is under root dir
TASKS_ROOT_FOLDER = os.path.join(ROOT_DIR, "tasks")


def main():
    orchestrator = Orchestrator(TASKS_ROOT_FOLDER)
    orchestrator.run()


if __name__ == '__main__':
    main()

