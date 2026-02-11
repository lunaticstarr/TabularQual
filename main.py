import os
import shutil
import asyncio
import uuid
import zipfile
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse
from tabularqual.convert_spreadsheet_to_sbml import convert_spreadsheet_to_sbml
from tabularqual.convert_sbml_to_spreadsheet import convert_sbml_to_spreadsheet

app = FastAPI(title="TabularQual API")
lock = asyncio.Semaphore(1) # Ensure only one request at a time

def get_temp_paths(ext_in, ext_out):
    uid = uuid.uuid4()
    return f"in_{uid}{ext_in}", f"out_{uid}{ext_out}"

@app.post("/to-sbml")
async def api_to_sbml(
    file: UploadFile = File(...),
    inter_anno: bool = Form(True),
    trans_anno: bool = Form(True),
    validate: bool = Form(True),
    use_name: bool = Form(False)
):
    async with lock:
        temp_in, temp_out = get_temp_paths(os.path.splitext(file.filename)[1], ".sbml")
        try:
            with open(temp_in, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            
            convert_spreadsheet_to_sbml(
                temp_in, temp_out, 
                interactions_anno=inter_anno, 
                transitions_anno=trans_anno,
                validate=validate, 
                use_name=use_name,
                print_messages=False
            )
            return FileResponse(temp_out, filename="model.sbml")
        finally:
            if os.path.exists(temp_in): os.remove(temp_in)

@app.post("/to-table")
async def api_to_table(
    file: UploadFile = File(...),
    colon_format: bool = Form(False),
    use_name: bool = Form(False),
    validate: bool = Form(True),
    output_csv: bool = Form(False)
):
    async with lock:
        # Determine prefix and extension
        ext_out = "" if output_csv else ".xlsx"
        temp_in, temp_out = get_temp_paths(".sbml", ext_out)
        
        try:
            with open(temp_in, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
            
            rule_format = "colon" if colon_format else "operators"
            
            # cli.py logic: if no template, look in doc/
            template_path = None
            if not output_csv:
                doc_template = os.path.join(os.path.dirname(__file__), "doc", "template.xlsx")
                if os.path.exists(doc_template):
                    template_path = doc_template

            _, created_files, _ = convert_sbml_to_spreadsheet(
                temp_in, temp_out, 
                template_path=template_path,
                rule_format=rule_format, 
                output_csv=output_csv,
                validate=validate, 
                use_name=use_name,
                print_messages=False
            )

            # If CSV, zip the multiple created files
            if output_csv:
                zip_path = f"{temp_out}_archive.zip"
                with zipfile.ZipFile(zip_path, 'w') as zipf:
                    for f in created_files:
                        zipf.write(f, os.path.basename(f))
                return FileResponse(zip_path, filename="model_csv.zip", media_type="application/zip")
            
            return FileResponse(created_files[0], filename="model.xlsx")
            
        finally:
            # Cleanup all temporary files
            files_to_clean = [temp_in, temp_out]
            if output_csv:
                files_to_clean.extend(created_files)
                if 'zip_path' in locals(): files_to_clean.append(zip_path)
            for f in files_to_clean:
                if f and os.path.exists(f): os.remove(f)