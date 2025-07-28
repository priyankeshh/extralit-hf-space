from fastapi import FastAPI, UploadFile, HTTPException
from fastapi.responses import JSONResponse
import fitz  # PyMuPDF

app = FastAPI()


@app.post("/extract")
async def extract(pdf: UploadFile):
    """
    Accepts a PDF file upload and returns the extracted plain text.
    """
    if pdf.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Invalid content type. Must be application/pdf")
    try:
        file_bytes = await pdf.read()
        document = fitz.open(stream=file_bytes, filetype="pdf")
        pages_text = []
        for page in document:
            text = page.get_text()
            pages_text.append(text)
        full_text = "\n\n".join(pages_text)
        return JSONResponse(content={"text": full_text})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF extraction failed: {e}")