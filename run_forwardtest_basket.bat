@echo off
REM ============================================================
REM  Gold-QM paper forward-test across the 12-symbol basket.
REM  Read-only on the broker (paper SimBroker) -> ZERO capital risk.
REM  Leave this window OPEN for the test to keep running.
REM  Requires: Exness MT5 terminal installed + logged into your
REM  demo account, left running.
REM ============================================================
cd /d "%~dp0"
set PYTHONPATH=%~dp0
set PYTHONIOENCODING=utf-8

echo Starting basket forward-test. Combined status prints every 10 min.
echo Trades -> output\basket\<SYMBOL>.jsonl   Logs -> output\basket\<SYMBOL>.log
echo Press Ctrl-C in this window to stop and print a final summary.
echo.

python scripts\forwardtest_basket.py --warmup-bars 3000 --status-every 600

echo.
echo Forward-test stopped. Journals are preserved in output\basket\.
pause
