import queue
import threading
import tkinter as tk
import os
from tkinter.scrolledtext import ScrolledText

from assistant_app.api_client import AssistantAPIError, AssistantClient
from assistant_app.settings import Settings
from assistant_app.voice import listen_hindi, speak_hindi, start_voice_task


SYSTEM_PROMPT = (
    "You are Jarvis, a helpful personal assistant. Reply in Hindi by default, using "
    "Devanagari. Use another language when the user requests it. Be clear, practical, and honest. "
    "Ask a brief clarifying question when needed. You cannot access the user's "
    "computer or perform actions outside this chat, so never claim that you did."
)


class AssistantWindow:
    def __init__(
        self,
        root: tk.Tk,
        client: AssistantClient | None,
        settings_error: str | None = None,
    ) -> None:
        self._root = root
        self._client = client
        self._history: list[dict[str, str]] = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]
        self._responses: queue.Queue[tuple[str, str, int, str]] = queue.Queue()
        self._phase = "idle"
        self._voice_mode = False
        self._voice_session_id = 0
        self._voice_cancel: threading.Event | None = None
        self._voice_button: tk.Button | None = None

        root.title("Jarvis AI")
        root.geometry("780x640")
        root.minsize(540, 420)
        root.configure(bg="#111827")

        header = tk.Frame(root, bg="#111827", padx=20, pady=16)
        header.pack(fill="x")
        tk.Label(
            header,
            text="JARVIS AI",
            font=("Segoe UI", 18, "bold"),
            fg="#f9fafb",
            bg="#111827",
        ).pack(anchor="w")
        tk.Label(
            header,
            text="Your personal AI assistant",
            font=("Segoe UI", 10),
            fg="#9ca3af",
            bg="#111827",
        ).pack(anchor="w", pady=(2, 0))

        self._transcript = ScrolledText(
            root,
            wrap="word",
            state="disabled",
            padx=14,
            pady=12,
            font=("Segoe UI", 10),
            bg="#1f2937",
            fg="#f3f4f6",
            insertbackground="#f3f4f6",
            relief="flat",
            borderwidth=0,
        )
        self._transcript.pack(fill="both", expand=True, padx=16, pady=(0, 10))
        self._transcript.tag_configure("speaker", foreground="#60a5fa", font=("Segoe UI", 10, "bold"))
        self._transcript.tag_configure("error", foreground="#fca5a5")

        compose = tk.Frame(root, bg="#111827", padx=16, pady=8)
        compose.pack(fill="x")
        self._input = tk.Text(
            compose,
            height=3,
            wrap="word",
            font=("Segoe UI", 10),
            bg="#1f2937",
            fg="#f9fafb",
            insertbackground="#f9fafb",
            relief="flat",
            padx=10,
            pady=8,
        )
        self._input.pack(side="left", fill="both", expand=True)
        self._input.bind("<Return>", self._on_return)
        self._input.bind("<Shift-Return>", self._on_shift_return)

        self._send_button = tk.Button(
            compose,
            text="Send",
            command=self._send_message,
            font=("Segoe UI", 10, "bold"),
            bg="#2563eb",
            fg="white",
            activebackground="#1d4ed8",
            activeforeground="white",
            relief="flat",
            padx=18,
            pady=10,
            cursor="hand2",
        )
        self._voice_button = tk.Button(
            compose,
            text="Voice chat",
            command=self._toggle_voice,
            font=("Segoe UI", 10, "bold"),
            bg="#374151",
            fg="white",
            activebackground="#4b5563",
            activeforeground="white",
            relief="flat",
            padx=14,
            pady=10,
            cursor="hand2",
        )
        self._voice_button.pack(side="left", padx=(8, 0), anchor="s")
        self._send_button.pack(side="left", padx=(8, 0), anchor="s")
        if client is None:
            self._send_button.configure(state="disabled")
            self._voice_button.configure(state="disabled")

        self._status = tk.Label(
            root,
            text="",
            anchor="w",
            font=("Segoe UI", 9),
            fg="#9ca3af",
            bg="#111827",
            padx=18,
            pady=6,
        )
        self._status.pack(fill="x")
        if settings_error:
            self._show_message("Jarvis", settings_error, is_error=True)
            self._status.configure(text="Check your AI API configuration.")
        else:
            self._show_message("Jarvis", "Hi! What can I help you with?")

        self._input.focus_set()
        self._root.after(100, self._process_responses)

    def _on_return(self, _event: tk.Event) -> str:
        self._send_message()
        return "break"

    def _on_shift_return(self, _event: tk.Event) -> str:
        self._input.insert("insert", "\n")
        return "break"

    def _send_message(self) -> None:
        if self._phase != "idle" or self._client is None:
            return
        text = self._input.get("1.0", "end").strip()
        if not text:
            return

        self._input.delete("1.0", "end")
        self._show_message("You", text)
        self._submit_message(text)

    def _submit_message(self, text: str, voice_session_id: int = -1) -> None:
        if self._client is None:
            return
        request_history = [*self._history, {"role": "user", "content": text}]
        self._phase = "thinking"
        self._update_controls()
        self._status.configure(text="Jarvis is thinking...")
        threading.Thread(
            target=self._request_answer,
            args=(request_history, text, voice_session_id),
            daemon=True,
        ).start()

    def _toggle_voice(self) -> None:
        if self._voice_mode:
            self._stop_voice()
            return
        if self._phase != "idle" or self._client is None:
            return
        self._voice_mode = True
        self._voice_session_id += 1
        self._voice_cancel = threading.Event()
        self._start_listening()

    def _start_listening(self) -> None:
        if not self._voice_mode or self._voice_cancel is None:
            return
        self._phase = "listening"
        self._update_controls()
        self._status.configure(
            text="Listening in Hindi. Press Stop voice to end the conversation."
        )
        start_voice_task(
            listen_hindi,
            self._responses,
            "voice",
            self._voice_session_id,
            self._voice_cancel,
        )

    def _stop_voice(self, force_idle: bool = False) -> None:
        self._voice_mode = False
        self._voice_session_id += 1
        if self._voice_cancel is not None:
            self._voice_cancel.set()
            self._voice_cancel = None
        if force_idle or self._phase in {"listening", "speaking"}:
            self._phase = "idle"
        self._update_controls()
        if self._phase == "idle":
            self._status.configure(text="Voice chat stopped.")

    def _request_answer(
        self,
        request_history: list[dict[str, str]],
        text: str,
        voice_session_id: int,
    ) -> None:
        try:
            if self._client is None:
                raise AssistantAPIError("The AI client is not configured.")
            answer = self._client.complete(request_history)
        except AssistantAPIError as error:
            self._responses.put(("error", str(error), voice_session_id, text))
        else:
            self._responses.put(("answer", answer, voice_session_id, text))

    def _process_responses(self) -> None:
        while True:
            try:
                kind, content, session_id, user_text = self._responses.get_nowait()
            except queue.Empty:
                break
            if kind in {"voice", "voice_error", "speech", "speech_error"}:
                if session_id != self._voice_session_id or not self._voice_mode:
                    continue
            if kind == "answer":
                self._history.extend(
                    [
                        {"role": "user", "content": user_text},
                        {"role": "assistant", "content": content},
                    ]
                )
                is_voice_reply = (
                    self._voice_mode and session_id == self._voice_session_id
                )
                if is_voice_reply:
                    self._phase = "speaking"
                    self._update_controls()
                    self._status.configure(text="Jarvis is speaking...")
                    start_voice_task(
                        speak_hindi,
                        self._responses,
                        "speech",
                        session_id,
                        content,
                        self._voice_cancel,
                        os.environ.get("JARVIS_TTS", "google").strip().lower(),
                    )
                else:
                    self._show_message("Jarvis", content)
                    self._phase = "idle"
                    self._update_controls()
                    self._status.configure(text="")
            elif kind == "voice":
                self._submit_message(content, session_id)
            elif kind == "speech":
                self._start_listening()
            elif kind in {"voice_error", "speech_error"}:
                self._show_message("Voice", content, is_error=True)
                self._stop_voice(force_idle=True)
                self._status.configure(text="Voice chat stopped. Check the message above.")
            else:
                self._show_message("Jarvis", content, is_error=True)
                if self._voice_mode and session_id == self._voice_session_id:
                    self._stop_voice(force_idle=True)
                else:
                    self._phase = "idle"
                    self._update_controls()
                self._status.configure(text="The request failed. You can try again.")
        self._root.after(100, self._process_responses)

    def _update_controls(self) -> None:
        if self._client is None:
            self._send_button.configure(state="disabled")
            if self._voice_button is not None:
                self._voice_button.configure(state="disabled", text="Voice chat")
            return
        busy = self._phase != "idle"
        self._send_button.configure(state="disabled" if busy else "normal")
        if self._voice_button is not None:
            self._voice_button.configure(
                state="normal" if self._voice_mode or not busy else "disabled",
                text="Stop voice" if self._voice_mode else "Voice chat",
            )

    def _show_message(self, speaker: str, message: str, is_error: bool = False) -> None:
        self._transcript.configure(state="normal")
        self._transcript.insert("end", f"{speaker}\n", "speaker")
        if is_error:
            self._transcript.insert("end", f"{message}\n\n", "error")
        else:
            self._transcript.insert("end", f"{message}\n\n")
        self._transcript.configure(state="disabled")
        self._transcript.see("end")


def run() -> None:
    root = tk.Tk()
    try:
        settings = Settings.from_environment()
        client = AssistantClient(settings)
        settings_error = None
    except ValueError as error:
        settings_error = str(error)
        client = None

    AssistantWindow(root, client, settings_error)
    root.mainloop()
