# Лодочная станция

Веб-приложение для курсовой работы по дисциплине «Базы данных»: учёт аренды плавсредств, заявок клиентов, инструктажа и администрирования лодочной станции.


## Описание

Система объединяет клиентский портал, кабинет инструктора, панель администратора и интерфейс владельца (суперадмина). Бизнес-логика опирается на PostgreSQL: представления, триггеры и хранимые процедуры; приложение выполняет SQL через слой `sql_queries/` и `crud.py`.

### Роли пользователей

| Роль | Возможности |
|------|-------------|
| **Клиент** | Просмотр водоёмов и судов, проверка запрета купания, подача заявки на аренду, календарь доступных часов, история аренд |
| **Инструктор** | Список назначенных инструктажей, подтверждение проведения инструктажа по заявке |
| **Администратор** | Управление заявками (назначение инструктора, утверждение после инструктажа), ручное создание аренды, флот, ремонты |
| **Владелец (owner)** | CRUD по таблицам БД, просмотр потока логов |

### Типичный сценарий аренды

1. Клиент выбирает водоём и судно, указывает дату и интервал.
2. Система проверяет занятость судна и отсутствие пересечения с активной арендой клиента.
3. Администратор назначает инструктора; инструктор подтверждает инструктаж.
4. Администратор утверждает заявку — в БД срабатывает триггер создания записи аренды (`return_time = NULL` до фактического возврата).

## Скриншоты


### Кабинет клиента

![Клиент](docs/screenshots/04-client.png)

### Панель администратора

![Администратор](docs/screenshots/05-admin.png)

### Кабинет инструктора

![Инструктор](docs/screenshots/06-instructor.png)

## Технологии

| Компонент | Стек |
|-----------|------|
| Backend | [FastAPI](https://fastapi.tiangolo.com/), [Uvicorn](https://www.uvicorn.org/) |
| БД | [PostgreSQL](https://www.postgresql.org/), доступ через [psycopg2](https://www.psycopg.org/) |
| Шаблоны | [Jinja2](https://jinja.palletsprojects.com/) |
| Frontend | HTML, [Tailwind CSS](https://tailwindcss.com/) (CDN), JavaScript |
| Логирование | [Loguru](https://github.com/Delgan/loguru) (`logs/api.log`, локально) |
| Валидация | [Pydantic](https://docs.pydantic.dev/) |

Схема БД, триггеры и представления разворачиваются отдельно (дамп или скрипты курсового проекта PostgreSQL). Имя базы по умолчанию: `boat_station_db`.

## Структура проекта

```
├── main.py              # Точка входа FastAPI, middleware логирования
├── crud.py              # Бизнес-операции и вызовы SQL
├── database.py          # Подключение к PostgreSQL
├── sql_queries/         # Параметризованные SQL-запросы по ролям
├── routers/             # API и HTML-роуты (auth, client, admin, …)
├── templates/           # Jinja2-шаблоны интерфейса
├── static/              # CSS, JS, изображения
├── docs/screenshots/    # Скриншоты для README
├── logging_config.py
└── requirements.txt
```

## Требования

- Python 3.12+
- PostgreSQL 14+ с развёрнутой схемой `boat_station_db`
- Git

## Установка и запуск

```bash
git clone https://github.com/Mark-dgtl/boat_station.git
cd boat_station

python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env
# Отредактируйте DATABASE_URL в .env

export DATABASE_URL="postgresql://USER:PASSWORD@localhost:5432/boat_station_db"

python main.py
```

Приложение будет доступно по адресу: **http://127.0.0.1:8001**

Для разработки в `main.py` включён `reload=True` (автоперезапуск при изменении кода). Каталог `logs/` исключён из отслеживания watcher, чтобы не зацикливать перезагрузку.

### Запуск через uvicorn (без reload)

```bash
uvicorn main:app --host 127.0.0.1 --port 8001
```

## Переменные окружения

| Переменная | Описание |
|------------|----------|
| `DATABASE_URL` | Строка подключения PostgreSQL (`postgresql://user:pass@host:port/dbname`) |

## API

- Документация Swagger: http://127.0.0.1:8001/docs  
- ReDoc: http://127.0.0.1:8001/redoc  

Префиксы роутеров: `/api/auth`, `/api/client`, `/api/instructor`, `/api/admin`, `/api/superadmin`, `/api/logs`.

## Лицензия

Проект распространяется под лицензией [GPL-3.0](LICENSE).
