from conftest import require_env


def test_real_word_commands(real_service):
    process_name = require_env("HERMES_TEST_WORD_PROCESS")

    result = real_service.word_select_paragraph(
        start_index=1,
        end_index=1,
        non_empty=True,
        process_name=process_name,
    )

    assert isinstance(result, str)
    assert result


def test_real_excel_commands(real_service):
    process_name = require_env("HERMES_TEST_EXCEL_PROCESS")
    sheet_name = require_env("HERMES_TEST_EXCEL_SHEET")

    result = real_service.excel_get_range_values(
        sheet_name=sheet_name,
        start_row=1,
        start_col=1,
        end_row=2,
        end_col=2,
        process_name=process_name,
    )

    assert isinstance(result, list)


def test_real_powerpoint_commands(real_service):
    process_name = require_env("HERMES_TEST_POWERPOINT_PROCESS")

    result = real_service.powerpoint_set_background_color(
        color="FFFFFF",
        slide_index=[1],
        process_name=process_name,
    )

    assert isinstance(result, str)
    assert result
