"""Antarmuka Textual modern berbahasa Indonesia untuk XToolKit-Diego (macOS & Windows).

Orkestrasi UI: logika Android, Frida, Google Play, dan validasi penawaran tetap
dijalankan melalui adapter native (`macos_runner.py` / `run-all.ps1`) dan `ultra0.py`.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import signal
from collections import deque
from pathlib import Path
import re
import subprocess
import sys
import threading
import time
from typing import cast

from rich.markup import escape
from textual import on, work
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.css.query import NoMatches
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Header, RichLog, Select, Static

from tui_core import (
    STAGES,
    Outcome,
    cli_issue_outcome,
    command_for_step,
    format_realtime_log,
    mask_email,
    needs_setup,
    offer_explorer_lines,
    outcome_for_stage,
    read_fresh_report,
    readable_issue_line,
    report_summary,
    safe_launch_diagnostic,
    sanitize_log_line,
    validate_step,
)
from device_diagnostics import (
    AdbRecoveryResult,
    ConnectionDiagnosis,
    ConnectionStatus,
    inspect_connection,
    poll_connection,
    recover_adb_connection,
)
from stage_history import latest_history, read_history, record_history


SPINNER_FRAMES = ("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏")


class TechnicalLog(RichLog):
    """Menjaga output teknis terbaru selalu terlihat dan auto-scroll ke bawah."""

    def on_resize(self, event) -> None:
        super().on_resize(event)
        if self.display:
            self.scroll_end(animate=False, immediate=True, x_axis=False)


class Approval(ModalScreen[bool]):
    """Dialog konfirmasi berbahasa Indonesia untuk mode manual."""

    CSS = """
    Approval { align: center middle; background: #050a14 82%; }
    #approval_card {
        width: 68; max-width: 92%; height: auto; max-height: 92%;
        padding: 1 3; background: #0f1b30; border: round #38bdf8;
    }
    #approval_title { text-style: bold; color: #f1f5f9; margin-bottom: 1; }
    #approval_scroll { height: auto; max-height: 16; min-height: 3; overflow-y: auto; }
    #approval_message { color: #cbd5e1; margin-bottom: 1; }
    #approval_actions { height: 3; min-height: 3; align-horizontal: right; margin-top: 1; }
    #approval_actions Button {
        height: 3; min-height: 3; margin-left: 1;
        content-align: center middle; text-align: center;
    }
    #cancel { background: #162238; color: #cbd5e1; border: round #334a6e; }
    #cancel:hover { background: #1f304d; color: #ffffff; }
    #approve { background: #b45309; color: #ffffff; border: round #fbbf24; text-style: bold; }
    #approve:hover { background: #d97706; }
    """

    def __init__(self, title: str, message: str) -> None:
        super().__init__()
        self.title_text, self.message_text = title, message

    def compose(self) -> ComposeResult:
        with Vertical(id="approval_card"):
            yield Static(self.title_text, id="approval_title")
            with VerticalScroll(id="approval_scroll", can_focus=True):
                yield Static(self.message_text, id="approval_message")
            with Horizontal(id="approval_actions"):
                yield Button("Batal", id="cancel")
                yield Button("Lanjutkan", id="approve")

    @on(Button.Pressed, "#approval_actions Button")
    def approve(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "approve")


class CheckComplete(ModalScreen[bool]):
    """Dialog ringkasan setelah Step 1 saat mode Auto Step 2 dimatikan."""

    CSS = """
    CheckComplete { align: center middle; background: #050a14 82%; }
    #check_card {
        width: 64; max-width: 94%; height: auto; max-height: 90%;
        padding: 1 3; background: #0f1b30; border: round #10b981;
    }
    #check_scroll { height: auto; max-height: 1fr; }
    #check_title { text-style: bold; color: #6ee7b7; margin-bottom: 1; }
    #check_desc { color: #cbd5e1; margin-bottom: 1; }
    #check_actions { height: 3; min-height: 3; align-horizontal: right; margin-top: 1; }
    #check_actions Button {
        height: 3; min-height: 3; margin-left: 1;
        content-align: center middle; text-align: center;
    }
    #check_later { background: #162238; color: #cbd5e1; border: round #334a6e; }
    #check_later:hover { background: #1f304d; color: #ffffff; }
    #check_continue { background: #059669; color: #ffffff; border: round #34d399; text-style: bold; }
    #check_continue:hover { background: #10b981; }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="check_card"):
            with VerticalScroll(id="check_scroll"):
                yield Static("✓ Pemeriksaan perangkat & penawaran selesai", id="check_title")
                yield Static(
                    "Penawaran Pro 12 bulan dengan fase awal Rp0/$0 ditemukan. "
                    "Kelayakan akhir dan biaya perpanjangan tetap ditentukan oleh Google Play. "
                    "Lanjutkan ke Step 2 sekarang?",
                    id="check_desc",
                )
            with Horizontal(id="check_actions"):
                yield Button("Nanti Saja", id="check_later")
                yield Button("Lanjut ke Step 2", id="check_continue")

    @on(Button.Pressed, "#check_actions Button")
    def choose(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "check_continue")


class SetupNotice(ModalScreen[None]):
    """Pemberitahuan aksi perbaikan berbahasa Indonesia."""

    CSS = """
    SetupNotice { align: center middle; background: #050a14 82%; }
    #notice_card {
        width: 68; max-width: 94%; height: auto; max-height: 90%;
        padding: 1 3; background: #0f1b30; border: round #f59e0b;
    }
    #notice_scroll { height: auto; max-height: 1fr; margin-bottom: 1; }
    #notice_title { text-style: bold; color: #fde68a; margin-bottom: 1; }
    #notice_body, #connection_instruction { color: #e2e8f0; }
    #notice_close {
        width: 100%; height: 3; min-height: 3;
        content-align: center middle; text-align: center;
        background: #162238; color: #e2e8f0; border: round #3b5278;
    }
    #notice_close:hover { background: #1f304d; color: #ffffff; border: round #60a5fa; }
    """

    def __init__(self, title: str, instruction: str) -> None:
        super().__init__()
        self.notice_title, self.instruction = title, instruction

    def compose(self) -> ComposeResult:
        with Vertical(id="notice_card"):
            with VerticalScroll(id="notice_scroll"):
                yield Static(self.notice_title, id="notice_title")
                yield Static(self.instruction, id="notice_body")
            yield Button("Mengerti", id="notice_close")

    @on(Button.Pressed, "#notice_close")
    def close_notice(self) -> None:
        self.dismiss(None)


class AccountPicker(ModalScreen[str | None]):
    """Pilih kandidat akun Google di perangkat Android."""

    CSS = """
    AccountPicker { align: center middle; background: #050a14 82%; }
    #account_picker {
        width: 66; max-width: 94%; height: auto; padding: 1 3;
        background: #0f1b30; border: round #38bdf8;
    }
    #picker_title { text-style: bold; color: #7dd3fc; margin-bottom: 1; }
    #picker_desc { color: #cbd5e1; margin-bottom: 1; }
    #account_choice { width: 100%; }
    #account_picker_actions { height: 3; min-height: 3; margin-top: 1; }
    #account_picker_actions Button {
        width: 1fr; height: 3; min-height: 3;
        content-align: center middle; text-align: center;
    }
    #account_cancel { margin-right: 1; background: #162238; color: #cbd5e1; border: round #334a6e; }
    #account_cancel:hover { background: #1f304d; color: #ffffff; }
    #account_accept { background: #0284c7; color: #ffffff; border: round #38bdf8; text-style: bold; }
    #account_accept:hover { background: #0ea5e9; }
    """

    def __init__(self, accounts: list[str]) -> None:
        super().__init__()
        self.accounts = accounts

    def compose(self) -> ComposeResult:
        with Vertical(id="account_picker"):
            yield Static("◈ Pilih Akun Google di Perangkat", id="picker_title")
            yield Static(
                "Daftar ini adalah kandidat akun di Android, bukan bukti akun aktif di Play Store. "
                "Pastikan akun yang sama dipilih di Google Play Store sebelum menjalankan pemeriksaan.",
                id="picker_desc",
            )
            yield Select(
                [(f"{i + 1}. {email}", email) for i, email in enumerate(self.accounts)],
                value=self.accounts[0],
                allow_blank=False,
                id="account_choice",
            )
            with Horizontal(id="account_picker_actions"):
                yield Button("Batal", id="account_cancel")
                yield Button("Gunakan Akun Ini", id="account_accept")

    @on(Button.Pressed, "#account_picker_actions Button")
    def choose(self, event: Button.Pressed) -> None:
        if event.button.id != "account_accept":
            self.dismiss(None)
            return
        value = self.query_one("#account_choice", Select).value
        self.dismiss(value if isinstance(value, str) and value in self.accounts else None)


class ConnectionNotice(SetupNotice):
    """Dialog gangguan koneksi Android dengan pemulihan ADB otomatis (macOS & Windows)."""

    CSS = SetupNotice.CSS + """
    ConnectionNotice { align: center middle; background: #050a14 82%; }
    #connection_actions { height: 3; min-height: 3; margin-top: 1; }
    #connection_retry {
        width: 2fr;
        min-width: 22;
        height: 3;
        min-height: 3;
        margin-right: 1;
        padding: 0 2;
        content-align: center middle;
        text-align: center;
        background: #0284c7;
        color: #ffffff;
        border: round #38bdf8;
        text-style: bold;
    }
    #connection_retry:hover { background: #0ea5e9; color: #ffffff; border: round #7dd3fc; }
    #connection_actions #notice_close {
        width: 1fr;
        min-width: 12;
        height: 3;
        min-height: 3;
        padding: 0 2;
        content-align: center middle;
        text-align: center;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="notice_card"):
            with VerticalScroll(id="notice_scroll"):
                yield Static(self.notice_title, id="notice_title")
                yield Static(self.instruction, id="connection_instruction")
            with Horizontal(id="connection_actions"):
                yield Button("⚡ Perbaiki & Sambungkan", id="connection_retry")
                yield Button("Tutup", id="notice_close")

    def on_mount(self) -> None:
        self._retry_started: float | None = None
        self.set_interval(1, self._update_retry_time)

    def _update_retry_time(self) -> None:
        if self._retry_started is not None:
            elapsed = int(time.monotonic() - self._retry_started)
            self.query_one("#connection_retry", Button).label = f"Memulihkan ADB… {elapsed}d"

    @property
    def toolkit_app(self) -> "GoogleAITUI":
        return cast("GoogleAITUI", self.app)

    @on(Button.Pressed, "#connection_retry")
    def retry_connection(self) -> None:
        if self._retry_started is not None or self.toolkit_app.busy:
            return
        self._retry_started = time.monotonic()
        self.query_one("#connection_retry", Button).disabled = True
        self.query_one("#notice_close", Button).disabled = True
        self._update_retry_time()
        self._retry_connection_worker()

    @work(thread=True, exclusive=True, group="connection-retry")
    def _retry_connection_worker(self) -> None:
        try:
            recovery = recover_adb_connection(force_reset=True)
            if recovery.ok:
                result = ConnectionStatus(
                    "connected",
                    recovery.devices,
                    offline_devices=recovery.offline_devices,
                    unauthorized_devices=recovery.unauthorized_devices,
                )
            else:
                result = ConnectionStatus(
                    "offline" if recovery.state == "still_offline" else (
                        "unauthorized" if recovery.state == "unauthorized" else (
                            "missing_adb" if recovery.state == "missing_adb" else "disconnected"
                        )
                    ),
                    recovery.devices,
                    offline_devices=recovery.offline_devices,
                    unauthorized_devices=recovery.unauthorized_devices,
                )
            guidance = recovery.guidance
        except Exception:
            result = ConnectionStatus("adb_error")
            guidance = (
                "Gagal memulihkan ADB. Pastikan MuMuPlayer aktif, Android sudah selesai boot, "
                "lalu coba klik 'Perbaiki & Sambungkan'."
            )
        try:
            self.app.call_from_thread(self._retry_finished, result, guidance)
        except RuntimeError:
            pass

    def _retry_finished(self, result: ConnectionStatus, guidance: str = "") -> None:
        if not self.is_mounted:
            return
        self._retry_started = None
        self.query_one("#connection_retry", Button).disabled = False
        self.query_one("#connection_retry", Button).label = "⚡ Perbaiki & Sambungkan"
        self.query_one("#notice_close", Button).disabled = False
        if result.state == "connected":
            self.toolkit_app._connection_polled(result)
        else:
            fallback = (
                "Masih belum terhubung. Tutup lalu buka kembali MuMuPlayer, tunggu Android selesai boot, "
                "aktifkan ADB Debugging, lalu klik 'Perbaiki & Sambungkan'."
            )
            self.query_one("#connection_instruction", Static).update(guidance or fallback)


def is_macos_platform() -> bool:
    return sys.platform == "darwin"


class GoogleAITUI(App[None]):
    """Dasbor utama XToolKit-Diego dengan desain modern & log teknis realtime."""

    TITLE = "XToolKit-Diego"
    SUB_TITLE = "Otomasi & Diagnostik Android"
    BINDINGS = [
        ("d", "toggle_debug", "Log Teknis"),
        ("a", "recover_adb", "Perbaiki ADB"),
        ("i", "reinject_billing", "Inject Billing"),
        ("x", "stop_current", "Hentikan"),
        ("r", "run_selected", "Jalankan"),
        ("q", "quit_safely", "Keluar"),
    ]

    CSS = """
    Screen {
        background: #080e1a;
        color: #e2e8f0;
    }
    Header {
        background: #0c1425;
        color: #38bdf8;
        text-style: bold;
    }
    Footer {
        background: #0c1425;
        color: #94a3b8;
    }
    #screen {
        height: 1fr;
        min-height: 0;
        padding: 0 1;
    }

    /* ─── Top Banner Modern ─── */
    #topbar {
        height: 1;
        background: #0f1b33;
        padding: 0 2;
        align-vertical: middle;
        margin-bottom: 1;
    }
    #app_title {
        width: auto;
        color: #f8fafc;
        text-style: bold;
    }
    #app_badge {
        width: auto;
        color: #38bdf8;
        margin-left: 2;
    }
    #topbar_spacer {
        width: 1fr;
    }
    #top_pill {
        width: auto;
        color: #34d399;
        text-style: bold;
    }
    #top_pill.busy { color: #38bdf8; }
    #top_pill.warn { color: #fbbf24; }
    #top_pill.error { color: #fb7185; }

    /* ─── Telemetry Cards (Perangkat & Akun) ─── */
    #details {
        height: 3;
        margin-bottom: 1;
    }
    #device, #account {
        width: 1fr;
        height: 3;
        background: #0f172a;
        border: round #23324d;
        color: #e2e8f0;
        padding: 0 2;
        content-align: left middle;
    }
    #device.online { border: round #10b981; color: #a7f3d0; background: #0a1f1c; }
    #device.offline { border: round #f59e0b; color: #fde68a; background: #21190c; }
    #device.disconnected { border: round #f43f5e; color: #fecdd3; background: #240f17; }
    #account { margin-left: 1; }
    #account.verified { border: round #38bdf8; color: #bae6fd; background: #0b1c2e; }
    #fix_adb_quick {
        width: 14;
        min-width: 11;
        height: 3;
        margin-left: 1;
        background: #0e2a47;
        color: #7dd3fc;
        border: round #0284c7;
        text-style: bold;
    }
    #fix_adb_quick:hover { background: #143b61; color: #ffffff; border: round #38bdf8; }
    #choose_account {
        width: 15;
        min-width: 12;
        height: 3;
        margin-left: 1;
        background: #162238;
        color: #e2e8f0;
        border: round #3b5278;
        text-style: bold;
    }
    #choose_account:hover { background: #1f304d; color: #ffffff; border: round #60a5fa; }

    /* ─── Main Two-Column Body ─── */
    #content {
        height: 1fr;
        min-height: 0;
    }

    /* ─── Sidebar Kiri ─── */
    #controls {
        width: 30;
        min-width: 24;
        min-height: 0;
        border: round #1e304d;
        background: #0c1425;
        padding: 1 1 0 1;
        overflow-y: auto;
        scrollbar-size: 1 1;
    }
    .section {
        color: #38bdf8;
        text-style: bold;
        padding: 0 1;
        margin: 0;
    }
    .sidebar-divider {
        color: #1e304d;
        height: 1;
        margin: 0 1;
    }
    #workflow {
        height: auto;
        margin: 1 0 1 0;
    }
    .workflow-step {
        color: #94a3b8;
        height: 1;
        padding: 0 1;
    }
    .workflow-step.step-running {
        color: #38bdf8;
        text-style: bold;
        background: #122642;
    }
    .workflow-step.step-done {
        color: #34d399;
        text-style: bold;
    }
    .workflow-step.step-review {
        color: #fbbf24;
        text-style: bold;
    }
    .workflow-step.step-history {
        color: #818cf8;
    }

    /* Tombol Sidebar Proporsional & Rata Tengah Sempurna */
    #recover_adb, #diagnose, #debug, #nav_help, #reload, #exit {
        width: 100%;
        height: 3;
        min-height: 3;
        margin: 0;
        padding: 0 1;
        content-align: center middle;
        text-align: center;
    }
    #recover_adb {
        margin-top: 1;
        background: #0c2e4d;
        color: #7dd3fc;
        border: round #0ea5e9;
        text-style: bold;
    }
    #recover_adb:hover { background: #0f3f69; color: #ffffff; border: round #38bdf8; }
    #diagnose {
        background: #102a38;
        color: #5eead4;
        border: round #0d9488;
        text-style: bold;
    }
    #diagnose:hover { background: #14394c; color: #ccfbf1; border: round #2dd4bf; }
    #debug {
        background: #162238;
        color: #cbd5e1;
        border: round #334a6e;
    }
    #debug:hover { background: #1f304d; color: #f8fafc; border: round #60a5fa; }
    #nav_help {
        background: #162033;
        color: #cbd5e1;
        border: round #2c3e5e;
    }
    #nav_help:hover { background: #1f2d47; color: #f8fafc; border: round #64748b; }
    #reload {
        background: #162033;
        color: #cbd5e1;
        border: round #2c3e5e;
    }
    #reload:hover { background: #1f2d47; color: #f8fafc; border: round #64748b; }
    #exit {
        background: #2b121e;
        color: #fda4af;
        border: round #9f1239;
        text-style: bold;
    }
    #exit:hover { background: #45162b; color: #ffe4e6; border: round #f43f5e; }
    #nav_home, #nav_quick, #sequence, #run_all { display: none; }

    /* ─── Area Kerja Kanan ─── */
    #results {
        width: 1fr;
        min-width: 30;
        min-height: 0;
        margin-left: 1;
        overflow-y: auto;
        scrollbar-size: 1 1;
    }

    /* ─── Card 1: Kontrol Aksi ─── */
    #welcome_panel {
        height: auto;
        max-height: 55%;
        min-height: 6;
        overflow-y: auto;
        scrollbar-size: 1 1;
        border: round #0ea5e9;
        background: #0f1b30;
        padding: 0 2;
        margin-bottom: 1;
    }
    #welcome_header {
        height: 1;
        margin-bottom: 0;
    }
    #welcome {
        width: 1fr;
        color: #38bdf8;
        text-style: bold;
        height: 1;
    }
    #quick_hint {
        display: none;
        color: #94a3b8;
        height: auto;
        margin: 0;
    }
    #primary_actions {
        height: 3;
        margin-bottom: 0;
    }
    #quickstart {
        width: 1fr;
        height: 3;
        margin: 0;
        background: #059669;
        color: #ffffff;
        border: round #34d399;
        text-style: bold;
    }
    #quickstart:hover {
        background: #10b981;
        color: #ffffff;
        border: round #6ee7b7;
    }
    #quickstart.checking:disabled, #run.checking:disabled {
        background: #065f46;
        color: #ecfdf5;
        border: round #10b981;
        text-style: bold;
        text-opacity: 1;
        opacity: 1;
    }
    #next {
        display: none;
        width: 1fr;
        height: 3;
        margin: 0;
        background: #059669;
        color: #ffffff;
        border: round #34d399;
        content-align: center middle;
        text-align: center;
        text-style: bold;
    }
    #next:hover { background: #10b981; }
    #reinject_billing {
        display: none;
        width: 1fr;
        height: 3;
        margin: 0 1 0 0;
        background: #0284c7;
        color: #ffffff;
        border: round #38bdf8;
        content-align: center middle;
        text-align: center;
        text-style: bold;
    }
    #reinject_billing:hover { background: #0ea5e9; color: #ffffff; border: round #7dd3fc; }
    #stop {
        display: none;
        width: 22;
        min-width: 16;
        height: 3;
        margin: 0 0 0 1;
        background: #be123c;
        color: #fff1f2;
        border: round #fb7185;
        text-style: bold;
    }
    #stop:hover { background: #e11d48; color: #ffffff; }
    #secondary_actions {
        height: 3;
        margin-top: 0;
    }
    #auto_toggle {
        width: 1fr;
        height: 3;
        min-height: 3;
        padding: 0 2;
        margin: 0 1 0 0;
        background: #162033;
        color: #94a3b8;
        border: round #334155;
    }
    #auto_toggle:hover { background: #1e2d47; color: #e2e8f0; }
    #auto_toggle.auto-on {
        background: #09352b;
        color: #6ee7b7;
        border: round #10b981;
        text-style: bold;
    }
    #auto_toggle.auto-on:hover { background: #0d4a3c; color: #a7f3d0; }
    #advanced_toggle {
        width: 1fr;
        height: 3;
        min-height: 3;
        padding: 0 2;
        margin: 0;
        background: #162238;
        color: #cbd5e1;
        border: round #334a6e;
    }
    #advanced_toggle:hover { background: #1f304d; color: #f8fafc; border: round #60a5fa; }
    #refresh_offers {
        display: none;
        width: 100%;
        height: 3;
        margin-top: 1;
    }
    #workflow_actions {
        display: none;
        height: auto;
        margin-top: 1;
        border-top: solid #1e3a5f;
        padding-top: 1;
    }
    #form_row { height: auto; }
    #mode_field { display: none; }
    .field { width: 1fr; min-width: 12; height: auto; }
    #step_field { margin-left: 0; }
    #mode_field { margin-left: 1; }
    #mode_label, #advanced_label {
        color: #7dd3fc;
        text-style: bold;
        height: 1;
        margin: 0 0 1 0;
    }
    #mode, #step { width: 100%; margin: 0; }
    #run_row { layout: vertical; width: 1fr; height: auto; margin: 1 0 0 0; }
    #run { width: 100%; min-width: 0; height: 3; margin: 0; content-align: center middle; }
    #mode_hint {
        width: 1fr;
        height: auto;
        color: #94a3b8;
        padding: 1 0 0 0;
    }
    #read_only { color: #7dd3fc; height: auto; margin-top: 1; }

    /* ─── Card 2: Status Langsung & Penawaran ─── */
    #status_panel {
        height: auto;
        min-height: 5;
        max-height: 12;
        border: round #1e3a5f;
        background: #0c1527;
        padding: 0 2;
        margin-bottom: 1;
        overflow-y: auto;
        scrollbar-size: 1 1;
    }
    #status_header {
        height: 1;
        margin-bottom: 0;
    }
    #status_title {
        width: 1fr;
        color: #38bdf8;
        text-style: bold;
    }
    #elapsed {
        width: auto;
        color: #38bdf8;
        text-style: bold;
    }
    #activity {
        color: #67e8f9;
        text-style: bold;
        height: auto;
    }
    #state {
        color: #f8fafc;
        text-style: bold;
        margin: 0;
    }
    #message {
        color: #cbd5e1;
        height: auto;
    }
    #step_result {
        color: #34d399;
        height: auto;
    }
    #offers_title {
        display: none;
        color: #38bdf8;
        text-style: bold;
        margin-top: 1;
    }
    #offer_view {
        display: none;
        height: 6;
        min-height: 4;
        margin-top: 0;
        border: round #1e3a5f;
        background: #060b16;
    }
    #manual {
        display: none;
        width: 100%;
        height: 3;
        margin-top: 1;
    }
    #history {
        color: #64748b;
        height: auto;
        margin-top: 0;
    }
    #hint {
        display: none;
        color: #64748b;
        height: auto;
        margin-top: 0;
    }

    /* ─── Card 3: Konsol Log Teknis Realtime (Otomatis Tampil!) ─── */
    #console_panel {
        height: 1fr;
        min-height: 6;
        border: round #2563eb;
        background: #060b16;
        padding: 0 1;
    }
    #console_panel.active {
        border: round #38bdf8;
    }
    #console_header {
        height: 1;
        padding: 0 1;
        background: #0e1d36;
    }
    #console_title {
        width: 1fr;
        color: #38bdf8;
        text-style: bold;
    }
    #log_meta {
        width: auto;
        color: #94a3b8;
        margin-right: 1;
    }
    #clear_log {
        width: auto;
        min-width: 11;
        height: 1;
        border: none;
        padding: 0 1;
        background: #1e293b;
        color: #cbd5e1;
    }
    #clear_log:hover { background: #334155; color: #ffffff; }
    #debug_log {
        height: 1fr;
        min-height: 4;
        background: #060b16;
        border: none;
        padding: 0 1;
        overflow-x: hidden;
        scrollbar-size: 1 1;
    }

    /* ─── Responsive Breakpoints ─── */
    Screen.compact #topbar { height: 1; border: none; padding: 0 1; margin-bottom: 0; }
    Screen.compact #details { height: 1; margin-bottom: 0; }
    Screen.compact #device, Screen.compact #account { height: 1; border: none; padding: 0 1; }
    Screen.compact #fix_adb_quick, Screen.compact #choose_account {
        height: 1; min-height: 1; border: none; padding: 0 1;
    }
    Screen.compact #controls { padding: 0 1; }
    Screen.compact #recover_adb, Screen.compact #diagnose, Screen.compact #debug,
    Screen.compact #nav_help, Screen.compact #reload, Screen.compact #exit {
        height: 1; min-height: 1; border: none; margin: 0; padding: 0 1;
    }
    Screen.compact #welcome_panel {
        padding: 0 1; margin-bottom: 0; min-height: 5; max-height: 45%;
    }
    Screen.compact #welcome_header, Screen.compact #quick_hint, Screen.compact #read_only {
        display: none;
    }
    Screen.compact #secondary_actions { height: 1; margin-top: 0; }
    Screen.compact #auto_toggle, Screen.compact #advanced_toggle {
        height: 1; min-height: 1; border: none; padding: 0 1;
    }
    Screen.compact #status_panel {
        min-height: 4; max-height: 36%; padding: 0 1; margin-bottom: 0;
    }
    Screen.compact #history, Screen.compact #hint { display: none; }
    Screen.compact #console_panel { min-height: 5; }
    Screen.compact #workflow_actions { margin-top: 0; padding-top: 0; border-top: none; }
    Screen.compact #mode_label, Screen.compact #advanced_label { margin-bottom: 0; }
    Screen.compact #run_row { margin-top: 0; }
    Screen.compact #mode_hint { padding: 0; }

    Screen.narrow #form_row { layout: vertical; }
    Screen.narrow #mode_field { margin: 1 0 0 0; }
    Screen.narrow #controls { width: 23; min-width: 20; }
    Screen.narrow #fix_adb_quick { width: 10; min-width: 9; }
    Screen.narrow #choose_account { width: 12; min-width: 10; }
    Screen.narrow #stop { width: 14; min-width: 12; }

    Screen.tiny #content { layout: vertical; }
    Screen.tiny #controls {
        width: 100%; min-width: 0; height: auto;
        max-height: 9; overflow-y: auto; margin-bottom: 1;
    }
    Screen.tiny #workflow { display: none; }
    Screen.tiny #results { width: 100%; min-width: 0; margin-left: 0; }
    """

    def __init__(
        self,
        *,
        repo: Path,
        selected_step: int = 1,
        start_sequence: bool = False,
        initial_debug: bool = True,
        auto_step2: bool = True,
    ) -> None:
        super().__init__()
        self.repo = repo.resolve()
        self.initial_step = validate_step(selected_step)
        self.macos_mode = is_macos_platform()
        self.start_sequence = start_sequence
        self.debug_visible = initial_debug
        self.auto_step2 = auto_step2
        self._auto_continue_armed = False
        self.busy = False
        self._diagnosing = False
        self._recovering_adb = False
        self._recovering_adb_silent = False
        self._adb_cancel_event = threading.Event()
        self._last_auto_adb_recovery = 0.0
        self.sequence = False
        self.current_step: int | None = None
        self._child: subprocess.Popen[str] | None = None
        self._last_output: deque[str] = deque(maxlen=500)
        self._run_output: deque[str] = deque(maxlen=50)
        self._stop_after_step = False
        self._cancel_requested = False
        self._exit_after_step = False
        self._last_outcome: Outcome | None = None
        self._verified_account: str | None = None
        self._selected_account: str | None = None
        self._history_account: str | None = None
        self._environment_checked = False
        self._offer_ready_account: str | None = None
        self._accounts_loading = False
        self._offer_check_ready = False
        self._initial_offer_ready = False
        self._billing_opened_step: int | None = None
        self._reinject_step: int | None = None
        self._reinject_mode = False
        self._checked_device: str | None = None
        self._offer_ready_device: str | None = None
        self._connection_state: ConnectionStatus | None = None
        self._connection_polling = False
        self._connection_generation = 0
        self._started_at: float | None = None
        self._last_activity_at: float | None = None
        self._spinner_index = 0
        self._activity_text = "Menunggu perintah Anda."
        self.advanced_visible = False
        self.more_modes_visible = False
        self._last_selected_step = self.initial_step
        self._last_mode = "single"

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical(id="screen"):
            with Horizontal(id="topbar"):
                yield Static("✦ XToolKit-Diego", id="app_title")
                platform_tag = "macOS · Native ADB/Frida" if self.macos_mode else "Windows · MuMu/ADB"
                yield Static(f"│  {platform_tag}", id="app_badge")
                yield Static("", id="topbar_spacer")
                yield Static("● SIAGA", id="top_pill")

            with Horizontal(id="details"):
                yield Static("○ Perangkat  ·  Deteksi otomatis", id="device")
                yield Button("⚡ ADB", id="fix_adb_quick")
                yield Static("○ Akun  ·  Belum diperiksa", id="account")
                yield Button("◈ Akun", id="choose_account")

            with Horizontal(id="content"):
                with Vertical(id="controls"):
                    yield Static("TAHAPAN PROSES", classes="section")
                    with Vertical(id="workflow"):
                        for stage in STAGES:
                            yield Static(
                                f"○  {stage.number}. {stage.label}",
                                id=f"stage_{stage.number}",
                                classes="workflow-step",
                            )
                    yield Static("─" * 24, classes="sidebar-divider")
                    yield Static("ALAT & KONTROL", classes="section")
                    yield Button("⚡ Perbaiki ADB", id="recover_adb")
                    yield Button("◎ Diagnosa Koneksi", id="diagnose")
                    yield Button("▤ Sembunyikan Log", id="debug")
                    yield Button("◈ Panduan", id="nav_help")
                    yield Button("↻ Muat Ulang", id="reload")
                    yield Button("⏻ Keluar", id="exit")

                with Vertical(id="results"):
                    with Vertical(id="welcome_panel"):
                        with Horizontal(id="welcome_header"):
                            yield Static("KONTROL UTAMA · PROSES CEPAT", id="welcome")
                        yield Static(
                            "Cek perangkat & penawaran, lalu lanjut otomatis ke Step 2 saat penawaran 12 bulan siap.",
                            id="quick_hint",
                        )
                        with Horizontal(id="primary_actions"):
                            yield Button(
                                "▶ Cek & Lanjut Step 2" if self.auto_step2 else "▶ Cek Perangkat & Penawaran",
                                id="quickstart",
                                variant="success",
                            )
                            yield Button("↻ Inject Ulang Billing", id="reinject_billing", disabled=True)
                            yield Button("✓ Lanjut ke Step Berikutnya →", id="next", variant="primary", disabled=True)
                            yield Button("■ Hentikan", id="stop", disabled=True)
                        with Horizontal(id="secondary_actions"):
                            yield Button(
                                "⚡ Auto Step 2: AKTIF" if self.auto_step2 else "○ Auto Step 2: MANUAL",
                                id="auto_toggle",
                                classes="auto-on" if self.auto_step2 else "",
                            )
                            yield Button("⚙ Pilih Langkah Manual  +", id="advanced_toggle")

                        with Vertical(id="workflow_actions"):
                            yield Button("↻ Cek Perangkat & Penawaran — Step 1", id="refresh_offers", variant="success")
                            with Horizontal(id="form_row"):
                                with Vertical(classes="field", id="step_field"):
                                    yield Static("Pilih langkah", id="advanced_label")
                                    yield Select(
                                        [(f"{stage.number}. {stage.label}", stage.number) for stage in STAGES]
                                        + [("Opsi mode lanjutan…", 99)],
                                        value=self.initial_step,
                                        id="step",
                                        allow_blank=False,
                                    )
                                with Vertical(classes="field", id="mode_field"):
                                    yield Static("Setelah langkah ini", id="mode_label")
                                    yield Select(
                                        [
                                            ("Berhenti setelah langkah ini", "single"),
                                            ("Lanjut ke langkah berikutnya", "from"),
                                            ("Mulai berurutan dari Step 2", "all"),
                                        ],
                                        value="single",
                                        id="mode",
                                        allow_blank=False,
                                    )
                            with Horizontal(id="run_row"):
                                yield Button("▶ Jalankan Langkah Ini", id="run", variant="primary")
                                yield Static("Menjalankan satu langkah yang dipilih.", id="mode_hint")
                            yield Button("Jalankan berurutan", id="sequence")
                            yield Button("Jalankan semua", id="run_all")
                            yield Static(
                                "Step 2–4 dapat membuka checkout Google Play; periksa status akun dan ketentuan di perangkat.",
                                id="read_only",
                            )

                    with Vertical(id="status_panel"):
                        with Horizontal(id="status_header"):
                            yield Static("● STATUS LANGSUNG", id="status_title")
                            yield Static("⏱ --:--", id="elapsed")
                        yield Static("Menunggu perintah Anda.", id="activity", markup=False)
                        yield Static("Siap — belum ada proses berjalan", id="state", markup=False)
                        yield Static(
                            "Tekan 'Cek & Lanjut Step 2' untuk memulai, atau 'Perbaiki ADB' jika emulator belum terdeteksi.",
                            id="message",
                            markup=False,
                        )
                        yield Static("", id="step_result", markup=False)
                        yield Static("PENAWARAN TERSEDIA · FASE AWAL", id="offers_title")
                        yield RichLog(id="offer_view", wrap=True, highlight=False, markup=False)
                        yield Button("✓ Aksi di Android Selesai", id="manual", variant="warning", disabled=True)
                        yield Static(
                            "Riwayat muncul setelah akun dipilih/diverifikasi.",
                            id="history",
                            markup=False,
                        )
                        yield Static("", id="hint")

                    with Vertical(id="console_panel"):
                        with Horizontal(id="console_header"):
                            yield Static("◉ LOG TEKNIS REALTIME", id="console_title")
                            yield Static("0 baris", id="log_meta")
                            yield Button("Bersihkan", id="clear_log")
                        yield TechnicalLog(id="debug_log", wrap=True, highlight=False, markup=True)
        yield Footer()

    def on_resize(self, event) -> None:
        self.screen.set_class(event.size.height < 27, "compact")
        self.screen.set_class(event.size.width < 90, "narrow")
        self.screen.set_class(event.size.width < 62, "tiny")

    def on_mount(self) -> None:
        self._render_history(
            latest_history(self.repo),
            "Riwayat terakhir · pilih akun lalu jalankan Step 1 untuk verifikasi",
        )
        self.set_interval(0.25, self._tick_realtime)
        self.set_interval(5, self._poll_connection)

        console_panel = self.query_one("#console_panel", Vertical)
        console_panel.display = self.debug_visible
        self.query_one("#debug_log", RichLog).display = self.debug_visible
        self.query_one("#debug", Button).label = (
            "▤ Sembunyikan Log" if self.debug_visible else "▤ Tampilkan Log"
        )
        self._append_log(
            "XToolKit-Diego siap. Log teknis realtime aktif otomatis. "
            "Mode Auto Step 2: AKTIF." if self.auto_step2
            else "XToolKit-Diego siap. Log teknis realtime aktif otomatis. Mode Auto Step 2: MANUAL.",
            level="OK",
        )

        if self.start_sequence:
            self.query_one("#mode", Select).value = "from"
            self.more_modes_visible = True
            self.advanced_visible = True
            self.query_one("#workflow_actions", Vertical).display = True
            self.query_one("#advanced_toggle", Button).label = "⚙ Sembunyikan Langkah  −"
            self.query_one("#mode_field", Vertical).display = True
        self._sync_auto_toggle_ui()
        self._update_run_mode()

    # ─── Realtime Logging & Animation Helpers ───────────────────────────

    def _set_top_pill(self, text: str, variant: str = "") -> None:
        try:
            pill = self.query_one("#top_pill", Static)
        except NoMatches:
            return
        pill.remove_class("busy", "warn", "error")
        if variant:
            pill.add_class(variant)
        pill.update(text)

    def _set_activity(self, text: str) -> None:
        self._activity_text = text
        prefix = f"{SPINNER_FRAMES[self._spinner_index]} " if (self.busy or self._recovering_adb or self._diagnosing) else "• "
        self.query_one("#activity", Static).update(f"{prefix}{text}")

    def _append_log(self, line: str, *, level: str | None = None) -> None:
        if not line:
            return
        formatted = format_realtime_log(line, level=level)
        self._last_output.append(formatted)
        self.query_one("#log_meta", Static).update(f"{len(self._last_output)} baris")
        if self.debug_visible:
            self.query_one("#debug_log", RichLog).write(formatted, scroll_end=True)

    def _tick_realtime(self) -> None:
        active = self.busy or self._recovering_adb or self._diagnosing
        if not active or not self.is_mounted:
            return
        try:
            self._spinner_index = (self._spinner_index + 1) % len(SPINNER_FRAMES)
            spinner = SPINNER_FRAMES[self._spinner_index]
            self.query_one("#activity", Static).update(f"{spinner} {self._activity_text}")
            if self._started_at is not None:
                elapsed = int(time.monotonic() - self._started_at)
                self.query_one("#elapsed", Static).update(f"⏱ {elapsed // 60:02d}:{elapsed % 60:02d}")
                if self._recovering_adb:
                    if not self._recovering_adb_silent:
                        self.query_one("#quickstart", Button).label = f"{spinner} Memulihkan ADB… {elapsed}d"
                    self._set_top_pill(f"{spinner} MEMULIHKAN ADB {elapsed}d", "warn")
                elif self.busy and self.current_step == 1:
                    self.query_one("#quickstart", Button).label = f"{spinner} Cek Penawaran… {elapsed}d"
                    self.query_one("#run", Button).label = f"{spinner} Step 1… {elapsed}d"
                    self._set_top_pill(f"{spinner} STEP 1 · {elapsed}d", "busy")
                elif self.busy and self.current_step is not None:
                    self.query_one("#quickstart", Button).label = f"{spinner} Menjalankan Step {self.current_step}… {elapsed}d"
                    self.query_one("#run", Button).label = f"{spinner} Step {self.current_step}… {elapsed}d"
                    self._set_top_pill(f"{spinner} STEP {self.current_step} · {elapsed}d", "busy")
            if self.busy and self._last_activity_at is not None:
                idle = int(time.monotonic() - self._last_activity_at)
                if idle >= 30:
                    self._activity_text = f"Belum ada output baru selama {idle} detik. Cek layar emulator atau tekan Hentikan."
        except NoMatches:
            return

    def _refresh_elapsed(self) -> None:
        """Alias kompatibilitas untuk timer uji otomatis."""
        self._tick_realtime()

    @on(Button.Pressed, "#clear_log")
    def clear_log_pressed(self) -> None:
        self._last_output.clear()
        self.query_one("#debug_log", RichLog).clear()
        self.query_one("#log_meta", Static).update("0 baris")

    # ─── Toggle Auto Step 2 ─────────────────────────────────────────────

    def _sync_auto_toggle_ui(self) -> None:
        toggle = self.query_one("#auto_toggle", Button)
        if self.auto_step2:
            toggle.add_class("auto-on")
            toggle.label = "⚡ Auto Step 2: AKTIF"
        else:
            toggle.remove_class("auto-on")
            toggle.label = "○ Auto Step 2: MANUAL"
        if not self.busy and not self._recovering_adb:
            self.query_one("#quickstart", Button).label = self._idle_quickstart_label()

    def _idle_quickstart_label(self) -> str:
        if self._initial_offer_ready:
            return "▶ Lanjut ke Step 2 (Pro 12 Bulan)"
        if self.auto_step2:
            return "▶ Cek & Lanjut Step 2"
        return "▶ Cek Perangkat & Penawaran"

    @on(Button.Pressed, "#auto_toggle")
    def auto_toggle_pressed(self) -> None:
        if self.busy:
            return
        self.auto_step2 = not self.auto_step2
        self._sync_auto_toggle_ui()
        self.notify(f"Auto Step 2: {'AKTIF' if self.auto_step2 else 'MANUAL'}")

    # ─── ADB Recovery (Handle Nyangkut, Offline, Connection Refused) ───

    def action_recover_adb(self) -> None:
        self.recover_adb_pressed()

    @on(Button.Pressed, "#recover_adb")
    @on(Button.Pressed, "#fix_adb_quick")
    def recover_adb_pressed(self) -> None:
        if self.busy or self._diagnosing or self._recovering_adb:
            return
        self._start_adb_recovery(force_reset=True, silent=False)

    def _start_adb_recovery(self, *, force_reset: bool, silent: bool) -> None:
        self._invalidate_connection_polls()
        self._recovering_adb = True
        self._recovering_adb_silent = silent
        self._adb_cancel_event.clear()
        self._started_at = time.monotonic()
        self._last_activity_at = self._started_at
        self.query_one("#console_panel", Vertical).add_class("active")
        self._set_top_pill("⚡ MEMULIHKAN ADB", "warn")
        self._set_activity("Memulai ulang ADB server & menyambungkan ulang perangkat (127.0.0.1:16384)...")
        if not silent:
            self._set_status("Memulihkan koneksi ADB...")
            self._set_message(
                "Menjalankan adb start-server, membersihkan entri offline, dan menyambungkan ulang ke emulator."
            )
            self._lock_action_controls(running_adb=True)
        self._run_adb_recovery_worker(force_reset, silent)

    def _lock_action_controls(self, *, running_adb: bool = False) -> None:
        self.query_one("#quickstart", Button).disabled = True
        self.query_one("#quickstart", Button).add_class("checking")
        self.query_one("#recover_adb", Button).disabled = True
        self.query_one("#fix_adb_quick", Button).disabled = True
        self.query_one("#diagnose", Button).disabled = True
        self.query_one("#choose_account", Button).disabled = True
        self.query_one("#auto_toggle", Button).disabled = True
        self.query_one("#reload", Button).disabled = True
        self.query_one("#refresh_offers", Button).disabled = True
        self.query_one("#run", Button).disabled = True
        self.query_one("#sequence", Button).disabled = True
        self.query_one("#mode", Select).disabled = True
        self.query_one("#step", Select).disabled = True
        self.query_one("#next", Button).disabled = True
        self.query_one("#next", Button).display = False
        self.query_one("#reinject_billing", Button).disabled = True
        self.query_one("#reinject_billing", Button).display = False
        stop_btn = self.query_one("#stop", Button)
        stop_btn.display = True
        stop_btn.disabled = False
        stop_btn.label = "■ Hentikan ADB" if running_adb else "■ Hentikan"

    def _unlock_action_controls(self) -> None:
        self.query_one("#quickstart", Button).remove_class("checking")
        self.query_one("#quickstart", Button).disabled = False
        self.query_one("#quickstart", Button).label = self._idle_quickstart_label()
        self.query_one("#run", Button).remove_class("checking")
        self.query_one("#recover_adb", Button).disabled = False
        self.query_one("#fix_adb_quick", Button).disabled = False
        self.query_one("#diagnose", Button).disabled = False
        self.query_one("#choose_account", Button).disabled = self._accounts_loading
        self.query_one("#auto_toggle", Button).disabled = False
        self.query_one("#reload", Button).disabled = False
        self.query_one("#refresh_offers", Button).disabled = False
        self.query_one("#run", Button).disabled = False
        self.query_one("#sequence", Button).disabled = False
        self.query_one("#mode", Select).disabled = False
        self.query_one("#step", Select).disabled = False
        self.query_one("#stop", Button).disabled = True
        self.query_one("#stop", Button).display = False
        self.query_one("#exit", Button).disabled = False
        self.query_one("#console_panel", Vertical).remove_class("active")

    @work(thread=True, exclusive=True, group="adb-recovery")
    def _run_adb_recovery_worker(self, force_reset: bool, silent: bool) -> None:
        def _stream(msg: str) -> None:
            try:
                self.call_from_thread(self._adb_log_line, msg)
            except RuntimeError:
                pass

        try:
            result = recover_adb_connection(
                force_reset=force_reset,
                log=_stream,
                cancel_check=self._adb_cancel_event.is_set,
            )
        except Exception as exc:
            result = AdbRecoveryResult(
                ok=False,
                state="adb_error",
                headline="Pemulihan ADB gagal",
                guidance=safe_launch_diagnostic(exc),
            )
        try:
            self.call_from_thread(self._adb_recovery_done, result, silent)
        except RuntimeError:
            pass

    def _adb_log_line(self, message: str) -> None:
        self._last_activity_at = time.monotonic()
        self._set_activity(message)

    def _adb_recovery_done(self, result: AdbRecoveryResult, silent: bool) -> None:
        self._recovering_adb = False
        self._recovering_adb_silent = False
        self._started_at = None
        self._last_auto_adb_recovery = time.monotonic()
        self.query_one("#console_panel", Vertical).remove_class("active")
        if not silent:
            self._unlock_action_controls()
            self._update_run_mode()
        elif not self.busy:
            # Pastikan label tombol utama tidak pernah tertinggal pada teks "Memulihkan ADB..."
            quick = self.query_one("#quickstart", Button)
            quick.remove_class("checking")
            quick.disabled = False
            quick.label = self._idle_quickstart_label()

        if result.ok:
            status = ConnectionStatus(
                "connected",
                result.devices,
                offline_devices=result.offline_devices,
                unauthorized_devices=result.unauthorized_devices,
            )
            self._connection_state = status
            self._update_device_card(status)
            self._set_top_pill("● TERHUBUNG", "")
            self._set_activity("Koneksi ADB siap digunakan.")
            if not silent:
                self._set_status(result.headline)
                self._set_message(result.guidance)
                self.query_one("#step_result", Static).update(
                    f"Perangkat online: {', '.join(result.devices)}"
                )
            if isinstance(self.screen, ConnectionNotice):
                self.screen.dismiss(None)
            self.notify(f"ADB terhubung: {', '.join(result.devices)}")
            return

        if result.state == "cancelled":
            self._set_top_pill("● SIAGA", "")
            self._set_activity("Pemulihan ADB dihentikan.")
            if not silent:
                self._set_status("Pemulihan ADB dihentikan")
                self._set_message("Proses pemulihan ADB dibatalkan oleh pengguna.")
            return

        mapped_state = (
            "offline"
            if result.state == "still_offline"
            else (
                "unauthorized"
                if result.state == "unauthorized"
                else ("missing_adb" if result.state == "missing_adb" else "disconnected")
            )
        )
        status = ConnectionStatus(
            mapped_state,
            result.devices,
            offline_devices=result.offline_devices,
            unauthorized_devices=result.unauthorized_devices,
        )
        self._connection_state = status
        self._update_device_card(status)
        self._set_top_pill("! ADB TERPUTUS", "error")
        self._set_activity("Koneksi ADB belum berhasil dipulihkan.")
        if not silent:
            self._set_status(result.headline)
            self._set_message(result.guidance)
            self.query_one("#step_result", Static).update("")
        if not isinstance(self.screen, ModalScreen):
            self.push_screen(ConnectionNotice(result.headline, result.guidance))

    def _update_device_card(self, result: ConnectionStatus) -> None:
        card = self.query_one("#device", Static)
        card.remove_class("online", "offline", "disconnected")
        if result.state == "connected":
            card.add_class("online")
            label = (
                f"● Perangkat · {escape(result.devices[0])}"
                if len(result.devices) == 1
                else f"● Perangkat · {len(result.devices)} perangkat ADB"
            )
            card.update(label)
        elif result.state == "offline":
            card.add_class("offline")
            target = result.offline_devices[0] if result.offline_devices else "ADB"
            card.update(f"◌ Perangkat · {escape(target)} (OFFLINE)")
        elif result.state == "unauthorized":
            card.add_class("offline")
            card.update("◌ Perangkat · Menunggu izin USB")
        else:
            card.add_class("disconnected")
            card.update("✕ Perangkat · Tidak terhubung")

    # ─── Navigation & Utility Buttons ───────────────────────────────────

    @on(Button.Pressed, "#nav_home")
    def home_pressed(self) -> None:
        if not self.busy:
            self._set_message("Pilih tombol Cek & Lanjut Step 2 untuk memulai.")

    @on(Button.Pressed, "#nav_quick")
    def quick_pressed(self) -> None:
        self.quickstart_pressed()

    @on(Button.Pressed, "#reload")
    def reload_pressed(self) -> None:
        if self.busy or self._diagnosing or self._accounts_loading or self._recovering_adb:
            return
        try:
            os.execv(sys.executable, [sys.executable, str(self.repo / "tui.py")])
        except OSError:
            self.notify("Gagal memuat ulang aplikasi. Tutup lalu buka kembali terminal.", severity="error")

    @on(Button.Pressed, "#nav_help")
    def help_pressed(self) -> None:
        self._set_status("Panduan Singkat XToolKit-Diego")
        self._set_message(
            "1) Pastikan MuMuPlayer/Android aktif. Jika ADB nyangkut/offline, klik 'Perbaiki ADB' [a].\n"
            "2) Klik 'Cek & Lanjut Step 2' untuk memeriksa penawaran lalu otomatis lanjut ke Step 2.\n"
            "3) Tekan 'Hentikan' [x] kapan saja untuk membatalkan proses yang sedang berjalan."
        )

    @on(Button.Pressed, "#choose_account")
    def choose_account_pressed(self) -> None:
        if self.busy or self._diagnosing or self._accounts_loading or self._recovering_adb:
            return
        self._accounts_loading = True
        self.query_one("#choose_account", Button).disabled = True
        self._set_status("Membaca daftar akun Android...")
        self._set_message(
            "Mencari kandidat akun Google pada perangkat yang terhubung tanpa membuka checkout."
        )
        self._append_log("Membaca daftar kandidat akun Google dari perangkat Android...", level="AKUN")
        self.discover_account_candidates()

    @work(thread=True, exclusive=True, group="account-candidates")
    def discover_account_candidates(self) -> None:
        try:
            lookup = self.repo / "scripts" / "runtime-lookup.py"

            def read_value(command: str, serial: str = "") -> str:
                args = [sys.executable, str(lookup), command]
                if serial:
                    args.extend(["--serial", serial])
                result = subprocess.run(
                    args,
                    capture_output=True,
                    text=True,
                    errors="replace",
                    timeout=60,
                    check=False,
                )
                line = result.stdout.strip()
                match = re.fullmatch(r"RUNTIME_RESULT:([A-Za-z0-9+/=]*)", line)
                if result.returncode or not match:
                    raise RuntimeError("Pembacaan akun Android gagal")
                return base64.b64decode(match.group(1), validate=True).decode("utf-8")

            serial = self._checked_device or read_value("device")
            if not serial or not re.fullmatch(r"[A-Za-z0-9._:/-]{1,90}", serial):
                raise RuntimeError("Perangkat Android tunggal tidak ditemukan")
            raw = json.loads(read_value("play-accounts", serial))
            if not isinstance(raw, list):
                raise ValueError("Format daftar akun Android tidak valid")
            accounts = sorted(
                {
                    x.lower()
                    for x in raw
                    if isinstance(x, str)
                    and re.fullmatch(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}", x)
                }
            )
            self.call_from_thread(self._account_candidates_loaded, accounts)
        except (OSError, UnicodeError, ValueError, RuntimeError, subprocess.TimeoutExpired):
            self.call_from_thread(self._account_candidates_loaded, [])

    def _account_candidates_loaded(self, accounts: list[str]) -> None:
        self._accounts_loading = False
        self.query_one("#choose_account", Button).disabled = self.busy or self._diagnosing or self._recovering_adb
        if not accounts:
            self._set_status("Daftar akun tidak tersedia")
            self._set_message(
                "Android tidak mengembalikan daftar akun. Buka Google Play Store, pilih profil yang "
                "diinginkan secara manual, lalu jalankan Cek Perangkat & Penawaran."
            )
            self._append_log("Daftar akun Google tidak terbaca dari Android.", level="WARN")
            return
        self._append_log(f"Ditemukan {len(accounts)} kandidat akun Google di Android.", level="AKUN")
        self.push_screen(AccountPicker(accounts), self._account_chosen)

    def _account_chosen(self, account: str | None) -> None:
        if not account or self.busy:
            return
        self._selected_account = account
        self._show_history(account)
        self._verified_account = None
        self._offer_ready_account = None
        self._offer_check_ready = False
        self._initial_offer_ready = False
        self._billing_opened_step: int | None = None
        self._reinject_step: int | None = None
        self._reinject_mode = False
        self._offer_ready_device = None
        acct_card = self.query_one("#account", Static)
        acct_card.remove_class("verified")
        acct_card.update("○ Akun  ·  " + escape(mask_email(account)) + " (dipilih)")
        self.query_one("#quickstart", Button).label = self._idle_quickstart_label()
        self._update_run_mode()
        self._set_status("Akun dipilih — belum diverifikasi")
        self._set_message(
            "Pastikan akun tersebut aktif di Google Play Store, lalu jalankan pemeriksaan."
        )
        self._append_log(f"Akun target dipilih: {mask_email(account)} (menunggu verifikasi Step 1).", level="AKUN")

    @on(Button.Pressed, "#diagnose")
    def diagnose_pressed(self) -> None:
        if self.busy or self._diagnosing or self._recovering_adb:
            return
        self._invalidate_connection_polls()
        self._offer_check_ready = False
        self._initial_offer_ready = False
        self._billing_opened_step: int | None = None
        self._reinject_step: int | None = None
        self._reinject_mode = False
        self._offer_ready_device = None
        self.query_one("#quickstart", Button).label = self._idle_quickstart_label()
        self._diagnosing = True
        self._started_at = time.monotonic()
        self.query_one("#diagnose", Button).disabled = True
        self.query_one("#recover_adb", Button).disabled = True
        self.query_one("#fix_adb_quick", Button).disabled = True
        self.query_one("#quickstart", Button).disabled = True
        self.query_one("#quickstart", Button).display = True
        self.query_one("#next", Button).display = False
        self.query_one("#next", Button).disabled = True
        self.sequence = False
        self.query_one("#run", Button).disabled = True
        self._set_top_pill("🩺 DIAGNOSA", "busy")
        self._set_activity("Memeriksa ADB, perangkat Android, Google Play, dan Google One...")
        self._set_status("Memeriksa koneksi Android...")
        self._set_message(
            "Menjalankan diagnosa lokal ADB, Frida, Google Play, dan Google One tanpa memulai checkout."
        )
        self._append_log("Menjalankan diagnosa koneksi Android...", level="ADB")
        self.inspect_android_connection()

    @work(thread=True, exclusive=True, group="android-connection")
    def inspect_android_connection(self) -> None:
        try:
            diagnosis = inspect_connection()
        except Exception:
            diagnosis = ConnectionDiagnosis(
                "error",
                "Diagnosa koneksi tidak dapat diselesaikan",
                (),
                "Periksa instalasi ADB atau klik 'Perbaiki ADB' lalu coba lagi.",
            )
        self.call_from_thread(self._diagnosis_done, diagnosis)

    def _diagnosis_done(self, diagnosis: ConnectionDiagnosis) -> None:
        self._diagnosing = False
        self._started_at = None
        self.query_one("#diagnose", Button).disabled = False
        self.query_one("#recover_adb", Button).disabled = False
        self.query_one("#fix_adb_quick", Button).disabled = False
        self.query_one("#quickstart", Button).disabled = False
        self.query_one("#run", Button).disabled = False
        self._set_top_pill("● SIAGA" if diagnosis.status == "connected" else "! CEK ADB", "" if diagnosis.status == "connected" else "warn")
        self._set_activity("Diagnosa koneksi selesai.")
        self._set_status(diagnosis.headline)
        self._set_message(diagnosis.guidance)
        self.query_one("#step_result", Static).update("\n".join(diagnosis.details))
        self.query_one("#offers_title", Static).display = False
        self.query_one("#offer_view", RichLog).display = False
        self._append_log(f"Hasil diagnosa: {diagnosis.headline}", level="OK" if diagnosis.status == "connected" else "WARN")
        for detail in diagnosis.details:
            self._append_log(f"  {detail}", level="ADB")
        self._update_run_mode()

    # ─── Background ADB Polling & Auto-Recovery ─────────────────────────

    def _invalidate_connection_polls(self) -> None:
        self._connection_generation += 1
        self._connection_polling = False

    def _poll_connection(self) -> None:
        if (
            self.busy
            or self._diagnosing
            or self._recovering_adb
            or self._connection_polling
            or (isinstance(self.screen, ModalScreen) and not isinstance(self.screen, ConnectionNotice))
        ):
            return
        self._connection_polling = True
        self._inspect_connection_periodically(self._connection_generation)

    @work(thread=True, exclusive=True, group="connection-monitor")
    def _inspect_connection_periodically(self, generation: int) -> None:
        try:
            result = poll_connection()
        except Exception:
            result = ConnectionStatus("adb_error")
        try:
            self.call_from_thread(self._connection_polled, result, generation)
        except RuntimeError:
            pass

    def _connection_polled(self, result: ConnectionStatus, generation: int | None = None) -> None:
        if generation is not None and generation != self._connection_generation:
            return
        self._connection_polling = False
        if (
            self.busy
            or self._diagnosing
            or self._recovering_adb
            or (isinstance(self.screen, ModalScreen) and not isinstance(self.screen, ConnectionNotice))
        ):
            return
        previous = self._connection_state
        self._connection_state = result
        changed = previous != result
        self._update_device_card(result)

        if result.state == "connected":
            self._set_top_pill("● TERHUBUNG", "")
            if not self.busy and not self._recovering_adb:
                quick = self.query_one("#quickstart", Button)
                quick.remove_class("checking")
                quick.disabled = False
                quick.label = self._idle_quickstart_label()
            if changed and previous and previous.state != "connected":
                self._append_log(f"Perangkat Android terhubung: {', '.join(result.devices)} (✔).", level="OK")
                self.notify("Perangkat Android terhubung. Siap menjalankan pemeriksaan.")
            if isinstance(self.screen, ConnectionNotice):
                self.screen.dismiss(None)

        checked_device_missing = self._offer_check_ready and (
            not self._offer_ready_device or self._offer_ready_device not in result.devices
        )
        if (
            result.state != "connected"
            or checked_device_missing
            or (not self._offer_check_ready and previous and previous.state == "connected" and changed)
        ):
            self._offer_check_ready = False
            self._initial_offer_ready = False
            self._billing_opened_step = None
            self._reinject_step = None
            self._offer_ready_device = None
            self.sequence = False
            self.query_one("#reinject_billing", Button).display = False
            self.query_one("#reinject_billing", Button).disabled = True
            self.query_one("#next", Button).display = False
            self.query_one("#next", Button).disabled = True
            self.query_one("#quickstart", Button).display = True
            self.query_one("#quickstart", Button).label = self._idle_quickstart_label()
            self._update_run_mode()

        # Jika terdeteksi offline / terputus / server error saat polling otomatis,
        # coba pulihkan otomatis dulu sekali (dengan jeda 30 detik agar tidak spam)
        if result.state in ("offline", "disconnected", "adb_error") and changed:
            now = time.monotonic()
            can_auto_recover = (
                generation is not None
                and (now - self._last_auto_adb_recovery) >= 30.0
                and not isinstance(self.screen, ConnectionNotice)
            )
            if can_auto_recover:
                self._last_auto_adb_recovery = now
                self._start_adb_recovery(force_reset=(result.state != "disconnected"), silent=True)
                return

        if result.state in ("missing_adb", "disconnected", "offline", "unauthorized", "adb_error") and changed:
            if isinstance(self.screen, ConnectionNotice):
                return
            if result.state == "missing_adb":
                title = "ADB tidak ditemukan"
                guidance = (
                    "Pasang Android SDK Platform-Tools (di macOS: brew install android-platform-tools) "
                    "lalu hubungkan ulang Android."
                )
            elif result.state == "offline":
                target = result.offline_devices[0] if result.offline_devices else "127.0.0.1:16384"
                title = f"Perangkat ADB offline ({target})"
                guidance = (
                    f"Perangkat {target} nyangkut dalam status offline. Klik 'Perbaiki & Sambungkan' "
                    "untuk menjalankan disconnect, reset ADB server, dan reconnect otomatis."
                )
            elif result.state == "unauthorized":
                title = "Perangkat menunggu izin USB Debugging"
                guidance = "Buka layar Android/MuMu lalu setujui dialog izin USB Debugging."
            elif result.state == "adb_error":
                title = "Server ADB tidak merespons"
                guidance = "Server ADB mungkin nyangkut. Klik 'Perbaiki & Sambungkan' untuk memulai ulang server."
            else:
                title = "Perangkat Android belum terhubung"
                guidance = (
                    "Jalankan MuMuPlayer, aktifkan ADB Debugging, lalu klik 'Perbaiki & Sambungkan' "
                    "untuk menyambungkan 127.0.0.1:16384 secara otomatis."
                )
            self._set_top_pill("! ADB TERPUTUS", "error")
            self.push_screen(ConnectionNotice(title, guidance))

    # ─── Step Picker & Modes ────────────────────────────────────────────

    @on(Button.Pressed, "#advanced_toggle")
    def advanced_pressed(self) -> None:
        self.advanced_visible = not self.advanced_visible
        panel = self.query_one("#workflow_actions", Vertical)
        panel.display = self.advanced_visible
        self.query_one("#advanced_toggle", Button).label = (
            "⚙ Sembunyikan Langkah  −" if self.advanced_visible else "⚙ Pilih Langkah Manual  +"
        )
        target = "#mode_hint" if self.advanced_visible else "#advanced_toggle"
        self.call_after_refresh(lambda: self._reveal_step_control(target))

    def _reveal_step_control(self, selector: str) -> None:
        self.query_one(selector).scroll_visible(animate=False, immediate=True)
        if selector == "#run":
            self.query_one("#results").scroll_relative(y=1, animate=False, immediate=True)

    def toggle_more_modes(self) -> None:
        if self.busy or self._diagnosing or self._recovering_adb:
            return
        self.more_modes_visible = not self.more_modes_visible
        self.query_one("#mode_field", Vertical).display = self.more_modes_visible
        if not self.more_modes_visible:
            self.query_one("#mode", Select).value = "single"
        self._update_run_mode()
        self.call_after_refresh(lambda: self._reveal_step_control("#mode_hint"))

    @on(Select.Changed, "#mode")
    def mode_changed(self, event: Select.Changed) -> None:
        self._update_run_mode()

    @on(Select.Changed, "#step")
    def step_changed(self, event: Select.Changed) -> None:
        if event.value == 99:
            self.query_one("#step", Select).value = self._last_selected_step
            self.toggle_more_modes()
            return
        if isinstance(event.value, int) and event.value in range(5):
            self._last_selected_step = event.value
        self._update_run_mode()

    def _update_run_mode(self) -> None:
        if self.busy or self._recovering_adb:
            return
        if not len(self.query("#mode")) or not len(self.query("#step")):
            return
        mode = self.query_one("#mode", Select).value
        step = self.query_one("#step", Select).value
        if mode == "all":
            if self.query_one("#step", Select).value != 2:
                self.query_one("#step", Select).value = 2
            self.query_one("#step", Select).disabled = True
            self.query_one("#run", Button).label = "▶ Mulai dari Step 2"
            hint = "Setelah tiap langkah, periksa Google Play sebelum lanjut."
        elif mode == "from":
            self.query_one("#step", Select).disabled = False
            self.query_one("#run", Button).label = "▶ Jalankan Langkah Ini"
            hint = (
                "Pilih Step 2–4 untuk menjalankan urutan langkah."
                if step in (0, 1)
                else "Setelah langkah ini selesai, Anda bisa lanjut ke langkah berikutnya."
            )
        else:
            self.query_one("#step", Select).disabled = False
            self.query_one("#run", Button).label = "▶ Jalankan Langkah Ini"
            hint = "Hanya menjalankan satu langkah yang dipilih."
        paid_selected = mode == "all" or (mode in ("single", "from") and step in (2, 3, 4))
        self.query_one("#refresh_offers", Button).display = paid_selected and not self._offer_check_ready
        self.query_one("#run", Button).disabled = paid_selected and not self._offer_check_ready
        if paid_selected and not self._offer_check_ready:
            hint = "Jalankan pemeriksaan Step 1 terlebih dahulu untuk memverifikasi perangkat & akun."
            self.query_one("#run", Button).label = "Perlu Cek Step 1 Dulu"
        elif paid_selected and mode in ("single", "from"):
            hint = "Step 2–4 terbuka untuk sesi ini. Tiap eksekusi tetap memverifikasi akun & penawaran."
        self.query_one("#mode_hint", Static).update(hint)

    def action_toggle_advanced(self) -> None:
        self.advanced_pressed()

    # ─── Workflow Step Indicators & Status Helpers ──────────────────────

    def _set_workflow(self, step: int, state: str) -> None:
        widget = self.query_one(f"#stage_{step}", Static)
        widget.remove_class("step-running", "step-done", "step-review", "step-history")
        marker_map = {
            "running": ("◉", "step-running"),
            "done": ("✓", "step-done"),
            "review": ("!", "step-review"),
            "history": ("↺", "step-history"),
        }
        marker, css_class = marker_map.get(state, ("○", ""))
        if css_class:
            widget.add_class(css_class)
        widget.update(f"{marker}  {step}. {STAGES[step].label}")

    def _set_message(self, value: str) -> None:
        self.query_one("#message", Static).update(value)

    def _set_status(self, value: str) -> None:
        self.query_one("#state", Static).update(value)

    def _selected(self) -> int:
        value = self.query_one("#step", Select).value
        if not isinstance(value, int) or isinstance(value, bool):
            return self._last_selected_step
        return validate_step(value)

    # ─── Stage Confirmation & Instant Auto-Continue Step 2 ──────────────

    def _confirm_stage(
        self,
        step: int,
        sequence: bool,
        previous_verified: bool = False,
        instant: bool = False,
    ) -> None:
        if self.busy or self._diagnosing or self._recovering_adb:
            return
        if step >= 2 and not self._offer_check_ready:
            self._set_status("Jalankan Cek Perangkat & Penawaran dulu")
            self._set_message("Hubungkan Android dan selesaikan pemeriksaan Step 1 sebelum memulai Step 2–4.")
            return
        if (
            step >= 2
            and self._offer_ready_device
            and self._connection_state
            and (
                self._connection_state.state != "connected"
                or self._offer_ready_device not in self._connection_state.devices
            )
        ):
            self._offer_check_ready = False
            self._set_status("Perangkat Android berubah")
            self._set_message(
                "Hubungkan kembali perangkat yang diverifikasi di Step 1 lalu ulangi pemeriksaan."
            )
            return

        # Step 0 & 1 atau Step 2 saat mode instan/auto aktif -> langsung jalan tanpa dialog konfirmasi
        if step < 2 or (step == 2 and (instant or self.auto_step2)):
            self._start(step, sequence)
            return

        if step == 2:
            title = "Mulai checkout awal 12 bulan?"
            message = (
                "Pastikan akun Google Play ini belum memiliki langganan Google One aktif. "
                "Langkah ini dapat menekan tombol Langganan di Google Play."
            )
        else:
            title = f"Mulai Step {step} ({STAGES[step].label})?"
            message = (
                "Paket Google AI Pro harus sudah aktif sebelumnya. Pastikan status langganan "
                "dan tanggal perpanjangan di Google Play sudah sesuai."
            )
        account = self._selected_account or self._offer_ready_account
        if account:
            message += f"\n\nAkun target: {mask_email(account)}."
        if step in (2, 3, 4):
            number = step - 1
            message += (
                f"\n\nVerifikasi kartu {number} dari 3: sekitar US$1 per transaksi "
                "(biasanya berupa penahanan sementara/hold, bukan satu kali tagihan US$3)."
            )
        if previous_verified:
            message = "Pastikan langkah sebelumnya benar-benar telah memperbarui tanggal langganan.\n\n" + message
        if (
            step >= 2
            and step == self.current_step
            and self._last_outcome
            and self._last_outcome.code not in ("listed", "environment_ok", "checkout_requested")
        ):
            message = (
                "PERINGATAN COBA ULANG: Periksa langganan dan transaksi tertunda di Google Play "
                "sebelum mengulang langkah ini.\n\n" + message
            )
        self.push_screen(
            Approval(title, message),
            lambda approved: self._start(step, sequence) if approved else None,
        )

    @on(Button.Pressed, "#quickstart")
    def quickstart_pressed(self) -> None:
        if self._initial_offer_ready and self._offer_check_ready:
            self._confirm_stage(2, True, instant=self.auto_step2)
        else:
            self._auto_continue_armed = self.auto_step2
            self._confirm_stage(1, False)

    @on(Button.Pressed, "#refresh_offers")
    def refresh_offers_pressed(self) -> None:
        self._auto_continue_armed = False
        self._confirm_stage(1, False)

    @on(Button.Pressed, "#run")
    def selected_pressed(self) -> None:
        if self.busy or self._diagnosing or self._recovering_adb:
            return
        self._auto_continue_armed = False
        mode = self.query_one("#mode", Select).value
        if mode == "all":
            self._confirm_stage(2, True)
        elif mode == "from":
            step = self._selected()
            if step < 2:
                self._set_message("Pilih Step 2–4 untuk menjalankan urutan langkah.")
                return
            self._confirm_stage(step, True)
        else:
            step = self._selected()
            if step == 1:
                self._auto_continue_armed = False
            self._confirm_stage(step, False)

    @on(Button.Pressed, "#sequence")
    def sequence_pressed(self) -> None:
        self._auto_continue_armed = False
        step = self._selected()
        if step < 2:
            self._set_message("Pilih Step 2, 3, atau 4 untuk memulai urutan langganan.")
            return
        self._confirm_stage(step, True)

    def action_reinject_billing(self) -> None:
        self.reinject_billing_pressed()

    @on(Button.Pressed, "#reinject_billing")
    def reinject_billing_pressed(self) -> None:
        if self.busy or self._diagnosing or self._recovering_adb:
            return
        target_step = self._reinject_step or (self.current_step if self.current_step in (2, 3, 4) else None)
        if target_step is None or not self._offer_check_ready or not (self._selected_account or self._offer_ready_account):
            self._set_status("Jalankan Cek Step 1 terlebih dahulu")
            self._set_message("Perangkat dan akun Google Play perlu diverifikasi dulu sebelum inject ulang billing.")
            return
        self._append_log(
            f"↻ Menyuntikkan ulang Google Play Billing (Step {target_step} · {STAGES[target_step].label}) agar popup pembayaran muncul kembali...",
            level="STEP",
        )
        self._start(target_step, True, preserve_log=True, reinject=True)

    @on(Button.Pressed, "#next")
    def next_pressed(self) -> None:
        if self.busy or not self.sequence or self.current_step is None:
            return
        if self._last_outcome is None or not self._last_outcome.can_review:
            return
        next_step = self.current_step + 1
        if next_step > 4:
            return
        self._save_history(self._history_account, self.current_step, "user_verified")
        self._confirm_stage(next_step, True, previous_verified=True)

    # ─── Local History ──────────────────────────────────────────────────

    def _show_history(self, account: str) -> None:
        self._render_history(read_history(self.repo, account), f"Riwayat terbaru · {mask_email(account)}")

    def _render_history(self, entries: list, title: str) -> None:
        labels = {
            "started": "Dimulai; hasil belum diverifikasi",
            "billing_opened": "Google Play Billing terbuka — lanjutkan pembayaran",
            "checkout_requested": "Checkout dikirim; cek Google Play",
            "user_verified": "Terverifikasi pengguna di Google Play",
            "listed": "Penawaran dimuat",
            "environment_ok": "Lingkungan siap",
            "cancelled": "Dihentikan pengguna",
            "account_unverified": "Akun belum terverifikasi",
            "wrong_account": "Akun tidak cocok",
        }
        lines = [title]
        if not self.busy:
            for stage in STAGES:
                self._set_workflow(stage.number, "pending")
            for entry in entries:
                if isinstance(entry, dict) and entry.get("step") in range(5):
                    self._set_workflow(entry["step"], "history")
        for entry in reversed(entries[-4:]):
            if isinstance(entry, dict) and isinstance(entry.get("step"), int):
                raw_status = entry.get("status")
                status = labels.get(raw_status, "Berhenti; cek Google Play") if isinstance(raw_status, str) else "Berhenti; cek Google Play"
                lines.append(f"Step {entry['step']} · {status} · {entry.get('at', '')}")
        if not entries:
            lines.append("Belum ada riwayat tersimpan.")
        self.query_one("#history", Static).update("\n".join(lines))

    def _save_history(self, account: str | None, step: int, status: str) -> None:
        try:
            record_history(self.repo, account or "", step, status)
            if account:
                self._show_history(account)
            else:
                self._render_history(read_history(self.repo, ""), "Riwayat terbaru · akun belum terverifikasi")
        except OSError:
            self.notify("Gagal menyimpan riwayat lokal.", severity="warning")

    # ─── Stop / Hentikan Proses Kapan Saja ──────────────────────────────

    def action_stop_current(self) -> None:
        self.stop_pressed()

    @on(Button.Pressed, "#stop")
    def stop_pressed(self) -> None:
        if self._recovering_adb:
            self._adb_cancel_event.set()
            self._set_activity("Menghentikan pemulihan ADB...")
            self.query_one("#stop", Button).disabled = True
            return
        if not self.busy:
            return
        self._auto_continue_armed = False
        self._cancel_active_process()

    def _cancel_active_process(self) -> None:
        if not self.busy or self._cancel_requested:
            return
        self._cancel_requested = True
        self._stop_after_step = True
        step_num = self.current_step
        self._set_top_pill("■ MENGHENTIKAN...", "warn")
        self._set_activity(f"Menghentikan proses Step {step_num}...")
        self._set_status(f"Menghentikan Step {step_num}...")
        if step_num in (0, 1):
            self._set_message("Menghentikan pemeriksaan perangkat & penawaran. Tidak ada checkout yang dijalankan.")
        else:
            self._set_message(
                f"Menghentikan paksa proses Step {step_num}. Periksa status langganan di Google Play "
                "setelah proses berhenti."
            )
        self._append_log(f"Permintaan Hentikan ditekan — menghentikan proses Step {step_num}...", level="WARN")
        self.query_one("#stop", Button).disabled = True
        self.terminate_running_child()

    def _cancel_readonly(self) -> None:
        """Alias kompatibilitas untuk pembatalan proses."""
        self._cancel_active_process()

    @work(thread=True, exclusive=True, group="process-cancel")
    def terminate_running_child(self) -> None:
        child = self._child
        if child is None or child.poll() is not None:
            return
        try:
            if os.name == "nt":
                result = subprocess.run(
                    ["taskkill", "/PID", str(child.pid), "/T", "/F"],
                    capture_output=True,
                    text=True,
                    timeout=8,
                    check=False,
                )
                if result.returncode != 0 and child.poll() is None:
                    child.kill()
            else:
                try:
                    os.killpg(child.pid, signal.SIGTERM)
                except ProcessLookupError:
                    return
                deadline = time.monotonic() + 1.5
                while time.monotonic() < deadline and child.poll() is None:
                    time.sleep(0.1)
                if child.poll() is None:
                    try:
                        os.killpg(child.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
        except (OSError, subprocess.TimeoutExpired) as error:
            try:
                self.call_from_thread(
                    self._append_log,
                    f"Gagal menghentikan proses anak: {error}",
                    level="ERR",
                )
            except RuntimeError:
                pass

    def terminate_readonly_child(self) -> None:
        """Alias kompatibilitas untuk tes yang mem-mock penghentian child."""
        self.terminate_running_child()

    @on(Button.Pressed, "#exit")
    def exit_pressed(self) -> None:
        self.action_quit_safely()

    @on(Button.Pressed, "#manual")
    def manual_pressed(self) -> None:
        child = self._child
        if child and child.stdin:
            try:
                child.stdin.write("\n")
                child.stdin.flush()
                self.query_one("#manual", Button).disabled = True
                self.query_one("#manual", Button).display = False
                self._append_log("Konfirmasi manual dikirim ke proses Android.", level="OK")
            except (OSError, ValueError):
                self._set_message("Gagal mengirim konfirmasi ke Android. Lihat Log Teknis Realtime.")

    @on(Button.Pressed, "#debug")
    def debug_pressed(self) -> None:
        self.action_toggle_debug()

    def action_toggle_debug(self) -> None:
        self.debug_visible = not self.debug_visible
        panel = self.query_one("#console_panel", Vertical)
        log = self.query_one("#debug_log", RichLog)
        panel.display = self.debug_visible
        log.display = self.debug_visible
        if self.debug_visible:
            log.clear()
            last_index = len(self._last_output) - 1
            for index, line in enumerate(self._last_output):
                log.write(line, scroll_end=index == last_index)
            log.refresh(layout=True)
            log.call_after_refresh(
                lambda: log.scroll_end(animate=False, immediate=True, x_axis=False)
                if self.debug_visible
                else None
            )
        self.query_one("#debug", Button).label = (
            "▤ Sembunyikan Log" if self.debug_visible else "▤ Tampilkan Log"
        )

    def action_run_selected(self) -> None:
        self.selected_pressed()

    def action_quit_safely(self) -> None:
        if self._recovering_adb:
            self._adb_cancel_event.set()
            self.exit()
            return
        if not self.busy:
            self.exit()
            return
        self._exit_after_step = True
        self._auto_continue_armed = False
        self._cancel_active_process()
        self._set_message("Menghentikan proses aktif; XToolKit-Diego akan keluar otomatis setelah berhenti.")

    # ─── Stage Execution Pipeline ───────────────────────────────────────

    def _start(self, step: int, sequence: bool, *, preserve_log: bool = False, reinject: bool = False) -> None:
        if self.busy or self._diagnosing or self._recovering_adb:
            return
        if step >= 2 and not self._offer_check_ready:
            self._set_status("Jalankan Cek Perangkat & Penawaran dulu")
            self._set_message("Hubungkan Android dan selesaikan cek Step 1 sebelum memulai Step 2–4.")
            return
        if step >= 2 and (
            not self._offer_ready_device
            or not self._connection_state
            or self._connection_state.state != "connected"
            or self._offer_ready_device not in self._connection_state.devices
        ):
            self._offer_check_ready = False
            self._billing_opened_step = None
            self._reinject_step = None
            self._set_status("Perangkat Android berubah")
            self._set_message(
                "Hubungkan kembali perangkat yang diverifikasi di Step 1 lalu jalankan pemeriksaan ulang."
            )
            return

        self._invalidate_connection_polls()
        self._history_account = self._selected_account or self._offer_ready_account
        self._save_history(self._history_account, step, "started")
        self._checked_device = None
        self._billing_opened_step = None
        self._reinject_mode = step >= 2 and reinject
        if step <= 1:
            self._environment_checked = False
            self._set_workflow(0, "pending")
            self._offer_check_ready = False
            self._initial_offer_ready = False
            self._reinject_step = None
            self._offer_ready_device = None
            self._offer_ready_account = None
        else:
            self._initial_offer_ready = False

        self.busy = True
        self.sequence = sequence
        self.current_step = step
        self._stop_after_step = False
        self._cancel_requested = False
        self._exit_after_step = False
        self._last_outcome = None
        self._verified_account = None
        self._run_output.clear()
        if not preserve_log:
            self._last_output.clear()
            self.query_one("#debug_log", RichLog).clear()
            self.query_one("#log_meta", Static).update("0 baris")
            self.query_one("#offer_view", RichLog).clear()
            self.query_one("#offer_view", RichLog).display = False
            self.query_one("#offers_title", Static).display = False
            dev_card = self.query_one("#device", Static)
            dev_card.tooltip = None
            dev_card.remove_class("online", "offline", "disconnected")
            dev_card.update("○ Perangkat  ·  Mendeteksi...")
            acct_card = self.query_one("#account", Static)
            acct_card.remove_class("verified")
            acct_card.update("○ Akun  ·  Memeriksa...")

        self.query_one("#manual", Button).display = False
        self.query_one("#manual", Button).disabled = True
        self._started_at = time.monotonic()
        self._last_activity_at = self._started_at
        self.query_one("#elapsed", Static).update("⏱ 00:00")
        self.query_one("#status_panel").scroll_home(animate=False)
        self.query_one("#console_panel", Vertical).add_class("active")

        self._lock_action_controls(running_adb=False)
        quick_check = self.query_one("#quickstart", Button)
        quick_check.display = True
        run_button = self.query_one("#run", Button)
        run_button.add_class("checking")
        run_button.label = f"⠋ Step {step}… 0d"
        quick_check.label = "⠋ Cek Penawaran… 0d" if step == 1 else f"⠋ Menjalankan Step {step}… 0d"

        self.query_one("#step_result", Static).update(f"Step {step} · {STAGES[step].label}")
        self._set_workflow(step, "running")
        self._set_top_pill(f"◉ STEP {step} · 0d", "busy")
        self._set_activity(
            f"Memulai Step {step}: {STAGES[step].label} — mengecek koneksi ADB & Android..."
        )
        self._set_status(
            f"Menjalankan Step {step} ({STAGES[step].label}) — pantau layar Android bila ada prompt"
        )
        self._set_message("Proses sedang berjalan secara realtime. Klik 'Hentikan' [x] jika ingin membatalkan.")
        self._append_log(f"▶ Memulai Step {step}: {STAGES[step].label}", level="STEP")
        self.run_stage(step)

    def _execute(self, command: list[str]) -> int:
        child_env = os.environ.copy()
        child_env["PYTHONIOENCODING"] = "utf-8"
        child_env["PYTHONUTF8"] = "1"
        child_env["EPLUS_TUI"] = "1"
        if self._cancel_requested:
            return -1
        options = (
            {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
            if os.name == "nt"
            else {"start_new_session": True}
        )
        with subprocess.Popen(
            command,
            cwd=self.repo,
            env=child_env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
            **options,
        ) as child:
            self._child = child
            if child.stdout:
                for line in child.stdout:
                    try:
                        self.call_from_thread(self._received, line.rstrip("\r\n"))
                    except RuntimeError:
                        return -1
            return child.wait()

    @work(thread=True, exclusive=True)
    def run_stage(self, step: int) -> None:
        try:
            if not self.macos_mode and needs_setup():
                self.call_from_thread(self._set_status, "Menyiapkan lingkungan...")
                self.call_from_thread(
                    self._set_message,
                    "Menyiapkan Frida 16.5.9 dan ADB secara otomatis.",
                )
                setup = self.repo / "setup_env.py"
                if not setup.is_file():
                    raise FileNotFoundError("setup_env.py tidak ditemukan di direktori proyek")
                setup_code = self._execute([sys.executable, str(setup)])
                if self._cancel_requested:
                    self.call_from_thread(
                        self._finished,
                        step,
                        Outcome("cancelled", "Proses dihentikan", "Penyiapan lingkungan dihentikan oleh pengguna."),
                        None,
                    )
                    return
                if setup_code != 0:
                    self.call_from_thread(
                        self._finished,
                        step,
                        Outcome(
                            "setup_failed",
                            "Penyiapan lingkungan belum selesai",
                            "Periksa Log Teknis Realtime di bawah untuk melihat kendala, lalu coba ulang.",
                        ),
                        None,
                    )
                    return

            if self._cancel_requested:
                self.call_from_thread(
                    self._finished,
                    step,
                    Outcome("cancelled", "Proses dihentikan", f"Step {step} dihentikan oleh pengguna."),
                    None,
                )
                return

            started = time.time()
            command = command_for_step(
                step,
                self.repo,
                account=self._selected_account or self._offer_ready_account,
                device=self._offer_ready_device if step >= 2 else None,
                reinject=self._reinject_mode,
            )
            return_code = self._execute(command)
            if self._cancel_requested:
                cancel_msg = (
                    "Pemeriksaan dihentikan oleh pengguna. Tidak ada checkout yang dijalankan."
                    if step <= 1
                    else (
                        f"Proses Step {step} dihentikan oleh pengguna. Periksa status langganan & "
                        "riwayat pembayaran di Google Play untuk memastikan tidak ada transaksi tertunda."
                    )
                )
                self.call_from_thread(
                    self._finished,
                    step,
                    Outcome("cancelled", f"Step {step} dihentikan", cancel_msg),
                    None,
                )
                return

            report = read_fresh_report(
                self.repo / "ultra0-report",
                step,
                started,
                expected_account=self._verified_account,
            )
            result = outcome_for_stage(step, return_code, report)
            if return_code != 0 or result.code in ("missing_report", "tool_error"):
                result = cli_issue_outcome(list(self._run_output), step) or result
            self.call_from_thread(self._finished, step, result, report)
        except Exception as error:
            diagnostic = safe_launch_diagnostic(error)
            self.call_from_thread(self._record_internal_diagnostic, diagnostic)
            result = Outcome(
                "exception",
                "Gagal memulai langkah yang dipilih",
                "Periksa Python, ADB (klik 'Perbaiki ADB'), dan koneksi Android pada Log Teknis Realtime.",
            )
            self.call_from_thread(self._finished, step, result, None)
        finally:
            self._child = None

    def _record_internal_diagnostic(self, diagnostic: str) -> None:
        self._append_log(diagnostic, level="ERR")

    def _received(self, line: str) -> None:
        if not line:
            return
        if line.strip() == "EPLUS_STAGE_DONE:0":
            if self.busy:
                self._environment_checked = True
                self._set_workflow(0, "done")
                self._append_log("Cek lingkungan Android selesai (Step 0 ✔).", level="OK")
            return

        self._run_output.append(line)
        self._last_activity_at = time.monotonic()

        # Tangkap metadata terstruktur sebelum disanitasi ke log
        selected_device = re.search(
            r"\b(?:Connected ADB device:|Device|Perangkat)\s+([A-Za-z0-9._:/-]{1,90})\s*$",
            line,
        )
        if selected_device:
            self._checked_device = selected_device.group(1)
            card = self.query_one("#device", Static)
            card.remove_class("offline", "disconnected")
            card.add_class("online")
            card.update("● Perangkat  ·  " + escape(self._checked_device))
            card.tooltip = self._checked_device

        android = re.fullmatch(
            r"\s*Android\s+([A-Za-z0-9._-]{1,16}) \(SDK ([0-9]{1,4})\), ABI ([A-Za-z0-9_-]{1,24})\s*",
            line,
        )
        if android and self._checked_device:
            release, sdk, abi = android.groups()
            details = f"Android {release} · SDK {sdk} · {abi}"
            card = self.query_one("#device", Static)
            card.update(f"● {details} · {escape(self._checked_device)}")
            card.tooltip = f"{details}\nADB: {self._checked_device}"

        account = re.match(
            r"^\s*(?:Account|Akun)\s+([A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})\s*$",
            line,
        )
        if account:
            self._verified_account = account.group(1).lower()
            acct_card = self.query_one("#account", Static)
            acct_card.add_class("verified")
            acct_card.update("● Akun  ·  " + escape(mask_email(self._verified_account)))

        # Tampilkan di Log Teknis Realtime dengan format cantik & sanitasi aman
        self._append_log(line)

        # Deteksi realtime ketika Step 2–4 berhasil memunculkan Google Play Billing (`code: 0`)
        if self.current_step in (2, 3, 4) and re.search(
            r"Google Play billing flow response:.*['\"]ev['\"]\s*:\s*['\"]launched['\"].*['\"]code['\"]\s*:\s*0\b",
            line,
        ):
            step_num = self.current_step
            self._billing_opened_step = step_num
            self._reinject_step = step_num
            self._set_workflow(step_num, "done")
            self._set_top_pill(f"✓ BILLING STEP {step_num}", "")
            self._set_activity(
                f"Google Play Billing Step {step_num} terbuka — silakan lanjutkan pembayaran di Android!"
            )
            self._set_status(f"✓ Proses Step {step_num} Berhasil — Silakan Lanjutkan Pembayaran")
            self._set_message(
                f"Layar Google Play Billing Step {step_num} ({STAGES[step_num].label}) sudah terbuka di perangkat Android. "
                "Silakan selesaikan pembayaran. Bila popup billing terclose, klik '↻ Inject Ulang Billing' "
                "untuk memunculkannya kembali."
            )
            self._append_log(
                f"Proses Step {step_num} berhasil! Google Play Billing aktif — silakan lanjutkan pembayaran di Android.",
                level="OK",
            )
            self.notify(f"Google Play Billing Step {step_num} terbuka! Silakan lanjutkan pembayaran di Android.")
            return

        lower = line.lower()
        if "restarting google one before querying offers" in lower or "memulai ulang google one" in lower:
            phase = "Memulai ulang Google One sebelum mengambil penawaran..."
        elif "kill-server" in lower or "start-server" in lower or "connect 127.0.0.1" in lower or "offline" in lower:
            phase = "Memulihkan koneksi ADB ke emulator..."
        elif "frida" in lower or "setup" in lower or "injecting" in lower:
            phase = "Menyiapkan Frida & modul inspeksi Android..."
        elif "adb" in lower or "device" in lower or "perangkat" in lower:
            phase = "Memeriksa koneksi perangkat Android..."
        elif "offer" in lower or "billing" in lower or "google one" in lower or "penawaran" in lower:
            phase = "Memeriksa daftar penawaran Google AI..."
        elif "account" in lower or "play store" in lower or "akun" in lower:
            phase = "Memverifikasi akun Google Play Store..."
        elif "subscribe" in lower or "checkout" in lower:
            phase = "Memproses layar checkout Google Play..."
        else:
            phase = sanitize_log_line(line)[:78] or "Proses sedang berjalan..."
        self._set_activity(phase)

        if re.search(r"Action required:|Press Enter to continue|Aksi diperlukan:", line, re.I):
            btn = self.query_one("#manual", Button)
            btn.display = True
            btn.disabled = False
            self._set_message("Selesaikan instruksi pada layar Android, lalu klik 'Aksi di Android Selesai'.")

    def _finished(self, step: int, outcome: Outcome, report: dict | None) -> None:
        self.busy = False
        was_cancelled = self._cancel_requested or outcome.code == "cancelled"
        if (
            step >= 2
            and self._billing_opened_step == step
            and not was_cancelled
            and outcome.code
            not in (
                "billing_opened",
                "account_mismatch",
                "wrong_account",
                "device_mismatch",
                "payment_security_blocked",
                "checkout_security_blocked",
                "ineligible",
                "already_subscribed",
                "purchase_unavailable",
            )
        ):
            outcome = Outcome(
                "billing_opened",
                f"Proses Step {step} berhasil — silakan lanjutkan pembayaran",
                (
                    f"Layar Google Play Billing Step {step} ({STAGES[step].label}) sudah terbuka di perangkat Android. "
                    "Silakan selesaikan pembayaran. Bila popup billing tertutup (terclose), klik tombol "
                    "'↻ Inject Ulang Billing' untuk memunculkannya kembali."
                ),
                can_review=True,
            )
        history_account = self._history_account
        if step == 1:
            history_account = str((report or {}).get("detected_play_account") or "") or history_account
            if self._environment_checked:
                self._save_history(history_account, 0, "environment_ok")
        self._save_history(history_account, step, outcome.code)
        if self._environment_checked:
            self._set_workflow(0, "done")

        if step == 1:
            detected = str((report or {}).get("detected_play_account") or "").strip().lower()
            verified = (self._verified_account or "").strip().lower()
            offers = (report or {}).get("offers")
            self._offer_check_ready = bool(
                outcome.code == "listed"
                and isinstance(offers, list)
                and offers
                and verified
                and (not detected or detected == verified)
                and (not self._selected_account or self._selected_account == verified)
                and self._checked_device
            )
            self._offer_ready_device = self._checked_device if self._offer_check_ready else None
            self._offer_ready_account = verified if self._offer_check_ready else None
            if self._offer_ready_device:
                self._connection_state = ConnectionStatus("connected", (self._offer_ready_device,))
            self._initial_offer_ready = (
                self._offer_check_ready
                and isinstance(offers, list)
                and any(
                    isinstance(offer, dict)
                    and offer.get("id") == "12months-eft"
                    and str(offer.get("micros")) == "0"
                    for offer in offers
                )
            )
        elif step == 0:
            self._offer_check_ready = False
            self._initial_offer_ready = False
            self._offer_ready_device = None
            self._offer_ready_account = None
        elif step >= 2:
            self._initial_offer_ready = False
            account_changed = bool(
                self._verified_account
                and self._offer_ready_account
                and self._verified_account != self._offer_ready_account
            )
            device_changed = bool(
                self._checked_device
                and self._offer_ready_device
                and self._checked_device != self._offer_ready_device
            )
            identity_invalid = outcome.code in (
                "account_mismatch",
                "account_unavailable",
                "account_unverified",
                "wrong_account",
                "play_account_switch_failed",
                "device_missing",
                "device_mismatch",
                "device_ambiguous",
                "adb_missing",
            )
            if account_changed or device_changed or identity_invalid:
                self._offer_check_ready = False
                self._offer_ready_device = None
                self._offer_ready_account = None

        self._last_outcome = outcome
        self.query_one("#manual", Button).display = False
        self.query_one("#manual", Button).disabled = True
        self._unlock_action_controls()
        self._update_run_mode()
        self._started_at = None

        is_ok = outcome.code in ("listed", "environment_ok", "billing_opened")
        self._set_workflow(step, "done" if is_ok else ("pending" if was_cancelled else "review"))
        self._set_top_pill(
            "✓ BILLING SIAP"
            if outcome.code == "billing_opened"
            else ("● SELESAI" if is_ok else ("■ DIHENTIKAN" if was_cancelled else "! PERLU TINJAU")),
            "" if is_ok else "warn",
        )
        self._set_activity(
            "Google Play Billing terbuka — silakan lanjutkan pembayaran di Android."
            if outcome.code == "billing_opened"
            else (
                f"Step {step} selesai — lihat ringkasan di bawah."
                if is_ok
                else (f"Step {step} dihentikan." if was_cancelled else f"Step {step} berhenti: {outcome.title}")
            )
        )
        self._set_status(outcome.title)

        instruction = outcome.instruction
        if step == 1 and outcome.code == "listed" and not self._offer_check_ready:
            instruction += (
                " Pastikan akun aktif di Play Store sudah sesuai lalu jalankan pemeriksaan ulang."
            )
        elif step == 1 and self._offer_check_ready and not self._initial_offer_ready:
            instruction += " Penawaran 12 bulan (12months-eft Rp0/$0) tidak ditemukan pada daftar ini."
        self._set_message(instruction)
        self._append_log(
            f"Step {step} selesai -> {outcome.title}",
            level="OK" if is_ok else ("WARN" if was_cancelled or outcome.code == "checkout_requested" else "ERR"),
        )

        if step == 1:
            self.query_one("#step_result", Static).update(report_summary(report))
            if isinstance(report, dict):
                offer_view = self.query_one("#offer_view", RichLog)
                offer_view.clear()
                for item in offer_explorer_lines(report):
                    offer_view.write(item)
                offer_view.display = True
                self.query_one("#offers_title", Static).display = True
                detected = report.get("detected_play_account")
                if isinstance(detected, str) and detected:
                    acct_card = self.query_one("#account", Static)
                    acct_card.add_class("verified")
                    acct_card.update("● Akun  ·  " + escape(mask_email(detected)))

        if outcome.code == "billing_opened" and step >= 2:
            self._reinject_step = step
        show_reinject = (
            step >= 2
            and self._offer_check_ready
            and (outcome.code == "billing_opened" or self._reinject_step == step)
            and not was_cancelled
        )
        reinject_btn = self.query_one("#reinject_billing", Button)
        reinject_btn.display = show_reinject
        reinject_btn.disabled = not show_reinject
        if show_reinject:
            reinject_btn.label = f"↻ Inject Ulang Step {step}"

        if outcome.can_review and self.sequence and step < 4 and not self._stop_after_step:
            next_btn = self.query_one("#next", Button)
            next_btn.disabled = False
            next_btn.display = True
            next_btn.label = f"✓ Lanjut ke Step {step + 1} →"
            self.query_one("#quickstart", Button).display = False
        elif show_reinject:
            self.query_one("#next", Button).disabled = True
            self.query_one("#next", Button).display = False
            self.query_one("#quickstart", Button).display = True
        else:
            self.query_one("#next", Button).disabled = True
            self.query_one("#next", Button).display = False
            self.query_one("#quickstart", Button).display = True
            self.sequence = False

        if self._exit_after_step:
            self.exit()
            return

        # ─── AUTO-LANJUT INSTAN STEP 1 → STEP 2 (TANPA KONFIRMASI POPUP) ───
        auto_go = self._auto_continue_armed and self.auto_step2
        self._auto_continue_armed = False
        if step == 1 and self._initial_offer_ready and not was_cancelled and not self._stop_after_step:
            if auto_go:
                self._append_log(
                    "Auto-Lanjut aktif: cek perangkat & penawaran selesai (12months-eft Rp0/$0) -> langsung memulai Step 2 (Pro 12 Bulan)...",
                    level="AUTO",
                )
                self.notify("Penawaran 12 bulan siap — otomatis lanjut ke Step 2!", severity="information")
                self._start(2, True, preserve_log=True)
                return
            self.push_screen(
                CheckComplete(),
                lambda proceed: self._confirm_stage(2, True, instant=self.auto_step2) if proceed else None,
            )
            return

        if step == 1 and outcome.code == "listed" and not self._initial_offer_ready:
            self.push_screen(SetupNotice("Tinjau Hasil Cek Penawaran", instruction))
            return
        if step <= 1 and outcome.code not in ("listed", "environment_ok", "cancelled"):
            self.push_screen(SetupNotice(outcome.title, outcome.instruction))
            return
        if outcome.code == "billing_opened":
            self.notify(f"Step {step} berhasil — lanjutkan pembayaran di Android. Klik 'Inject Ulang Step {step}' bila tertutup.")
        elif outcome.code == "checkout_requested":
            self.notify("Checkout dikirim — periksa status langganan di Google Play.", severity="warning")
        elif outcome.code not in ("listed", "environment_ok", "cancelled"):
            self.notify(
                "Langkah berhenti — cek status & tagihan di Google Play sebelum mengulang.",
                severity="warning",
            )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Antarmuka Textual XToolKit-Diego")
    parser.add_argument("--step", type=int, default=1)
    parser.add_argument("--sequence", action="store_true")
    parser.add_argument("--debug", action="store_true", default=True, help="Tampilkan Log Teknis Realtime secara otomatis")
    parser.add_argument("--no-debug", dest="debug", action="store_false", help="Sembunyikan Log Teknis Realtime saat awal")
    parser.add_argument("--manual-step2", action="store_true", help="Nonaktifkan auto-lanjut Step 2 otomatis")
    args = parser.parse_args(argv)
    try:
        selected = validate_step(args.step)
    except ValueError as exc:
        parser.error(str(exc))
    GoogleAITUI(
        repo=Path(__file__).resolve().parent,
        selected_step=selected,
        start_sequence=args.sequence,
        initial_debug=args.debug,
        auto_step2=not args.manual_step2,
    ).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
