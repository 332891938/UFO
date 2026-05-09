import argparse
import asyncio
import platform
from typing import Any, Dict, List, Optional

from fastmcp import FastMCP
from pydantic import Field

from mcp_models import TargetInfo
from mcp_service import WindowsMCPService


def register_tools(mcp: FastMCP, service: WindowsMCPService) -> None:
    def _dump_target_list(items: List[TargetInfo]) -> List[Dict[str, Any]]:
        return [item.model_dump() for item in items]

    @mcp.tool()
    def get_desktop_app_info(
        remove_empty: bool = Field(True, description="Hide windows without title text when true."),
        refresh_app_windows: bool = Field(
            True, description="Refresh the desktop window cache when true."
        ),
    ) -> List[Dict[str, Any]]:
        return service.get_desktop_app_info(remove_empty, refresh_app_windows)

    @mcp.tool()
    async def get_desktop_app_target_info(
        remove_empty: bool = Field(True, description="Hide windows without title text when true."),
        refresh_app_windows: bool = Field(
            True, description="Refresh the desktop window cache when true."
        ),
    ) -> List[Dict[str, Any]]:
        return _dump_target_list(
            await asyncio.to_thread(
                service.get_desktop_app_target_info, remove_empty, refresh_app_windows
            )
        )

    @mcp.tool()
    def select_application_window(
        id: str = Field(description="Window id from get_desktop_app_info."),
        name: str = Field(description="Expected window name."),
    ) -> Dict[str, Any]:
        return service.select_application_window(id, name)

    @mcp.tool()
    def get_app_window_info(
        field_list: List[str] = Field(
            default_factory=list,
            description="Fields to return; empty means all supported fields.",
        )
    ) -> Dict[str, Any]:
        return service.get_app_window_info(field_list)

    @mcp.tool()
    def get_app_window_controls_info(
        field_list: List[str] = Field(
            default_factory=list,
            description="Fields to return; empty means all supported fields.",
        ),
        max_controls: int = Field(500, description="Upper bound of controls to return."),
    ) -> List[Dict[str, Any]]:
        return service.get_app_window_controls_info(field_list, max_controls)

    @mcp.tool()
    async def get_app_window_controls_target_info(
        field_list: List[str] = Field(
            default_factory=list, description="Reserved for compatibility; can be empty."
        ),
        max_controls: int = Field(500, description="Upper bound of controls to return."),
    ) -> List[Dict[str, Any]]:
        return _dump_target_list(
            await asyncio.to_thread(
                service.get_app_window_controls_target_info, field_list, max_controls
            )
        )

    @mcp.tool()
    def capture_window_screenshot(
        output_mode: str = Field(
            "data_url",
            description="Screenshot return mode: 'data_url' returns base64 data URI; 'file_path' saves locally and returns the PNG path.",
        ),
        save_path: str = Field(
            "",
            description="Optional local PNG path or directory used when output_mode='file_path'. Empty means auto-generate a temp PNG path.",
        ),
    ) -> str:
        return service.capture_window_screenshot(output_mode=output_mode, save_path=save_path)

    @mcp.tool()
    def capture_desktop_screenshot(
        all_screens: bool = Field(True, description="Capture all screens when true."),
        output_mode: str = Field(
            "data_url",
            description="Screenshot return mode: 'data_url' returns base64 data URI; 'file_path' saves locally and returns the PNG path.",
        ),
        save_path: str = Field(
            "",
            description="Optional local PNG path or directory used when output_mode='file_path'. Empty means auto-generate a temp PNG path.",
        ),
    ) -> str:
        return service.capture_desktop_screenshot(
            all_screens=all_screens,
            output_mode=output_mode,
            save_path=save_path,
        )

    @mcp.tool()
    def get_ui_tree() -> Dict[str, Any]:
        return service.get_ui_tree()

    @mcp.tool()
    def add_control_list(
        control_list: List[Dict[str, Any]] = Field(
            description="External control list in TargetInfo-like dict format."
        ),
    ) -> str:
        return service.add_control_list(control_list)

    @mcp.tool()
    async def parse_window_with_zonui3b(
        query: str = Field(
            "", description="要查找的UI元素描述。为空则返回空列表。"
        ),
    ) -> List[Dict[str, Any]]:
        return _dump_target_list(
            await asyncio.to_thread(service.parse_window_with_zonui3b, query)
        )

    @mcp.tool()
    async def find_control_on_screen(
        description: str = Field(
            description="要查找的UI元素描述，如 'Save button'，'关闭按钮'。"
        ),
        element_type: str = Field(
            "Button", description="元素类型标签，如 Button, TextBox, CheckBox。"
        ),
    ) -> Optional[Dict[str, Any]]:
        """用ZonUI-3B视觉定位屏幕上的控件。

        给定元素描述，截图后用ZonUI-3B精准定位坐标。
        返回TargetInfo（含id用于后续操作如click_control），未找到返回null。
        这是替换OmniParser后新增的核心能力。
        """
        result = await asyncio.to_thread(
            service.find_control_on_screen, description, element_type
        )
        if result is None:
            return None
        return result.model_dump()

    @mcp.tool()
    async def inject_zonui3b_controls(
        control_list: List[Dict[str, Any]] = Field(
            description="ZonUI-3B style controls to inject."
        ),
    ) -> List[Dict[str, Any]]:
        return _dump_target_list(
            await asyncio.to_thread(service.inject_zonui3b_controls, control_list)
        )

    @mcp.tool()
    async def list_controls_hybrid(
        max_uia_controls: int = Field(
            500, description="Maximum number of UIA controls to enumerate."
        ),
    ) -> List[Dict[str, Any]]:
        """列出窗口控件（纯UIA枚举）。

        与旧版不同，不再依赖OmniParser全屏解析。
        控件枚举由Windows UIA完成；ZonUI-3B通过
        find_control_on_screen()提供精准视觉定位。
        """
        return _dump_target_list(
            await asyncio.to_thread(service.list_controls_hybrid, max_uia_controls)
        )

    @mcp.tool()
    def click_input(
        id: str = Field(description="Control id."),
        name: str = Field(description="Expected control name."),
        button: str = Field("left", description="left|right|middle"),
        double: bool = Field(False, description="Double click when true."),
    ) -> str:
        return service.click_input(id, name, button, double)

    @mcp.tool()
    def click_control(
        control_id: str = Field(description="Control id."),
        control_name: str = Field(description="Expected control name."),
        button: str = Field("left", description="left|right|middle"),
        double: bool = Field(False, description="Double click when true."),
    ) -> Dict[str, Any]:
        return service.click_control(control_id, control_name, button, double)

    @mcp.tool()
    def click_on_coordinates(
        x: float = Field(description="Relative x in [0,1]."),
        y: float = Field(description="Relative y in [0,1]."),
        button: str = Field("left", description="left|right|middle"),
        double: bool = Field(False, description="Double click when true."),
    ) -> str:
        return service.click_on_coordinates(x, y, button, double)

    @mcp.tool()
    def drag_on_coordinates(
        start_x: float = Field(description="Relative start x in [0,1]."),
        start_y: float = Field(description="Relative start y in [0,1]."),
        end_x: float = Field(description="Relative end x in [0,1]."),
        end_y: float = Field(description="Relative end y in [0,1]."),
        button: str = Field("left", description="left|right|middle"),
        duration: float = Field(1.0, description="Drag duration in seconds."),
        key_hold: Optional[str] = Field(
            None, description="Optional key to hold during drag."
        ),
    ) -> str:
        return service.drag_on_coordinates(
            start_x, start_y, end_x, end_y, button, duration, key_hold
        )

    @mcp.tool()
    def set_edit_text(
        id: str = Field(description="Control id."),
        name: str = Field(description="Expected control name."),
        text: str = Field(description="Text to input."),
        clear_current_text: bool = Field(
            False, description="Clear current text before input when true."
        ),
    ) -> str:
        return service.set_edit_text(id, name, text, clear_current_text)

    @mcp.tool()
    def keyboard_input(
        id: str = Field(description="Control id."),
        name: str = Field(description="Expected control name."),
        keys: str = Field(description="Key sequence to send."),
        control_focus: bool = Field(
            True, description="Focus the control before sending keys when true."
        ),
    ) -> str:
        return service.keyboard_input(id, name, keys, control_focus)

    @mcp.tool()
    def wheel_mouse_input(
        id: str = Field(description="Control id."),
        name: str = Field(description="Expected control name."),
        wheel_dist: int = Field(description="Wheel delta."),
    ) -> str:
        return service.wheel_mouse_input(id, name, wheel_dist)

    @mcp.tool()
    def texts(
        id: str = Field(description="Control id."),
        name: str = Field(description="Expected control name."),
    ) -> str:
        return service.texts(id, name)

    @mcp.tool()
    async def wait(
        seconds: float = Field(description="Seconds to wait; max 300."),
    ) -> str:
        return await service.wait(seconds)

    @mcp.tool()
    def summary(
        text: str = Field(description="Summary text to return."),
    ) -> str:
        return service.summary(text)

    @mcp.tool()
    def run_shell(
        bash_command: str = Field(
            description="Allow-listed Windows application launch command, e.g. 'notepad.exe'."
        ),
    ) -> str:
        return service.run_shell(bash_command)

    @mcp.tool()
    def extract_pdf_text(
        pdf_path: str = Field(description="Full path to the PDF file to extract text from."),
        simulate_human: bool = Field(
            True, description="Open and wait like a human before extraction."
        ),
    ) -> str:
        return service.extract_pdf_text(pdf_path, simulate_human)

    @mcp.tool()
    def list_pdfs_in_directory(
        directory_path: str = Field(description="Directory path to scan for PDF files."),
    ) -> List[str]:
        return service.list_pdfs_in_directory(directory_path)

    @mcp.tool()
    def extract_all_pdfs_text(
        directory_path: str = Field(description="Directory path containing PDF files."),
        simulate_human: bool = Field(
            True, description="Simulate human review while extracting."
        ),
    ) -> Dict[str, str]:
        return service.extract_all_pdfs_text(directory_path, simulate_human)

    @mcp.tool()
    def word_insert_table(
        rows: int = Field(description="Number of rows in the table."),
        columns: int = Field(description="Number of columns in the table."),
        process_name: Optional[str] = Field(
            None, description="Optional document name or process hint."
        ),
    ) -> str:
        return service.word_insert_table(rows, columns, process_name)

    @mcp.tool()
    def word_select_text(
        text: str = Field(description="Exact text to be selected."),
        process_name: Optional[str] = Field(
            None, description="Optional document name or process hint."
        ),
    ) -> str:
        return service.word_select_text(text, process_name)

    @mcp.tool()
    def word_select_table(
        number: int = Field(description="1-based table index to select."),
        process_name: Optional[str] = Field(
            None, description="Optional document name or process hint."
        ),
    ) -> str:
        return service.word_select_table(number, process_name)

    @mcp.tool()
    def word_select_paragraph(
        start_index: int = Field(description="Start paragraph index."),
        end_index: int = Field(description="End paragraph index, or -1 for end of document."),
        non_empty: bool = Field(
            True, description="Select only non-empty paragraphs when true."
        ),
        process_name: Optional[str] = Field(
            None, description="Optional document name or process hint."
        ),
    ) -> str:
        return service.word_select_paragraph(
            start_index, end_index, non_empty, process_name
        )

    @mcp.tool()
    def word_save_as(
        file_dir: str = Field("", description="Target save directory."),
        file_name: str = Field("", description="Target file name without extension."),
        file_ext: str = Field("", description="Target extension, default .pdf."),
        process_name: Optional[str] = Field(
            None, description="Optional document name or process hint."
        ),
    ) -> str:
        return service.word_save_as(file_dir, file_name, file_ext, process_name)

    @mcp.tool()
    def word_set_font(
        font_name: Optional[str] = Field(None, description="Font name, e.g. Arial."),
        font_size: Optional[int] = Field(None, description="Font size."),
        process_name: Optional[str] = Field(
            None, description="Optional document name or process hint."
        ),
    ) -> str:
        return service.word_set_font(font_name, font_size, process_name)

    @mcp.tool()
    def excel_table2markdown(
        sheet_name: Any = Field(description="Sheet name or 1-based sheet index."),
        process_name: Optional[str] = Field(
            None, description="Optional workbook name or process hint."
        ),
    ) -> str:
        return service.excel_table2markdown(sheet_name, process_name)

    @mcp.tool()
    def excel_insert_table(
        table: List[List[Any]] = Field(description="Table content to insert."),
        sheet_name: str = Field(description="Sheet name."),
        start_row: int = Field(description="Start row, 1-based."),
        start_col: Any = Field(description="Start column, 1-based or letter."),
        process_name: Optional[str] = Field(
            None, description="Optional workbook name or process hint."
        ),
    ) -> str:
        return service.excel_insert_table(
            table, sheet_name, start_row, start_col, process_name
        )

    @mcp.tool()
    def excel_select_table_range(
        sheet_name: str = Field(description="Sheet name."),
        start_row: int = Field(description="Start row, 1-based."),
        start_col: Any = Field(description="Start column, 1-based or letter."),
        end_row: int = Field(description="End row, or -1."),
        end_col: Any = Field(description="End column, or -1 / letter."),
        process_name: Optional[str] = Field(
            None, description="Optional workbook name or process hint."
        ),
    ) -> str:
        return service.excel_select_table_range(
            sheet_name, start_row, start_col, end_row, end_col, process_name
        )

    @mcp.tool()
    def excel_save_as(
        file_dir: str = Field("", description="Target save directory."),
        file_name: str = Field("", description="Target file name without extension."),
        file_ext: str = Field("", description="Target extension, default .csv."),
        process_name: Optional[str] = Field(
            None, description="Optional workbook name or process hint."
        ),
    ) -> str:
        return service.excel_save_as(file_dir, file_name, file_ext, process_name)

    @mcp.tool()
    def excel_reorder_columns(
        sheet_name: str = Field(description="Sheet name."),
        desired_order: List[str] = Field(description="Column names in the new order."),
        process_name: Optional[str] = Field(
            None, description="Optional workbook name or process hint."
        ),
    ) -> str:
        return service.excel_reorder_columns(sheet_name, desired_order, process_name)

    @mcp.tool()
    def excel_get_range_values(
        sheet_name: str = Field(description="Sheet name."),
        start_row: int = Field(description="Start row, 1-based."),
        start_col: int = Field(description="Start column, 1-based."),
        end_row: int = Field(-1, description="End row, or -1."),
        end_col: int = Field(-1, description="End column, or -1."),
        process_name: Optional[str] = Field(
            None, description="Optional workbook name or process hint."
        ),
    ) -> List[List[Any]]:
        return service.excel_get_range_values(
            sheet_name, start_row, start_col, end_row, end_col, process_name
        )

    @mcp.tool()
    def powerpoint_set_background_color(
        color: str = Field(description="Hex RGB color, e.g. FFFFFF."),
        slide_index: Optional[List[int]] = Field(
            None, description="Slide indexes to update; empty means all slides."
        ),
        process_name: Optional[str] = Field(
            None, description="Optional presentation name or process hint."
        ),
    ) -> str:
        return service.powerpoint_set_background_color(color, slide_index, process_name)

    @mcp.tool()
    def powerpoint_save_as(
        file_dir: str = Field("", description="Target save directory."),
        file_name: str = Field("", description="Target file name without extension."),
        file_ext: str = Field("", description="Target extension, default .pptx."),
        current_slide_only: bool = Field(
            False,
            description="For image exports, export only the current slide.",
        ),
        process_name: Optional[str] = Field(
            None, description="Optional presentation name or process hint."
        ),
    ) -> str:
        return service.powerpoint_save_as(
            file_dir, file_name, file_ext, current_slide_only, process_name
        )


def create_windows_ui_mcp_server(host: str = "localhost", port: int = 8030, transport: str = "streamable-http") -> None:
    if platform.system() != "Windows":
        raise RuntimeError("windows_ui_mcp requires Windows.")

    mcp = FastMCP(
        "Windows UI MCP Server",
        instructions=(
            "Standalone Windows UI automation MCP server derived from UFO "
            "client UI MCP functionality."
        ),
    )
    register_tools(mcp, WindowsMCPService())
    if transport == "stdio":
        mcp.run(transport="stdio")
    else:
        mcp.run(transport="streamable-http", host=host, port=port, stateless_http=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="Standalone Windows UI MCP Server")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=8030)
    parser.add_argument("--transport", default="streamable-http", choices=["stdio", "streamable-http"])
    args = parser.parse_args()
    create_windows_ui_mcp_server(host=args.host, port=args.port, transport=args.transport)
