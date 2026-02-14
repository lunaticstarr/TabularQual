import os
import json
import shutil
import asyncio
import uuid
import zipfile
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from tabularqual.convert_spreadsheet_to_sbml import convert_spreadsheet_to_sbml
from tabularqual.convert_sbml_to_spreadsheet import convert_sbml_to_spreadsheet

app = FastAPI(title="TabularQual API")
lock = asyncio.Semaphore(1) # Ensure only one request at a time

def get_temp_paths(ext_in, ext_out):
    uid = uuid.uuid4()
    return f"in_{uid}{ext_in}", f"out_{uid}{ext_out}"

def cleanup_files(file_paths: list[str]):
    """Background task to delete files after the response is sent."""
    for path in file_paths:
        if path and os.path.exists(path):
            os.remove(path)

@app.post("/to-sbml")
async def api_to_sbml(
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...), # Parameter name must be 'files'
    inter_anno: bool = Form(True),
    trans_anno: bool = Form(True),
    validate: bool = Form(False),
    use_name: bool = Form(False)
):
    async with lock:
        job_id = str(uuid.uuid4())
        temp_dir = f"job_{job_id}"
        os.makedirs(temp_dir, exist_ok=True)

        try:
            for file in files:
                file_path = os.path.join(temp_dir, file.filename)
                with open(file_path, "wb") as buffer:
                    shutil.copyfileobj(file.file, buffer)
            
            # Logic to handle both single XLSX and CSV directory structure
            if len(files) == 1 and files[0].filename.endswith(('.xlsx', '.xls')):
                input_path = os.path.join(temp_dir, files[0].filename)
            else:
                input_path = temp_dir

            output_sbml = f"out_{job_id}.sbml"
            
            stats = convert_spreadsheet_to_sbml(
                input_path, output_sbml, 
                interactions_anno=inter_anno, 
                transitions_anno=trans_anno,
                validate=validate, 
                use_name=use_name,
                print_messages=False
            )
            
            # Queue deletion of temp folder and the created SBML
            background_tasks.add_task(cleanup_files, [temp_dir, output_sbml])
            
            return FileResponse(
                output_sbml, 
                filename="model.sbml",
                headers={
                    "X-Stats-Species": str(stats['species']),
                    "X-Stats-Transitions": str(stats['transitions']),
                    "X-Stats-Interactions": str(stats['interactions']),
                    "X-Warnings": json.dumps(stats['warnings']),
                    "X-Validation-Errors": json.dumps(stats.get('validation_errors', []))
                }
            )
        except Exception as e:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            raise HTTPException(status_code=500, detail=str(e))

@app.post("/to-table")
async def api_to_table(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    colon_format: bool = Form(False),
    use_name: bool = Form(False),
    validate: bool = Form(False), # False for API use to save memory
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

            stats = convert_sbml_to_spreadsheet(
                temp_in, temp_out, 
                template_path=template_path,
                rule_format=rule_format, 
                output_csv=output_csv,
                validate=validate, 
                use_name=use_name,
                print_messages=False
            )
            files_to_delete = [temp_in] + stats['created_files']

            # If CSV, zip the multiple created files
            if output_csv:
                zip_path = f"{temp_out}_archive.zip"
                with zipfile.ZipFile(zip_path, 'w') as zipf:
                    for f in stats['created_files']:
                        original_name = os.path.basename(f)
                        # Clean name: remove 'out_uuid_' prefix
                        parts = original_name.split('_')
                        clean_name = "_".join(parts[2:])
                        zipf.write(f, clean_name)

                files_to_delete.append(zip_path)
            
            background_tasks.add_task(cleanup_files, files_to_delete)
            
            return FileResponse(
                zip_path if output_csv else created_files[0], 
                filename="model.xlsx" if not output_csv else "model_csv.zip",
                headers={
                    "X-Stats-Species": str(stats['species']),
                    "X-Stats-Transitions": str(stats['transitions']),
                    "X-Stats-Interactions": str(stats['interactions']),
                    "X-Warnings": json.dumps(stats['warnings']), 
                    "X-Validation-Errors": json.dumps(stats['validation_errors'])
                }
            )

        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
async def root():
    return {"message": "TabularQual API is running. Go to /docs for the interactive UI."}