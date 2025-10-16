"""
TabularQual Web Converter
A Streamlit web application for converting between SpreadSBML spreadsheets and SBML-qual files.
"""

import streamlit as st
import tempfile
import os
from pathlib import Path
import pandas as pd
from openpyxl import load_workbook
import warnings
from io import BytesIO
import sys
import gc

# Import converter functions
from converter.convert_spreadsheet_to_sbml import convert_spreadsheet_to_sbml
from converter.convert_sbml_to_spreadsheet import convert_sbml_to_spreadsheet
from converter import spec

# Suppress openpyxl warnings
warnings.filterwarnings('ignore', category=UserWarning, module='openpyxl')

# Page configuration
st.set_page_config(
    page_title="TabularQual Converter",
    page_icon="🔄",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for better styling
st.markdown("""
    <style>
    .main-header {
        /* font-size: 3rem; */
        font-weight: bold;
        color: #1f77b4;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        /* font-size: 2.5rem; */
        color: #666;
        margin-bottom: 2rem;
    }
    .stDownloadButton button {
        background-color: #28a745;
        color: white;
        font-weight: bold;
    }
    .success-box {
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        color: #155724;
        margin: 1rem 0;
    }
    .info-box {
        padding: 1rem;
        border-radius: 0.5rem;
        background-color: #d1ecf1;
        border: 1px solid #bee5eb;
        color: #0c5460;
        margin: 1rem 0;
    }
    </style>
""", unsafe_allow_html=True)

# Header
st.markdown('<p class="main-header">🔄 TabularQual Converter</p>', unsafe_allow_html=True)
st.markdown('<p class="sub-header">Convert between spreadsheets and SBML-qual files for logical models (Boolean and multi-valued). <br>For more about the format, see the <a href="https://docs.google.com/document/d/1RCIN4bOsw4Uq9X2I-gdfBXDydyViYzaVhQK8cpdEWhA/edit?usp=sharing">Spreadsheet specification</a></p>', unsafe_allow_html=True)

# Sidebar with information
with st.sidebar:
    st.header("ℹ️ About")
    st.markdown("""
    This tool converts between:
    - **Spreadsheets** (.xlsx)
    - **SBML-qual** files (.sbml)
    """)
    st.header("🔍 Examples")
    st.markdown("""
    - [Faure2006 (Boolean)](https://docs.google.com/spreadsheets/d/1B9SUcuY_ioQVlY9y351yIHnW45oZ8J1t/edit?usp=drive_link&ouid=105819375684543832411&rtpof=true&sd=true)
    - [ThieffryThomas1995 (Multi-valued)](https://docs.google.com/spreadsheets/d/1Auepvb1Z0Q4lIjMqaesjWdh3oHWTwjA8/edit?usp=drive_link&ouid=105819375684543832411&rtpof=true&sd=true)
    """)
    
    st.header("📖 Documentation")
    st.markdown("""
    **Transition Rules Syntax:**
    - Logical: `&` (AND), `|` (OR), `!` (NOT)
    - Comparisons: `>=`, `<=`, `<`, `>`, `!=`
    - Colon notation: `A:2` means `A >= 2`
    - Negated: `!A:2` means `A < 2`
    """)
    
    st.header("🔗 Links")
    st.markdown("""
    - [GitHub Repository](https://github.com/sys-bio/TabularQual)
    - [The Spreadsheet Specification](https://docs.google.com/document/d/1RCIN4bOsw4Uq9X2I-gdfBXDydyViYzaVhQK8cpdEWhA/edit?usp=sharing)
    - [Google Drive](https://drive.google.com/drive/folders/14lE0jmL4wPnwbfdwgPTs22URD32sovjw?usp=drive_link)
    """)

# Main content
tab1, tab2 = st.tabs(["📊 Spreadsheet → SBML", "📋 SBML → Spreadsheet"])

# Tab 1: Spreadsheet to SBML
with tab1:
    st.header("Convert Spreadsheet to SBML")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        uploaded_xlsx = st.file_uploader(
            "Upload Excel file (.xlsx), you may use this [template](https://docs.google.com/spreadsheets/d/1_welMPd8-Wdbu3fTrCjUZz159yT5kxNO/edit?usp=sharing&ouid=105819375684543832411&rtpof=true&sd=true).",
            type=["xlsx"],
            key="xlsx_upload",
            help="Upload a spreadsheet following the specification"
        )
    
    with col2:
        st.markdown("### Options")
        inter_anno = st.checkbox(
            "Include Interaction Annotations",
            value=True,
            key="inter_anno",
            help="Include annotations from the Interaction tab in the SBML output"
        )
        trans_anno = st.checkbox(
            "Include Transition Annotations",
            value=True,
            key="trans_anno",
            help="Include annotations from the Transitions tab in the SBML output"
        )
    
    if uploaded_xlsx is not None:
        # Store file content once
        file_content = uploaded_xlsx.getvalue()
        
        # Preview uploaded spreadsheet
        with st.expander("📊 Preview Uploaded Spreadsheet", expanded=False):
            try:
                # Use read_only and data_only for memory efficiency
                wb = load_workbook(BytesIO(file_content), read_only=True, data_only=True)
                
                # Skip README and Appendix sheets
                skip_sheets = ["README", "Appendix"]
                skipped_sheets = [s for s in wb.sheetnames if s in skip_sheets]
                
                if skipped_sheets:
                    st.info(f"ℹ️ Skipping sheets: {', '.join(skipped_sheets)}")
                
                for sheet_name in wb.sheetnames:
                    if sheet_name in skip_sheets:
                        continue
                    
                    st.subheader(f"Sheet: {sheet_name}")
                    
                    # Read sheet data
                    sheet = wb[sheet_name]
                    data = []
                    max_preview_rows = 50
                    for idx, row in enumerate(sheet.iter_rows(values_only=True)):
                        if idx >= max_preview_rows:
                            break
                        data.append(row)
                    
                    if data:
                        # Find the maximum number of columns
                        max_cols = max(len(row) for row in data)
                        # Pad rows with None to make them equal length
                        padded_data = [list(row) + [None] * (max_cols - len(row)) for row in data]
                        df = pd.DataFrame(padded_data)
                        st.dataframe(df, use_container_width=True)
                        if idx >= max_preview_rows - 1 and sheet.max_row > max_preview_rows:
                            st.info(f"Preview limited to {max_preview_rows} rows (sheet has {sheet.max_row} rows)")
                        del df, padded_data, data
                        gc.collect()
                    else:
                        st.info("Sheet is empty")
                
                wb.close()
                del wb  # Explicit cleanup
                gc.collect()  # Force garbage collection
            except Exception as e:
                st.error(f"Error previewing spreadsheet: {str(e)}")
        
        # Output filename editor
        st.markdown("### Output File Name")
        original_name = uploaded_xlsx.name.rsplit('.', 1)[0]
        output_filename = st.text_input(
            "Edit output filename (without extension)",
            value=f"{original_name}_out",
            key="sbml_output_name",
            help="The file will be saved with .sbml extension"
        )
        
        # Convert button
        if st.button("🔄 Convert to SBML", type="primary", key="convert_to_sbml"):
            with st.spinner("Converting..."):
                try:
                    # Create temporary file ONCE
                    with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp_in:
                        tmp_in.write(file_content)
                        input_path = tmp_in.name
                    
                    with tempfile.NamedTemporaryFile(suffix='.sbml', delete=False) as tmp_out:
                        output_path = tmp_out.name
                    
                    # conversion
                    stats = convert_spreadsheet_to_sbml(
                        input_path,
                        output_path,
                        interactions_anno=inter_anno,
                        transitions_anno=trans_anno
                    )
                    species_count = stats['species']
                    transitions_count = stats['transitions']
                    interactions_count = stats['interactions']
                    all_messages = stats.get('warnings', [])
                    
                    # Read output file
                    with open(output_path, 'r', encoding='utf-8') as f:
                        sbml_content = f.read()
                    
                    # Success message
                    st.markdown('<div class="success-box">✅ Conversion successful!</div>', unsafe_allow_html=True)
                    
                    # Display messages
                    if all_messages:
                        # Separate info messages from warnings
                        info_msgs = [m for m in all_messages if m.startswith("Found ") or m.startswith("No ")]
                        warning_msgs = [m for m in all_messages if m not in info_msgs]
                        
                        # if info_msgs:
                        #     with st.expander("ℹ️ Conversion Details", expanded=False):
                        #         for msg in info_msgs:
                        #             st.info(msg)
                        
                        if warning_msgs:
                            for msg in warning_msgs:
                                st.warning(f"{msg}")
                    
                    # Display statistics
                    col1, col2, col3 = st.columns(3)
                    col1.metric("Species", species_count)
                    col2.metric("Transitions", transitions_count)
                    col3.metric("Interactions", interactions_count)
                    
                    # LIMIT preview size
                    with st.expander("📄 Preview SBML Output", expanded=False):
                        if len(sbml_content) > 50000:  # ~50KB
                            preview_lines = sbml_content.split('\n')[:100]
                            st.code('\n'.join(preview_lines) + "\n\n... (truncated, download to see full file)", language="xml")
                        else:
                            st.code(sbml_content, language="xml")
                    
                    # Download button
                    final_filename = f"{output_filename}.sbml" if output_filename else f"{original_name}_out.sbml"
                    st.download_button(
                        label="⬇️ Download SBML File",
                        data=sbml_content,
                        file_name=final_filename,
                        mime="application/xml",
                        type="primary"
                    )
                    
                    # Cleanup
                    del sbml_content
                    os.unlink(input_path)
                    os.unlink(output_path)
                    gc.collect()
                    
                except Exception as e:
                    st.error(f"❌ Conversion failed: {str(e)}")
                    import traceback
                    with st.expander("Error Details"):
                        st.code(traceback.format_exc())
                    gc.collect()

# Tab 2: SBML to Spreadsheet
with tab2:
    st.header("Convert SBML to Spreadsheet")
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        uploaded_sbml = st.file_uploader(
            "Upload SBML-qual file (.sbml or .xml)",
            type=["sbml", "xml"],
            key="sbml_upload",
            help="Upload an SBML-qual file for logical models"
        )
    
    with col2:
        st.markdown("### Options")
        colon_format = st.checkbox(
            "Use Colon Notation",
            value=False,
            key="colon_format",
            help="Use colon notation (A:2) instead of operators (A >= 2)"
        )
        
        use_default_template = st.checkbox(
            "Use Default Template",
            value=True,
            key="use_default_template",
            help="Include README and Appendix sheets from default template"
        )
        
        # Custom template upload
        st.markdown("**Or upload custom template:**")
        custom_template = st.file_uploader(
            "Custom Template (.xlsx)",
            type=["xlsx"],
            key="custom_template_upload",
            help="Upload a custom template file for README and Appendix sheets"
        )
    
    if uploaded_sbml is not None:
        # Store file content
        file_content = uploaded_sbml.getvalue()
        
        # Preview
        with st.expander("📄 Preview Uploaded SBML", expanded=False):
            try:
                sbml_text = file_content.decode('utf-8')
                if len(sbml_text) > 50000:  # ~50KB
                    preview_lines = sbml_text.split('\n')[:100]
                    st.code('\n'.join(preview_lines) + "\n\n... (truncated)", language="xml")
                else:
                    st.code(sbml_text, language="xml")
                del sbml_text
            except Exception as e:
                st.error(f"Error previewing SBML: {str(e)}")
        
        # Output filename editor
        st.markdown("### Output File Name")
        original_name = uploaded_sbml.name.rsplit('.', 1)[0]
        output_filename = st.text_input(
            "Edit output filename (without extension)",
            value=f"{original_name}_out",
            key="xlsx_output_name",
            help="The file will be saved with .xlsx extension"
        )
        
        # Convert button
        if st.button("🔄 Convert to Spreadsheet", type="primary", key="convert_to_spreadsheet"):
            with st.spinner("Converting..."):
                try:
                    # Create temporary files
                    with tempfile.NamedTemporaryFile(suffix='.sbml', delete=False) as tmp_in:
                        tmp_in.write(file_content)
                        input_path = tmp_in.name
                    
                    with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp_out:
                        output_path = tmp_out.name
                    
                    # Determine template path
                    template_path = None
                    template_tmp_path = None
                    
                    if custom_template is not None:
                        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp_template:
                            tmp_template.write(custom_template.getvalue())
                            template_tmp_path = tmp_template.name
                            template_path = template_tmp_path
                        st.info("✅ Using custom template")
                    elif use_default_template:
                        template_file = Path(__file__).parent / "doc" / "template.xlsx"
                        if template_file.exists():
                            template_path = str(template_file)
                            st.info("✅ Using default template")
                    
                    # Determine rule format
                    rule_format = "colon" if colon_format else "operators"
                    
                    # Perform conversion and capture messages
                    message_list = convert_sbml_to_spreadsheet(
                        input_path,
                        output_path,
                        template_path=template_path,
                        rule_format=rule_format
                    )
                    
                    # Read the output file
                    with open(output_path, 'rb') as f:
                        xlsx_content = f.read()
                    
                    # Success message
                    st.markdown('<div class="success-box">✅ Conversion successful!</div>', unsafe_allow_html=True)
                    
                    # Display messages
                    if message_list:
                        # Separate info messages from warnings
                        info_msgs = [m for m in message_list if m.startswith("Found ")]
                        warning_msgs = [m for m in message_list if m not in info_msgs]
                        
                        # if info_msgs:
                        #     with st.expander("ℹ️ Conversion Details", expanded=False):
                        #         for msg in info_msgs:
                        #             st.info(msg)
                        
                        if warning_msgs:
                            for msg in warning_msgs:
                                st.warning(f"{msg}")
                    
                    # Display statistics
                    wb = load_workbook(BytesIO(xlsx_content), read_only=True, data_only=True)
                    col1, col2, col3 = st.columns(3)
                    col1.metric("Sheets", len(wb.sheetnames))
                    col2.metric("File Size", f"{len(xlsx_content)} bytes")
                    col3.metric("Format", "Colon" if colon_format else "Operators")
                    
                    # LIMITED Preview
                    with st.expander("📊 Preview Spreadsheet Output", expanded=False):
                        skip_sheets = ["README", "Appendix"]
                        skipped_sheets = [s for s in wb.sheetnames if s in skip_sheets]
                        
                        if skipped_sheets:
                            st.info(f"ℹ️ Skipping sheets: {', '.join(skipped_sheets)}")
                        
                        for sheet_name in wb.sheetnames:
                            if sheet_name in skip_sheets:
                                continue
                            
                            st.subheader(f"Sheet: {sheet_name}")
                            sheet = wb[sheet_name]
                            
                            # LIMIT rows for preview
                            data = []
                            max_preview_rows = 50  # Only show first 50 rows
                            for idx, row in enumerate(sheet.iter_rows(values_only=True)):
                                if idx >= max_preview_rows:
                                    break
                                data.append(row)
                            
                            if data:
                                max_cols = max(len(row) for row in data)
                                padded_data = [list(row) + [None] * (max_cols - len(row)) for row in data]
                                df = pd.DataFrame(padded_data)
                                st.dataframe(df, use_container_width=True)
                                if idx >= max_preview_rows:
                                    st.info(f"Preview limited to {max_preview_rows} rows")
                                del df, padded_data, data
                    
                    wb.close()
                    del wb
                    
                    # Download button
                    final_filename = f"{output_filename}.xlsx" if output_filename else f"{original_name}_out.xlsx"
                    st.download_button(
                        label="⬇️ Download Spreadsheet",
                        data=xlsx_content,
                        file_name=final_filename,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        type="primary"
                    )
                    
                    # Cleanup
                    del xlsx_content
                    os.unlink(input_path)
                    os.unlink(output_path)
                    if template_tmp_path:
                        os.unlink(template_tmp_path)
                    gc.collect()
                    
                except Exception as e:
                    st.error(f"❌ Conversion failed: {str(e)}")
                    import traceback
                    with st.expander("Error Details"):
                        st.code(traceback.format_exc())
                    gc.collect()

# Footer
st.markdown(f"""
<div style='text-align: center; color: #666; padding: 2rem 0;'>
    <p class="version">TabularQual v{spec.VERSION}</p>
    <p>For issues or feedback, please visit our <a href='https://github.com/sys-bio/TabularQual'>GitHub repository</a></p>
</div>
""", unsafe_allow_html=True)