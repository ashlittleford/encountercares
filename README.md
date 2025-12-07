# Encounter Adelaide Cares

This is a web application for Encounter Adelaide Cares, featuring a public submission form and a password-protected admin interface.

## Features

- **Submission Form**: Collects data for Person, Care Types, Date, Team Member, Notes, Plan, and Site.
- **Admin Dashboard**: View all submissions in a sortable and searchable table.
- **Authentication**: Password-protected access to the admin view.

## Setup and Installation

1.  **Clone the repository** (if you haven't already).
2.  **Install Dependencies**:
    Make sure you have Python installed. Then run:
    ```bash
    pip install -r requirements.txt
    ```

## Running the Application

1.  **Start the server**:
    ```bash
    python app.py
    ```
    The database will be initialized automatically the first time you run the app.

2.  **Access the Website**:
    Open your web browser and go to:
    [http://localhost:5000](http://localhost:5000)

## Usage

- **Submission**: Fill out the form on the landing page and click "Submit Entry".
- **Admin**: Click the "Admin View" tab.
    - **Default Password**: `admin`
