# Mergington High School Activities API

A super simple FastAPI application that allows students to view and sign up for extracurricular activities.

## Features

- View all available extracurricular activities
- Sign up for activities

## Getting Started

1. Install the dependencies:

   ```
   pip install fastapi uvicorn
   ```

2. Run the application:

   ```
   python app.py
   ```

3. Open your browser and go to:
   - API documentation: http://localhost:8000/docs
   - Alternative documentation: http://localhost:8000/redoc

## API Endpoints

| Method | Endpoint                                                          | Description                                                         |
| ------ | ----------------------------------------------------------------- | ------------------------------------------------------------------- |
| GET    | `/activities`                                                     | Get all activities with their details and current participant count |
| POST   | `/activities/{activity_name}/signup?email=student@mergington.edu` | Sign up for an activity                                             |

## Data and storage

The application stores activities and student signups in a SQLite database.
By default, the database is `src/activities.db`; set `DATABASE_PATH` to use a
different location. The database is created and initialized when the server
starts.

On the first start with an empty database, sample activities and their initial
participants are loaded from `src/activities.json`. That file is only a seed
for a fresh database: after initialization, the SQLite database is the source
of truth, so restarting the server does not overwrite signups or activity
records. Back up the database file to preserve local data.

Each signup has an approval status. Signups made through the current API are
approved immediately, preserving the existing registration behavior.
