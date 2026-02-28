# NLB Library Availability Checker

Check which Singapore National Library Board (NLB) branches have physical copies of your books available live at https://nlbapi.streamlit.app/.

**API Limit**: 1 per second, 15 per minute

## Features

- Look up availability for multiple books at once via the NLB OpenWeb Catalogue API.
- Import your Goodreads library (CSV export) and filter by shelves (e.g. To Read).
- Add individual books or paste a bulk list of `Title, Author` lines.
- See, per library branch:
  - how many copies are available vs total copies
  - detailed copy info including status, media type, and call number.
- Pin favourite libraries so they appear at the top of rankings.
- Handles API rate limiting and caches results to avoid unnecessary calls.

## Quick start

### 1. Clone the repository

```bash
git clone https://github.com/oboboa/nlb_api.git
cd nlb_api
```

### 2. Create and activate a virtual environment (optional but recommended)

On Windows (PowerShell):

```bash
python -m venv env
./env/Scripts/Activate.ps1
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure NLB API credentials

Create a `.env` file in the project root with your NLB OpenWeb API credentials:

```bash
NLB_API_KEY=your_api_key_here
NLB_APP_CODE=your_app_code_here
```

You can request free credentials from the [NLB Open Web Service](https://go.gov.sg/nlblabs-form).

### 5. Run the app

```bash
streamlit run app.py
```

Then open the URL shown in the terminal (by default http://localhost:8501).

To access it from other devices on your local network (same Wi‑Fi):

```bash
streamlit run app.py --server.address 0.0.0.0 --server.port 8501
```

## Using the app

1. **Enter API credentials** in `.env` / Streamlit secrets if deployed.
2. **Import from Goodreads (optional):**
   - Go to Goodreads → [Import/Export](https://www.goodreads.com/review/import) → Export Library and download the CSV.
   - Upload the CSV in the sidebar and choose which shelves to include.
3. **Use the built‑in title list (optional):** enable the `titles.py` list in the sidebar.
4. **Add your own titles:**
   - Add single titles via the form, or
   - Paste multiple `Title, Author` lines in the bulk text area.
5. **Select which titles to check** in the main table and click **Check availability**.
6. Scroll down to see per‑library rankings and detailed copy information.

## Project structure

- `app.py` – Streamlit UI for searching and visualising availability.
- `models.py` – Dataclasses for queries, copies, and aggregated availability.
- `nlb_client.py` – HTTP client for the NLB OpenWeb Catalogue API with rate‑limit handling.
- `availability.py` – Orchestration logic to fetch availability for a list of books.
- `goodreads.py` – Parses Goodreads CSV exports into `BookQuery` objects.
- `titles.py` – Default list of hard‑coded book queries you can customise.

## Notes

- This project focuses on **physical** availability (branches and shelf copies), not e‑books.
- Results are cached in memory for 30 minutes to keep the app responsive and reduce API calls.
