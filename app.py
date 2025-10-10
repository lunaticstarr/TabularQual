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
from io import StringIO

# Import converter functions
from converter.convert_spreadsheet_to_sbml import convert_spreadsheet_to_sbml
from converter.convert_sbml_to_spreadsheet import convert_sbml_to_spreadsheet
from converter.spreadsheet_reader import read_spreadsheet_to_model

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
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        font-size: 1.2rem;
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
st.markdown('<p class="sub-header">Convert between SpreadSBML spreadsheets and SBML-qual files for logical models.</p>', unsafe_allow_html=True)

# Sidebar with information
with st.sidebar:
    st.header("ℹ️ About")
    st.markdown("""
    This tool converts between:
    - **SpreadSBML** spreadsheets (.xlsx)
    - **SBML-qual** files (.sbml)
    
    Supports Boolean and multi-valued logical models.
    """)
    st.header("🔍 Examples")
    st.markdown("""
    - [Faure2006 - Boolean Model](https://docs.google.com/spreadsheets/d/1B9SUcuY_ioQVlY9y351yIHnW45oZ8J1t/edit?usp=drive_link&ouid=105819375684543832411&rtpof=true&sd=true)
    - [ThieffryThomas1995 - Multi-valued Model](https://docs.google.com/spreadsheets/d/1Auepvb1Z0Q4lIjMqaesjWdh3oHWTwjA8/edit?usp=drive_link&ouid=105819375684543832411&rtpof=true&sd=true)
    """)
    
    st.header("📖 Documentation")
    st.markdown("""
    **Transition Rules Syntax:**
    - Logical: `&` (AND), `|` (OR), `!` (NOT)
    - Comparisons: `>=`, `<=`, `<`, `>`, `!=`
    - Colon notation: `A:2` means `A >= 2`
    - Negated: `!A:2` means `A < 2`
    
    **Examples:**
    - `A & B` - Both active
    - `A:2 | B < 1` - A at level 2+ OR B inactive
    - `(A & B) | !C` - Grouped expression
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
            "Upload SpreadSBML Excel file (.xlsx)",
            type=["xlsx"],
            key="xlsx_upload",
            help="Upload a spreadsheet following the SpreadSBML specification"
        )
    
    with col2:
        st.markdown("### Options")
        inter_anno = st.checkbox(
            "Include Interaction Annotations",
            value=True,
            key="inter_anno",
            help="Include interaction annotations in the SBML output"
        )
        trans_anno = st.checkbox(
            "Include Transition Annotations",
            value=True,
            key="trans_anno",
            help="Include transition annotations in the SBML output"
        )
    
    if uploaded_xlsx is not None:
        # Preview uploaded spreadsheet
        with st.expander("📊 Preview Uploaded Spreadsheet", expanded=False):
            try:
                # Load workbook for preview
                wb = load_workbook(BytesIO(uploaded_xlsx.getvalue()), read_only=True)
                
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
                    for row in sheet.iter_rows(values_only=True):
                        data.append(row)
                    
                    if data:
                        # Find the maximum number of columns
                        max_cols = max(len(row) for row in data)
                        # Pad rows with None to make them equal length
                        padded_data = [list(row) + [None] * (max_cols - len(row)) for row in data]
                        df = pd.DataFrame(padded_data)
                        st.dataframe(df, use_container_width=True)
                    else:
                        st.info("Sheet is empty")
                
                wb.close()
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
                    # Create temporary files
                    with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp_in:
                        tmp_in.write(uploaded_xlsx.getvalue())
                        input_path = tmp_in.name
                    
                    with tempfile.NamedTemporaryFile(suffix='.sbml', delete=False) as tmp_out:
                        output_path = tmp_out.name
                    
                    # Read the model to get statistics first
                    model = read_spreadsheet_to_model(input_path)
                    species_count = len(model.species)
                    transitions_count = len(model.transitions)
                    interactions_count = len(model.interactions)
                    
                    # Perform conversion
                    convert_spreadsheet_to_sbml(
                        input_path,
                        output_path,
                        interactions_anno=inter_anno,
                        transitions_anno=trans_anno
                    )
                    
                    # Read the output file
                    with open(output_path, 'r', encoding='utf-8') as f:
                        sbml_content = f.read()
                    
                    # Success message
                    st.markdown('<div class="success-box">✅ Conversion successful!</div>', unsafe_allow_html=True)
                    
                    # Display statistics from the model
                    col1, col2, col3 = st.columns(3)
                    col1.metric("Species", species_count)
                    col2.metric("Transitions", transitions_count)
                    col3.metric("Interactions", interactions_count)
                    
                    # Preview SBML - show full content with scrollable area
                    with st.expander("📄 Preview SBML Output", expanded=True):
                        st.code(sbml_content, language="xml")
                    
                    # Download button with custom filename
                    final_filename = f"{output_filename}.sbml" if output_filename else f"{original_name}_out.sbml"
                    st.download_button(
                        label="⬇️ Download SBML File",
                        data=sbml_content,
                        file_name=final_filename,
                        mime="application/xml",
                        type="primary"
                    )
                    
                    # Clean up temp files
                    os.unlink(input_path)
                    os.unlink(output_path)
                    
                except Exception as e:
                    st.error(f"❌ Conversion failed: {str(e)}")
                    import traceback
                    with st.expander("Error Details"):
                        st.code(traceback.format_exc())

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
        # Preview uploaded SBML - show full content
        with st.expander("📄 Preview Uploaded SBML", expanded=False):
            try:
                sbml_text = uploaded_sbml.getvalue().decode('utf-8')
                st.code(sbml_text, language="xml")
            except Exception as e:
                st.error(f"Error previewing SBML: {str(e)}")
        
        # Output filename editor
        st.markdown("### Output File Name")
        original_name = uploaded_sbml.name.rsplit('.', 1)[0]
        output_filename = st.text_input(
            "Edit output filename (without extension)",
            value=f"{original_name}_reconstructed",
            key="xlsx_output_name",
            help="The file will be saved with .xlsx extension"
        )
        
        # Convert button
        if st.button("🔄 Convert to Spreadsheet", type="primary", key="convert_to_spreadsheet"):
            with st.spinner("Converting..."):
                try:
                    # Create temporary files
                    with tempfile.NamedTemporaryFile(suffix='.sbml', delete=False) as tmp_in:
                        tmp_in.write(uploaded_sbml.getvalue())
                        input_path = tmp_in.name
                    
                    with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp_out:
                        output_path = tmp_out.name
                    
                    # Determine template path
                    template_path = None
                    template_tmp_path = None
                    
                    # Priority: custom template > default template > no template
                    if custom_template is not None:
                        # Save custom template to temp file
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
                    
                    # Perform conversion
                    convert_sbml_to_spreadsheet(
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
                    
                    # Load workbook for preview and stats
                    wb = load_workbook(BytesIO(xlsx_content))
                    
                    # Display statistics
                    col1, col2, col3 = st.columns(3)
                    col1.metric("Sheets", len(wb.sheetnames))
                    col2.metric("File Size", f"{len(xlsx_content)} bytes")
                    col3.metric("Format", "Colon" if colon_format else "Operators")
                    
                    # Preview spreadsheet - skip README and Appendix
                    with st.expander("📊 Preview Spreadsheet Output", expanded=True):
                        skip_sheets = ["README", "Appendix"]
                        skipped_sheets = [s for s in wb.sheetnames if s in skip_sheets]
                        
                        if skipped_sheets:
                            st.info(f"ℹ️ Skipping sheets: {', '.join(skipped_sheets)}")
                        
                        for sheet_name in wb.sheetnames:
                            if sheet_name in skip_sheets:
                                continue
                            
                            st.subheader(f"Sheet: {sheet_name}")
                            
                            sheet = wb[sheet_name]
                            data = []
                            for row in sheet.iter_rows(values_only=True):
                                data.append(row)
                            
                            if data:
                                max_cols = max(len(row) for row in data)
                                padded_data = [list(row) + [None] * (max_cols - len(row)) for row in data]
                                df = pd.DataFrame(padded_data)
                                st.dataframe(df, use_container_width=True)
                    
                    wb.close()
                    
                    # Download button with custom filename
                    final_filename = f"{output_filename}.xlsx" if output_filename else f"{original_name}_out.xlsx"
                    st.download_button(
                        label="⬇️ Download Spreadsheet",
                        data=xlsx_content,
                        file_name=final_filename,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        type="primary"
                    )
                    
                    # Clean up temp files
                    os.unlink(input_path)
                    os.unlink(output_path)
                    if template_tmp_path:
                        os.unlink(template_tmp_path)
                    
                except Exception as e:
                    st.error(f"❌ Conversion failed: {str(e)}")
                    import traceback
                    with st.expander("Error Details"):
                        st.code(traceback.format_exc())

# Footer
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666; padding: 2rem 0;'>
    <p>TabularQual v0.1.0</p>
    <p>For issues or feedback, please visit our <a href='https://github.com/sys-bio/TabularQual'>GitHub repository</a></p>
</div>
""", unsafe_allow_html=True)