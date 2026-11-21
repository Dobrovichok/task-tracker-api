# Task Tracker API

REST API трекера задач на FastAPI. Данные хранятся в PostgreSQL, запросы выполняет SQLAlchemy, схемой базы управляет Alembic. Swagger UI доступен по адресу [127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

## Запуск через Docker Compose

Из каталога проекта создайте `.env` с двумя случайными секретами. Команда рассчитана на первый запуск и сохраняет существующий `.env`. Для ручной настройки используйте шаблон [`.env.example`](.env.example).

```sh
python -c "from secrets import token_urlsafe; f = open('.env', 'x', encoding='utf-8'); print('POSTGRES_PASSWORD=' + token_urlsafe(32), 'JWT_SECRET=' + token_urlsafe(48), sep=chr(10), file=f); f.close()"
docker compose up --build -d
```

PostgreSQL слушает на `127.0.0.1:5432`, приложение на `127.0.0.1:8000`. Если порт базы занят, добавьте в `.env` `POSTGRES_PORT=5433`. Compose дожидается готовности базы. Затем контейнер API применяет миграции через `alembic upgrade head` и поднимает Uvicorn. Данные сохраняются в именованном томе `postgres_data`.

## Маршруты

| Метод и путь | Действие | Доступ |
| --- | --- | --- |
| `POST /auth/register` | Создать аккаунт с ролью `member` | Публичный |
| `POST /auth/login` | Получить JWT по email и паролю в JSON | Публичный |
| `GET /auth/me` | Получить ID, email и текущую роль | С JWT |
| `POST /tasks` | Создать задачу от своего имени | С JWT |
| `GET /tasks` | Получить задачи с фильтрацией и пагинацией | `member` — свои, `admin` — все |
| `GET /tasks/{task_id}` | Получить задачу | Владелец или `admin` |
| `PATCH /tasks/{task_id}` | Обновить переданные поля | Владелец или `admin` |
| `DELETE /tasks/{task_id}` | Удалить задачу и получить `204` | Владелец или `admin` |

Пароль при регистрации должен содержать от 12 до 128 символов. Пароли хранятся в виде хешей Argon2id. Email приводится к нижнему регистру, повторная регистрация возвращает `409`. JWT передаётся в заголовке `Authorization: Bearer <token>` и действует 30 минут по умолчанию. API проверяет подпись, срок действия, издателя и аудиторию токена. Текущая роль читается из базы при каждом запросе. Если токен истёк, снова вызовите `POST /auth/login`.

Владелец задачи определяется сервером по текущему пользователю. Запрос на чтение, изменение или удаление чужой задачи от имени `member` возвращает `404`. Неизвестные поля и недопустимые значения дают `422`. Чтобы очистить описание или срок выполнения, передайте соответствующему полю значение `null` в `PATCH`.

### Фильтрация и пагинация

```http
GET /tasks?status=todo&priority=high&due_to=2030-06-30&page=1&page_size=10
```

- `status` принимает `todo`, `in_progress` или `done`, `priority` принимает `low`, `medium` или `high`.
- `q` ищет подстроку в названии и описании без учёта регистра. `owner_id` сужает список видимых задач до указанного владельца.
- `due_to` выбирает задачи со сроком до указанной даты включительно. Даты передаются в формате `YYYY-MM-DD`.
- `page` начинается с 1, `page_size` по умолчанию равен 20 и принимает значения от 1 до 100. `total` содержит число всех видимых задач, подходящих под фильтры. При выходе за последнюю страницу `items` пуст, а `total` сохраняет число совпадений.

Новые задачи идут первыми. При совпадении времени создания порядок определяется по ID.

## Проверка вручную

В Swagger UI вызовите `POST /auth/register` и `POST /auth/login`. Нажмите **Authorize**, вставьте значение поля `access_token` и вызовите `POST /tasks`, затем `GET /tasks`. Тот же сценарий в PowerShell выглядит так.

```powershell
$Base = 'http://127.0.0.1:8000'
$Credentials = @{ email = 'demo@example.com'; password = 'demo-password-2026' } | ConvertTo-Json
Invoke-RestMethod "$Base/auth/register" -Method Post -ContentType 'application/json' -Body $Credentials
$Login = Invoke-RestMethod "$Base/auth/login" -Method Post -ContentType 'application/json' -Body $Credentials
$Headers = @{ Authorization = "Bearer $($Login.access_token)" }
$Task = @{ title = 'Review API'; priority = 'high' } | ConvertTo-Json
Invoke-RestMethod "$Base/tasks" -Method Post -ContentType 'application/json' -Headers $Headers -Body $Task
Invoke-RestMethod "$Base/tasks?status=todo&priority=high&page=1&page_size=10" -Headers $Headers
```

Чтобы выдать уже зарегистрированному аккаунту права администратора, выполните команду в окружении сервиса. Для возврата обычных прав передайте `member`. Изменение действует со следующего запроса, в том числе с уже выданным токеном.

```sh
docker compose exec api python -m app.manage_roles demo@example.com admin
```

## Запуск без Docker

Нужны Python 3.14 и доступ к созданной базе PostgreSQL. Укажите реквизиты в `.env` по шаблону, сгенерируйте `JWT_SECRET` длиной не менее 32 символов и выполните из каталога проекта команды ниже. На Linux и macOS путь к интерпретатору окружения — `.venv/bin/python`.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Для изменения роли используйте `python -m app.manage_roles EMAIL admin` с тем же интерпретатором. Текущую ревизию показывает `python -m alembic current`, а `python -m alembic check` проверяет расхождения схемы и моделей.

## Интеграционные тесты

В том же виртуальном окружении установите зависимости из `requirements-dev.txt` и запустите `pytest`. Тесты используют параметры PostgreSQL из `.env` и применяют настоящую миграцию к отдельной временной схеме для каждого сценария. Пользователю базы нужно право `CREATE` на базу.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
```

## Где смотреть код

| Что | Файлы |
| --- | --- |
| Регистрация, вход и JWT | [`app/auth.py`](app/auth.py), [`app/security.py`](app/security.py) |
| Уровни доступа, CRUD и фильтры | [`app/tasks.py`](app/tasks.py), [`app/manage_roles.py`](app/manage_roles.py) |
| Валидация запросов | [`app/schemas.py`](app/schemas.py), [`app/main.py`](app/main.py) |
| Модели и миграция PostgreSQL | [`app/models.py`](app/models.py), [`0001_initial_schema.py`](migrations/versions/0001_initial_schema.py) |

Документация библиотек. [FastAPI — JWT и хеширование паролей](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/) · [FastAPI — модели query-параметров](https://fastapi.tiangolo.com/tutorial/query-param-models/) · [Alembic — миграции](https://alembic.sqlalchemy.org/en/latest/tutorial.html)
