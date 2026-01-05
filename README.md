# Newsletter Listener App

A minimal, offline-capable Python web app to sync, read, and listen to newsletters from Gmail.

## Setup Instructions

### 1. Google Cloud Credentials
To allow this app to access your Gmail, you need to create a `credentials.json` file.

1.  Go to the [Google Cloud Console](https://console.cloud.google.com/).
2.  Create a new project.
3.  Enable the **Gmail API** for that project.
4.  Go to **Credentials** -> **Create Credentials** -> **OAuth client ID**.
5.  Select **Desktop App** as the application type.
6.  Download the JSON file and rename it to `credentials.json`.
7.  Place `credentials.json` in the root folder of this project.

### 2. Install Dependencies
Run the following command to install the required Python libraries:

```bash
pip install -r requirements.txt
```

### 3. Run the App
```bash
python app.py
```
Open your browser to `http://127.0.0.1:5000`.

## Features
*   **Sync:** Fetches emails that have the "unsubscribe" link or match a custom Label you provide.
*   **Listen:** Converts the newsletter text to speech so you can listen to it.
*   **Offline:** Uses local text-to-speech (no cloud APIs for audio).
