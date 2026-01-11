#!/usr/bin/env python
"""Django's command-line utility for administrative tasks for Flood Alert System."""

import os
import sys


def main():
    """Run administrative tasks."""
    
    # Set the default settings module for the 'backend' project
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
    
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        error_msg = (
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        )
        raise ImportError(error_msg) from exc
    
    # Add the project root to the Python path
    project_root = os.path.dirname(os.path.abspath(__file__))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    
    # Execute the command
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()