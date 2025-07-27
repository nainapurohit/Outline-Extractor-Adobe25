# Adobe India Hackathon 2025 - Round 1A Submission

## Problem Statement: To extract a structured outline from PDFs

In round 1A, the challenge is to extract a structured outline of a PDF - essentially the **Title**, and headings like **H1, H2, H3** - in a clean, hierarcihal format.

This project automatically detects document structure using an **offline, CPU-only pipeline**, without relying on external services.

---

## Approach:

Our approach combines **layout analysis**, **heuristic filtering** and **visual structure clustering** for speed and accuracy.

### Step-wise Breakdown

1. **Document Parsing**

   - Used `pdfplumber` to extract detailed text line info including font size, boldness, position, and page number.
   - Removed lines embedded in tables and detected document title via metadata or layout-based fallback.

2. **Header/Footer Removal**

   - Repetitive lines across pages (based on content and vertical coordinates) were filtered using `Counter`.
   - Custom logic avoids hardcoded rules and adapts to different formats.

3. **Heading Candidates Filtering**

   - Only lines with low word count and non-symbolic text were kept.
   - Discarded digits/symbol-only strings using `isalpha`, `isalnum` checks.

4. **Line Merging**

   - Adjacent lines were merged if they belonged to the same visual block, accounting for inconsistent splits.

5. **Heading Classification**

   - Used features like font size (relative to body font), boldness, and position to assign heading levels.
   - Applied clustering with `MiniBatchKMeans` or `DBSCAN` on scaled font sizes when needed.
   - Classified headings into **H1**, **H2**, **H3** based on cluster position.

6. **JSON Output**
   - Each PDF generates a JSON file with:
     ```json
     {
       "title": "Document Title",
       "outline": [
         { "level": "H1", "text": "Heading A", "page": 0 },
         { "level": "H2", "text": "Subsection A.1", "page": 1 }
       ]
     }
     ```

---

## Tech Stack:

- Python 3.11
- pdfplumber (https://github.com/jsvine/pdfplumber)
- PyMuPdf (https://pymupdf.readthedocs.io/en/latest/)
- NumPy
- scikit-learn

### Features:

✔️No internet is required
✔️Model-free
✔️Entire pipeline runs under 10 seconds for a 50-page document

---

## Project structure:

|--Dockerfile
|--main.py
|--requirements.txt
|--input/
|--output/
|--README.md

---

## Docker Build and Run- as per submission:

1. **Build the docker image using the following command:**
   `docker build --platform linux/amd64 -t mysolutionname:somerandomidentifier`
2. **After building the image, the solution runs using the run command:**
   `docker run --rm -v $(pwd)/input:/app/input -v $(pwd)/output:/app/output -- network none mysolutionname:somerandomidentifier`

## Installation (for Local Testing):

### 1. Create Environment:

bash :
`python3 -m venv venv`
`source venv/bin/activate`
OR
`venv\Scripts\activate` (on Windows)

### 2. Install Requirements

`pip install -r requirements.txt`

### 3. Run the Extractor

`python main.py`

PDFs inside /input will be processed and their corresponding .json files written to /output.

---

## Output format:

The output is a JSON file in the format below:

{
"title": "Understanding AI",
"outline": [
{ "level": "H1", "text": "Introduction", "page": 1 },
{ "level": "H2", "text": "What is AI?", "page": 2 },
{ "level": "H3", "text": "History of AI", "page": 3 }
]
}

---

## Resources used:

1. **PyMuPDF** - for PDF structure and rendering
2. **pdfplumber** - for extracting text lines
3. **scikit-learn** - for unsupervised font-based heading classification

---

This solution was designed and implemented by our team for the Adobe India Hackathon 2025 - Round 1A.
Team : **NOT YOUR DEFAULT** @AdobeIndiaHackathon-2025
