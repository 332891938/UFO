param(
    [string]$ServerUrl = "http://localhost:8030/mcp",
    [string]$UiApp = "notepad.exe",
    [string]$UiWindowKeyword = "Notepad",
    [string]$PdfPath = "",
    [string]$PdfDir = "",
    [string]$OmniParserEndpoint = "",
    [string]$WordProcess = "",
    [string]$ExcelProcess = "",
    [string]$ExcelSheet = "",
    [string]$PowerPointProcess = "",
    [string]$MinControls = "0"
)

$env:HERMES_RUN_REAL_TESTS = "1"
$env:HERMES_TEST_SERVER_URL = $ServerUrl
$env:HERMES_TEST_UI_APP = $UiApp
$env:HERMES_TEST_UI_WINDOW_KEYWORD = $UiWindowKeyword
$env:HERMES_TEST_PDF_PATH = $PdfPath
$env:HERMES_TEST_PDF_DIR = $PdfDir
$env:HERMES_OMNIPARSER_ENDPOINT = $OmniParserEndpoint
$env:HERMES_TEST_WORD_PROCESS = $WordProcess
$env:HERMES_TEST_EXCEL_PROCESS = $ExcelProcess
$env:HERMES_TEST_EXCEL_SHEET = $ExcelSheet
$env:HERMES_TEST_POWERPOINT_PROCESS = $PowerPointProcess
$env:HERMES_TEST_MIN_CONTROLS = $MinControls

python -m pytest integration -s
