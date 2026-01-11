# Ganga River Flood Alert System

A real-time flood monitoring dashboard for cities along the Ganga River. Built with Django and vanilla JavaScript.

## What does this do?

This app monitors water levels across 8 major cities along the Ganga River and shows you which areas are at risk. The dashboard updates in real-time and uses color-coded alerts to make it easy to see where flooding might happen.

## Features

- Live monitoring of 8 cities (Varanasi, Patna, Haridwar, Prayagraj, Kanpur, Farakka, Rishikesh, Kolkata)
- Blinking traffic light indicators - red means danger, orange means warning, green means safe
- Filter by region or severity level
- Shows affected population and rainfall data
- Clean, modern UI with smooth animations

## Quick Start

![Image 2](images/WhatsApp%20Image%202026-01-11%20at%205.48.12%20PM.jpeg)

![Image 1](images/WhatsApp%20Image%202026-01-11%20at%205.47.33%20PM.jpeg)

![Image 3](images/WhatsApp%20Image%202026-01-11%20at%205.48.42%20PM.jpeg)

![Image 4](images/WhatsApp%20Image%202026-01-11%20at%205.49.29%20PM.jpeg)


### Prerequisites

You need Python installed on your system. That's it.

### Installation

1. Clone or download this repo

2. Open terminal/command prompt and navigate to the project folder:
```bash
cd "c:\app_fron\ganga river\ganga river"
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up the database:
```bash
python manage.py migrate
```

5. Run the server:
```bash
python manage.py runserver
```

6. Open your browser and go to:
```
http://127.0.0.1:8000/
```

That's it! The dashboard should load with all the city data.

## How to Use

- **Region Filter**: Select a state (Uttarakhand, UP, Bihar, West Bengal) to see only those cities
- **Severity Filter**: Filter by Low/Medium/High severity levels
- **Recent Alerts**: Check the sidebar for blinking indicators - these show real-time status
- **Refresh Button**: Click to manually update the data

## Project Structure

```
ganga river/
├── backend/              # Django backend
│   ├── models.py        # Database models
│   ├── views.py         # View handlers
│   ├── settings.py      # Django settings
│   └── services/        # API services
├── frontend/            # Frontend files
│   ├── index.html       # Main dashboard
│   └── dashboard.js     # Dashboard logic
├── db.sqlite3          # Database
├── manage.py           # Django management
└── requirements.txt    # Python dependencies
```

## Understanding the Alerts

Each city has three threshold levels:
- **Danger Level**: Water is above this = immediate evacuation needed (RED)
- **Warning Level**: Water approaching danger zone (ORANGE)
- **Safe Level**: Normal water levels (GREEN)

The blinking lights in the sidebar show which threshold each city is at.

## Troubleshooting

**Dashboard shows 0 alerts?**
- Make sure `dashboard.js` is loading (check browser console)
- Try refreshing the page

**Server won't start?**
- Check if port 8000 is already in use
- Try running on a different port: `python manage.py runserver 8080`

**Static files not loading?**
- Run: `python manage.py collectstatic`
- Make sure `STATICFILES_DIRS` is set in settings.py

## Tech Stack

- **Backend**: Django 4.2, Django REST Framework
- **Frontend**: Vanilla JavaScript, HTML5, CSS3
- **Database**: SQLite
- **Styling**: Custom CSS with glassmorphism effects

## Contributing

Feel free to fork this and make it better. Some ideas:
- Add more cities
- Connect to real flood monitoring APIs
- Add email/SMS alerts
- Mobile app version

## License

Do whatever you want with this code.

## Contact

If something's broken or you have questions, open an issue.

---

Built for monitoring flood risks along the Ganga River 🌊


