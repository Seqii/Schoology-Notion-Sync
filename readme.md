# Schoology-Notion Sync

A simple integration to move things from schoology to a notion database.

## Function
Every time the script runs if an assignment does not exist it will create it. If is already in the notion database it will update it if anything has changed.

Currently it imports data into a notion database with the following structure:

Property Name | Type
| --- | --- |
Assignment | Title
Class | Select (will automatically create select options based on schoology)
Due	| Date
URL	| URL (link to schoology assigment)
Description	| Text
Status	| Status (defaults as as not started)
---

## Setup
### 1.  Install dependencies:

- python3 -m venv .venv
- source .venv/bin/activate
- pip install -r requirements.txt

### 2. Create .env:

You will need the following variables:



```
SCHOOLOGY_KEY=
SCHOOLOGY_SECRET=
```
You can get these at https://www.app.schoology.com/api/


```py
SCHOOLOGY_TIMEZONE=     #eg. America/Chicago

NOTION_TOKEN=
```
https://app.notion.com/developers/tokens/

```
NOTION_DATABASE_ID=
```
Open your database in full page then get the id from the link (its the 32 characters after /p/ and before the question mark)
```
NOTION_DATA_SOURCE_ID=
```
You can leave this blank, the script discovers this from NOTION_DATABASE_ID automatically.


## Structure
```
.
├── config.py        # Environment/configuration
├── schoology.py     # Schoology API and authentication
├── notion.py        # Notion API client
├── sync.py          # Assignment mapping and sync logic
├── main.py          # Entry point
├── requirements.txt
├── .env
└── .gitignore
```