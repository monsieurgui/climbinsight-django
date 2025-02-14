# ClimbInsight Django API

ClimbInsight is a comprehensive championship management system for climbing competitions. This repository contains the Django-based REST API that powers the platform.

## Features

- League and competition management
- Event scheduling and organization
- Gym profiles and facility management
- User authentication and authorization
- Competition scoring and ranking systems

## Prerequisites

- Python 3.8+
- pip
- virtualenv (recommended)
- Git

## Setup

1. Clone the repository:
```bash
git clone [repository-url]
cd climbinsight-django
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
# On Windows
.\venv\Scripts\activate
# On Unix or MacOS
source venv/bin/activate
```

3. Install dependencies:
```bash
cd src
pip install -r requirements.txt
```

4. Create a .env file in the src directory:
```env
DEBUG=True
SECRET_KEY=your-secret-key-here
ALLOWED_HOSTS=localhost,127.0.0.1
DATABASE_URL=sqlite:///db.sqlite3
```

5. Run migrations:
```bash
python manage.py migrate
```

6. Create a superuser (optional):
```bash
python manage.py createsuperuser
```

7. Run the development server:
```bash
python manage.py runserver
```

The API will be available at `http://localhost:8000/api/`

## Project Structure

```
src/
├── core/           # Core functionality and shared components
├── users/          # User management and authentication
├── leagues/        # League management
├── competitions/   # Competition organization
├── events/         # Event scheduling and management
├── gyms/           # Gym profiles and facility management
└── manage.py       # Django management script
```

## API Documentation

API documentation will be available at `http://localhost:8000/api/docs` once the server is running.

## Development

- Follow PEP 8 style guide
- Write tests for new features
- Update documentation when adding new endpoints
- Use meaningful commit messages

## Testing

```bash
python manage.py test
```

## Contributing

1. Create a new branch for your feature
2. Write tests for your changes
3. Submit a pull request

## License

[License information to be added]

## Contact

[Contact information to be added] 