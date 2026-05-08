from conftest import require_env


def test_real_pdf_extraction(real_service):
    pdf_path = require_env("HERMES_TEST_PDF_PATH")

    text = real_service.extract_pdf_text(pdf_path, simulate_human=False)

    assert isinstance(text, str)
    assert text != ""


def test_real_pdf_directory_scan(real_service):
    pdf_dir = require_env("HERMES_TEST_PDF_DIR")

    pdfs = real_service.list_pdfs_in_directory(pdf_dir)

    assert isinstance(pdfs, list)
    assert len(pdfs) >= 1
