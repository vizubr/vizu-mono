from celery import Celery

app = Celery(
    'vizu_tasks',
    broker='redis://localhost:6379/0',
    backend='redis://localhost:6379/0',
    include=['vizu_infra.tasks']
)

if __name__ == '__main__':
    app.start()