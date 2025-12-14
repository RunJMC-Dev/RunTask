DOMAIN = "runtasks"
CONF_TASKS = "tasks"
DATA_UNSUB = "unsub"
SERVICE_RUN_NOW = "run_now"
DEFAULT_TASKS = [
    {
        "name": "Red bin",
        "list": "todo.house_chores",
        "start_date": "2025-11-18",
        "period_days": 14,
        "weekday": 1,
    },
    {
        "name": "Yellow bin",
        "list": "todo.house_chores",
        "start_date": "2025-11-25",
        "period_days": 14,
        "weekday": 1,
    },
]

# Task keys
K_NAME = "name"
K_LIST = "list"
K_START_DATE = "start_date"     # "YYYY-MM-DD" (local date)
K_PERIOD_DAYS = "period_days"   # int
K_WEEKDAY = "weekday"           # 0=Mon..6=Sun

MIDNIGHT_FMT = "%Y-%m-%d %H:%M:%S"  # due_datetime format
