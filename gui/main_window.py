from __future__ import annotations

import logging
logger = logging.getLogger("protokolist.gui")
import gc
import json
import os
import threading
import time
import tempfile
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk
import soundfile as sf

from analysis_engine.text_postprocessor import TextPostprocessor
from analysis_engine.protocol_analyzer import (
    build_summary,
    extract_decisions,
    extract_tasks,
)
from audio.devices import list_input_devices
from audio.audio_processing import enhance_speech
from audio.recorder import Recorder
from export.excel_export import export_tasks_excel
from export.word_export import export_word
from models.meeting import MeetingData, Task
from storage.archive_search import SearchResult, search_archive
from storage.project import MeetingProject
from whisper_engine.transcriber import (
    Transcriber,
    format_segments,
)


class ProtokolistApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()

        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")

        self.title("Протоколист 4.0 — офисный CPU")
        self.geometry("1280x860")
        self.minsize(1080, 720)

        self.config_data = self._load_config()
        self.recorder = Recorder(
            sample_rate=int(self.config_data.get("sample_rate", 16000))
        )
        self.transcriber: Transcriber | None = None
        self.loaded_model_name: str | None = None
        self.model_loading = False
        self.project: MeetingProject | None = None
        self.recording_started_at: float | None = None
        self.timer_job: str | None = None
        self.level_job: str | None = None
        self.autosave_job: str | None = None
        self.tasks: list[Task] = []
        self.device_map: dict[str, int] = {}
        self.search_results: list[SearchResult] = []
        self.live_thread: threading.Thread | None = None
        self.live_stop_event = threading.Event()
        self.live_processed_seconds = 0.0
        self.current_audio_path: Path | None = None
        self.live_transcription_active = False
        self.live_context_text = ""
        self.live_first_chunk = True
        self.final_refine_running = False
        self.postprocessor = TextPostprocessor()

        self._build_ui()
        self._refresh_devices()
        self._schedule_autosave()
        self.after(200, self._load_whisper_async)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _load_config(self) -> dict:
        path = Path("config.json")
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))

    def _save_config(self) -> None:
        Path("config.json").write_text(
            json.dumps(self.config_data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _build_ui(self) -> None:
        header = ctk.CTkFrame(self)
        header.pack(fill="x", padx=18, pady=(14, 8))

        ctk.CTkLabel(
            header,
            text="ПРОТОКОЛИСТ 4.0",
            font=("Arial", 28, "bold"),
        ).pack(side="left", padx=15, pady=12)

        self.timer_label = ctk.CTkLabel(
            header,
            text="00:00:00",
            font=("Consolas", 24, "bold"),
        )
        self.timer_label.pack(side="right", padx=18)

        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(fill="both", expand=True, padx=18, pady=8)

        self.record_tab = self.tabview.add("Запись")
        self.protocol_tab = self.tabview.add("Протокол")
        self.tasks_tab = self.tabview.add("Поручения")
        self.archive_tab = self.tabview.add("Архив и поиск")

        self._build_record_tab()
        self._build_protocol_tab()
        self._build_tasks_tab()
        self._build_archive_tab()

        bottom = ctk.CTkFrame(self)
        bottom.pack(fill="x", padx=18, pady=(4, 12))

        self.level_bar = ctk.CTkProgressBar(bottom, width=180)
        self.level_bar.set(0)
        self.level_bar.pack(side="left", padx=10, pady=10)

        self.status_label = ctk.CTkLabel(
            bottom,
            text="Статус: загрузка модели Whisper...",
            anchor="w",
        )
        self.status_label.pack(side="left", padx=10)

        ctk.CTkButton(
            bottom,
            text="Открыть папку проекта",
            command=self.open_project_folder,
            width=170,
        ).pack(side="right", padx=10)

    def _build_record_tab(self) -> None:
        form = ctk.CTkFrame(self.record_tab)
        form.pack(fill="x", padx=12, pady=10)
        form.grid_columnconfigure(1, weight=1)
        form.grid_columnconfigure(3, weight=1)

        self.title_entry = self._entry_row(form, 0, 0, "Совещание")
        self.chairman_entry = self._entry_row(form, 0, 2, "Председатель")
        self.secretary_entry = self._entry_row(form, 1, 0, "Секретарь")
        self.place_entry = self._entry_row(form, 1, 2, "Место")

        ctk.CTkLabel(form, text="Микрофон").grid(
            row=2, column=0, padx=(12, 6), pady=10, sticky="w"
        )
        self.device_combo = ctk.CTkComboBox(form, values=["По умолчанию"])
        self.device_combo.grid(
            row=2, column=1, columnspan=3,
            padx=(0, 12), pady=10, sticky="ew"
        )

        ctk.CTkLabel(form, text="Живая модель").grid(
            row=3, column=0, padx=(12, 6), pady=10, sticky="w"
        )
        self.model_combo = ctk.CTkComboBox(
            form,
            values=["small", "turbo", "medium"],
            state="readonly",
        )
        self.model_combo.grid(
            row=3, column=1, padx=(0, 12), pady=10, sticky="ew"
        )
        self.model_combo.set(self.config_data.get("model", "medium"))

        self.load_model_button = ctk.CTkButton(
            form,
            text="Загрузить модель",
            command=self.change_model,
        )
        self.load_model_button.grid(
            row=3, column=2, padx=(12, 6), pady=10, sticky="ew"
        )

        self.model_status_label = ctk.CTkLabel(
            form,
            text="Модель ещё не загружена",
            anchor="w",
        )
        self.model_status_label.grid(
            row=3, column=3, padx=(0, 12), pady=10, sticky="ew"
        )

        ctk.CTkLabel(form, text="Словарь терминов").grid(
            row=4, column=0, padx=(12, 6), pady=10, sticky="w"
        )
        self.prompt_entry = ctk.CTkEntry(form)
        self.prompt_entry.grid(
            row=4, column=1, columnspan=3,
            padx=(0, 12), pady=10, sticky="ew"
        )
        self.prompt_entry.insert(
            0,
            self.config_data.get("initial_prompt", "")
        )

        ctk.CTkLabel(form, text="Окно живого распознавания").grid(
            row=5, column=0, padx=(12, 6), pady=10, sticky="w"
        )
        self.chunk_combo = ctk.CTkComboBox(
            form, values=["10", "12", "15", "20"], state="readonly"
        )
        self.chunk_combo.grid(
            row=5, column=1, padx=(0, 12), pady=10, sticky="ew"
        )
        self.chunk_combo.set(str(self.config_data.get("live_chunk_seconds", 15)))

        self.live_switch = ctk.CTkSwitch(
            form, text="Показывать черновой текст во время записи"
        )
        self.live_switch.grid(
            row=5, column=2, columnspan=2, padx=12, pady=10, sticky="w"
        )
        self.live_switch.select()

        ctk.CTkLabel(form, text="Финальная модель").grid(
            row=6, column=0, padx=(12, 6), pady=10, sticky="w"
        )
        self.final_model_combo = ctk.CTkComboBox(
            form,
            values=["medium", "turbo"],
            state="readonly",
        )
        self.final_model_combo.grid(
            row=6, column=1, padx=(0, 12), pady=10, sticky="ew"
        )
        self.final_model_combo.set(
            self.config_data.get("final_model", "large-v3")
        )

        self.auto_refine_switch = ctk.CTkSwitch(
            form,
            text="После остановки автоматически сделать точную расшифровку",
        )
        self.auto_refine_switch.grid(
            row=6, column=2, columnspan=2, padx=12, pady=10, sticky="w"
        )
        if self.config_data.get("auto_final_refine", True):
            self.auto_refine_switch.select()

        self.enhance_switch = ctk.CTkSwitch(
            form,
            text="Улучшать звук перед распознаванием",
        )
        self.enhance_switch.grid(
            row=7, column=0, columnspan=2, padx=12, pady=10, sticky="w"
        )
        if self.config_data.get("enhance_audio", True):
            self.enhance_switch.select()

        ctk.CTkLabel(
            form,
            text="Для качества используется окно 10–20 с с перекрытием; "
                 "поэтому задержка будет больше пары секунд.",
            anchor="w",
        ).grid(
            row=7, column=2, columnspan=2,
            padx=12, pady=10, sticky="ew"
        )

        self.dictionary_button = ctk.CTkButton(
            form,
            text="Открыть корпоративный словарь",
            command=self.open_dictionary_file,
        )
        self.dictionary_button.grid(
            row=8, column=0, columnspan=2,
            padx=12, pady=(2, 10), sticky="w"
        )

        self.correction_switch = ctk.CTkSwitch(
            form,
            text="Исправлять текст по корпоративному словарю",
        )
        self.correction_switch.grid(
            row=8, column=2, columnspan=2,
            padx=12, pady=(2, 10), sticky="w"
        )
        if self.config_data.get("enable_dictionary_correction", True):
            self.correction_switch.select()

        toolbar = ctk.CTkFrame(self.record_tab)
        toolbar.pack(fill="x", padx=12, pady=6)

        self.start_button = ctk.CTkButton(
            toolbar,
            text="🎤 Начать запись",
            command=self.start_recording,
            state="disabled",
        )
        self.start_button.pack(side="left", padx=7, pady=9)

        self.stop_button = ctk.CTkButton(
            toolbar,
            text="⏹ Остановить",
            command=self.stop_recording,
            state="disabled",
        )
        self.stop_button.pack(side="left", padx=7, pady=9)

        ctk.CTkButton(
            toolbar,
            text="Сохранить проект",
            command=self.save_project,
        ).pack(side="left", padx=7)

        ctk.CTkButton(
            toolbar,
            text="Открыть проект",
            command=self.open_project,
        ).pack(side="left", padx=7)

        ctk.CTkButton(
            toolbar,
            text="Удалить аудио",
            command=self.delete_audio,
        ).pack(side="right", padx=7)

        ctk.CTkButton(
            toolbar,
            text="Уточнить по полному файлу",
            command=self.retranscribe_full_audio,
        ).pack(side="right", padx=7)

        ctk.CTkButton(
            toolbar,
            text="Сформировать черновик протокола",
            command=self.analyze_transcript,
        ).pack(side="right", padx=7)

        ctk.CTkLabel(
            self.record_tab,
            text="Стенограмма с временными метками",
            font=("Arial", 18, "bold"),
        ).pack(anchor="w", padx=18, pady=(8, 0))

        self.transcript_box = ctk.CTkTextbox(
            self.record_tab,
            wrap="word",
        )
        self.transcript_box.pack(
            fill="both", expand=True, padx=12, pady=10
        )

    def _build_protocol_tab(self) -> None:
        self.protocol_tab.grid_columnconfigure(0, weight=1)
        self.protocol_tab.grid_columnconfigure(1, weight=1)
        self.protocol_tab.grid_rowconfigure(1, weight=1)
        self.protocol_tab.grid_rowconfigure(3, weight=1)

        ctk.CTkLabel(
            self.protocol_tab,
            text="Краткое резюме",
            font=("Arial", 16, "bold"),
        ).grid(row=0, column=0, padx=12, pady=(12, 4), sticky="w")

        ctk.CTkLabel(
            self.protocol_tab,
            text="Повестка",
            font=("Arial", 16, "bold"),
        ).grid(row=0, column=1, padx=12, pady=(12, 4), sticky="w")

        self.summary_box = ctk.CTkTextbox(self.protocol_tab, wrap="word")
        self.summary_box.grid(
            row=1, column=0, padx=12, pady=5, sticky="nsew"
        )

        self.agenda_box = ctk.CTkTextbox(self.protocol_tab, wrap="word")
        self.agenda_box.grid(
            row=1, column=1, padx=12, pady=5, sticky="nsew"
        )

        ctk.CTkLabel(
            self.protocol_tab,
            text="Ход обсуждения",
            font=("Arial", 16, "bold"),
        ).grid(row=2, column=0, padx=12, pady=(8, 4), sticky="w")

        ctk.CTkLabel(
            self.protocol_tab,
            text="Принятые решения",
            font=("Arial", 16, "bold"),
        ).grid(row=2, column=1, padx=12, pady=(8, 4), sticky="w")

        self.discussion_box = ctk.CTkTextbox(self.protocol_tab, wrap="word")
        self.discussion_box.grid(
            row=3, column=0, padx=12, pady=5, sticky="nsew"
        )

        self.decisions_box = ctk.CTkTextbox(self.protocol_tab, wrap="word")
        self.decisions_box.grid(
            row=3, column=1, padx=12, pady=5, sticky="nsew"
        )

        footer = ctk.CTkFrame(self.protocol_tab)
        footer.grid(
            row=4, column=0, columnspan=2,
            padx=12, pady=12, sticky="ew"
        )

        ctk.CTkButton(
            footer,
            text="Экспорт Word",
            command=self.export_word_document,
        ).pack(side="right", padx=8, pady=8)

    def _build_tasks_tab(self) -> None:
        editor = ctk.CTkFrame(self.tasks_tab)
        editor.pack(fill="x", padx=12, pady=10)
        editor.grid_columnconfigure(1, weight=1)
        editor.grid_columnconfigure(3, weight=1)

        self.responsible_entry = self._entry_row(
            editor, 0, 0, "Ответственный"
        )
        self.deadline_entry = self._entry_row(
            editor, 0, 2, "Срок"
        )

        ctk.CTkLabel(editor, text="Поручение").grid(
            row=1, column=0, padx=(12, 6), pady=10, sticky="w"
        )
        self.task_entry = ctk.CTkEntry(editor)
        self.task_entry.grid(
            row=1, column=1, columnspan=3,
            padx=(0, 12), pady=10, sticky="ew"
        )

        self.status_combo = ctk.CTkComboBox(
            editor,
            values=["Не начато", "В работе", "Выполнено", "Отменено"],
        )
        self.status_combo.set("Не начато")
        self.status_combo.grid(
            row=2, column=0, padx=12, pady=8, sticky="ew"
        )

        ctk.CTkButton(
            editor,
            text="Добавить поручение",
            command=self.add_task,
        ).grid(row=2, column=1, padx=8, pady=8, sticky="w")

        ctk.CTkButton(
            editor,
            text="Удалить последнее",
            command=self.remove_last_task,
        ).grid(row=2, column=2, padx=8, pady=8, sticky="w")

        ctk.CTkButton(
            editor,
            text="Экспорт Excel",
            command=self.export_tasks,
        ).grid(row=2, column=3, padx=12, pady=8, sticky="e")

        self.tasks_box = ctk.CTkTextbox(self.tasks_tab, wrap="word")
        self.tasks_box.pack(fill="both", expand=True, padx=12, pady=10)
        self._render_tasks()

    def _build_archive_tab(self) -> None:
        search_bar = ctk.CTkFrame(self.archive_tab)
        search_bar.pack(fill="x", padx=12, pady=10)

        self.search_entry = ctk.CTkEntry(
            search_bar,
            placeholder_text="Например: H760, RDW, Иванов, комплектующие",
        )
        self.search_entry.pack(side="left", fill="x", expand=True, padx=8, pady=8)

        ctk.CTkButton(
            search_bar,
            text="Найти",
            command=self.search_meetings,
            width=110,
        ).pack(side="left", padx=8)

        ctk.CTkButton(
            search_bar,
            text="Открыть выбранный",
            command=self.open_selected_search_result,
            width=160,
        ).pack(side="left", padx=8)

        self.search_box = ctk.CTkTextbox(self.archive_tab, wrap="word")
        self.search_box.pack(fill="both", expand=True, padx=12, pady=10)

        self.result_combo = ctk.CTkComboBox(
            self.archive_tab,
            values=["Нет результатов"],
            state="readonly",
        )
        self.result_combo.pack(fill="x", padx=12, pady=(0, 12))
        self.result_combo.set("Нет результатов")

    def _entry_row(self, parent, row: int, column: int, label: str):
        ctk.CTkLabel(parent, text=label).grid(
            row=row, column=column,
            padx=(12, 6), pady=10, sticky="w"
        )
        entry = ctk.CTkEntry(parent)
        entry.grid(
            row=row, column=column + 1,
            padx=(0, 12), pady=10, sticky="ew"
        )
        return entry

    def _refresh_devices(self) -> None:
        devices = list_input_devices()
        self.device_map = {"По умолчанию": -1}
        names = ["По умолчанию"]

        for index, name in devices:
            label = f"{index}: {name}"
            self.device_map[label] = index
            names.append(label)

        self.device_combo.configure(values=names)
        self.device_combo.set("По умолчанию")

    def _load_whisper_async(self) -> None:
        self._start_model_loading(self.config_data.get("model", "medium"))

    def change_model(self) -> None:
        if self.recorder.recording:
            messagebox.showwarning(
                "Модель Whisper",
                "Нельзя менять модель во время записи.",
            )
            return

        model_name = self.model_combo.get().strip()
        if not model_name:
            return

        if model_name == self.loaded_model_name and self.transcriber is not None:
            messagebox.showinfo(
                "Модель Whisper",
                f"Модель {model_name} уже загружена.",
            )
            return

        self._start_model_loading(model_name)

    def _start_model_loading(self, model_name: str) -> None:
        if self.model_loading:
            return

        self.model_loading = True
        self.start_button.configure(state="disabled")
        self.load_model_button.configure(state="disabled")
        self.model_status_label.configure(text=f"Загрузка: {model_name}...")
        self.status_label.configure(
            text=f"Статус: загрузка модели {model_name}..."
        )
        threading.Thread(
            target=self._load_whisper,
            args=(model_name,),
            daemon=True,
        ).start()

    def _load_whisper(self, model_name: str) -> None:
        try:
            old_transcriber = self.transcriber
            new_transcriber = Transcriber(
                model_name=model_name,
                device=self.config_data.get("device", "cpu"),
                compute_type=self.config_data.get("compute_type", "int8"),
                cpu_threads=int(self.config_data.get("cpu_threads", 4)),
                num_workers=int(self.config_data.get("num_workers", 1)),
            )
            self.transcriber = new_transcriber
            self.loaded_model_name = model_name
            self.config_data["model"] = model_name
            self._save_config()
            del old_transcriber
            gc.collect()
            self.after(0, lambda: self._whisper_ready(model_name))
        except Exception as exc:
            self.after(
                0,
                lambda error=exc: self._model_load_failed(error),
            )

    def _whisper_ready(self, model_name: str) -> None:
        logger.info("Модель Whisper загружена: %s", model_name)
        self.model_loading = False
        self.start_button.configure(state="normal")
        self.load_model_button.configure(state="normal")
        self.model_status_label.configure(text=f"Загружена: {model_name}")
        self.status_label.configure(
            text=f"Статус: готов к работе — модель {model_name}"
        )

    def _model_load_failed(self, exc: Exception) -> None:
        self.model_loading = False
        self.load_model_button.configure(state="normal")
        if self.transcriber is not None:
            self.start_button.configure(state="normal")
        self.model_status_label.configure(text="Ошибка загрузки")
        self._show_error("Whisper", exc)

    def start_recording(self) -> None:
        
        if self.recorder.recording:
            return

        try:
            if self.project is None:
                self.project = MeetingProject(self.title_entry.get())

            selected = self.device_combo.get()
            device_index = self.device_map.get(selected, -1)
            self.recorder.set_device(None if device_index == -1 else device_index)

            self.config_data["live_chunk_seconds"] = int(self.chunk_combo.get())
            self.config_data["final_model"] = self.final_model_combo.get()
            self.config_data["auto_final_refine"] = bool(self.auto_refine_switch.get())
            self.config_data["enhance_audio"] = bool(self.enhance_switch.get())
            self.config_data["enable_dictionary_correction"] = bool(
                self.correction_switch.get()
            )
            self._save_config()

            self.transcript_box.delete("1.0", "end")
            self.live_processed_seconds = 0.0
            self.live_context_text = ""
            self.live_first_chunk = True
            self.current_audio_path = None
            self.live_stop_event.clear()
            self.live_transcription_active = bool(self.live_switch.get())

            self.recorder.start()
            logger.info(
                "Начало записи. Совещание=%r, микрофон=%r",
                self.title_entry.get().strip(),
                self.device_combo.get(),
            )
            self.recording_started_at = time.time()

            if self.live_transcription_active:
                self.live_thread = threading.Thread(
                    target=self._live_transcription_loop,
                    daemon=True,
                )
                self.live_thread.start()

            self.start_button.configure(state="disabled")
            self.stop_button.configure(state="normal")
            mode = "живое распознавание" if self.live_transcription_active else "запись"
            self.status_label.configure(text=f"Статус: 🔴 {mode}...")
            self._update_timer()
            self._update_level()
        except Exception as exc:
            self._show_error("Запись", exc)

    def stop_recording(self) -> None:
        if not self.recorder.recording or self.project is None:
            return

        try:
            self.current_audio_path = self.recorder.stop(self.project.folder)
            logger.info("Запись остановлена. Файл=%s", audio_path)
            self.live_stop_event.set()
            self.stop_button.configure(state="disabled")
            self._stop_timer_and_level()

            if self.live_transcription_active:
                self.status_label.configure(
                    text="Статус: обработка последнего фрагмента..."
                )
            else:
                self.status_label.configure(
                    text="Статус: высокоточная расшифровка файла..."
                )
                self._start_high_accuracy_refinement(
                    self.current_audio_path
                )
        except Exception as exc:
            self._show_error("Остановка записи", exc)
            self.start_button.configure(state="normal")

    def _live_transcription_loop(self) -> None:
        try:
            chunk_seconds = int(self.config_data.get("live_chunk_seconds", 15))
            overlap_seconds = float(
                self.config_data.get("live_overlap_seconds", 3)
            )

            while True:
                should_finish = self.live_stop_event.is_set()
                duration = self.recorder.live_buffer_duration()

                enough_for_window = duration >= chunk_seconds
                enough_for_final = (
                    should_finish
                    and duration > overlap_seconds + 0.8
                )

                if enough_for_window or enough_for_final:
                    audio = self.recorder.pop_live_chunk(
                        overlap_seconds=overlap_seconds
                    )
                    if audio is not None and len(audio) > 0:
                        self._transcribe_live_array(
                            audio,
                            overlap_seconds=overlap_seconds,
                        )
                    continue

                if should_finish:
                    break
                time.sleep(0.15)

            self.after(0, self._live_finished)
        except Exception as exc:
            self.after(
                0,
                lambda error=exc: self._show_error(
                    "Живое распознавание",
                    error,
                ),
            )

    def _transcribe_live_array(
        self,
        audio,
        overlap_seconds: float,
    ) -> None:
        if self.transcriber is None:
            raise RuntimeError("Модель Whisper ещё не загружена.")

        duration = len(audio) / self.recorder.sample_rate
        domain_prompt = self.postprocessor.build_prompt(
            self.prompt_entry.get().strip()
        )
        context_tail = self.live_context_text[-500:]
        prompt = (
            f"{domain_prompt}\nПредыдущий контекст: {context_tail}"
            if context_tail
            else domain_prompt
        )

        temp_dir = (
            self.project.folder / ".live_temp"
            if self.project
            else Path(tempfile.gettempdir())
        )
        temp_dir.mkdir(parents=True, exist_ok=True)
        base_ms = int(self.live_processed_seconds * 1000)
        raw_path = temp_dir / f"chunk_{base_ms:010d}_raw.wav"
        clean_path = temp_dir / f"chunk_{base_ms:010d}_clean.wav"
        sf.write(raw_path, audio, self.recorder.sample_rate)

        input_path = raw_path
        if self.enhance_switch.get():
            input_path = enhance_speech(raw_path, clean_path)

        try:
            segments = self.transcriber.transcribe(
                input_path,
                language=self.config_data.get("language", "ru"),
                beam_size=int(self.config_data.get("beam_size_live", 3)),
                temperature=float(self.config_data.get("temperature", 0.0)),
                initial_prompt=prompt,
                live_mode=True,
                no_speech_threshold=float(
                    self.config_data.get("no_speech_threshold", 0.55)
                ),
                log_prob_threshold=float(
                    self.config_data.get("log_prob_threshold", -1.0)
                ),
                compression_ratio_threshold=float(
                    self.config_data.get(
                        "compression_ratio_threshold",
                        2.4,
                    )
                ),
            )

            lines = []
            accepted_text = []
            for segment in segments:
                # В окнах с перекрытием пропускаем повтор начала.
                if (
                    not self.live_first_chunk
                    and segment.end <= overlap_seconds + 0.25
                ):
                    continue

                absolute_start = self.live_processed_seconds + segment.start
                total = int(absolute_start)
                hours, remainder = divmod(total, 3600)
                minutes, seconds = divmod(remainder, 60)
                stamp = (
                    f"{hours:02}:{minutes:02}:{seconds:02}"
                    if hours
                    else f"{minutes:02}:{seconds:02}"
                )
                lines.append(f"[{stamp}] {segment.text}")
                accepted_text.append(segment.text)

            if lines:
                block = "\n".join(lines) + "\n"
                if self.correction_switch.get():
                    block = self.postprocessor.correct(block) + "\n"
                context_update = " ".join(accepted_text)
                self.after(
                    0,
                    lambda value=block, ctx=context_update:
                        self._append_live_text(value, ctx),
                )
        finally:
            step = duration
            if duration > overlap_seconds:
                step = duration - overlap_seconds
            self.live_processed_seconds += step
            self.live_first_chunk = False

            for path in (raw_path, clean_path):
                try:
                    path.unlink(missing_ok=True)
                except Exception:
                    pass

    def _append_live_text(self, text: str, context_text: str = "") -> None:
        self.transcript_box.insert("end", text)
        if context_text:
            self.live_context_text = (
                f"{self.live_context_text} {context_text}"
            ).strip()
        self.transcript_box.see("end")
        self.status_label.configure(text="Статус: речь распознаётся в реальном времени...")
        if self.project is not None:
            self.project.save(self._collect_meeting())

    def _live_finished(self) -> None:
        self.save_project()
        self._cleanup_live_temp()

        if (
            self.auto_refine_switch.get()
            and self.current_audio_path is not None
            and self.current_audio_path.exists()
        ):
            self.status_label.configure(
                text="Статус: запускается высокоточная финальная расшифровка..."
            )
            self.start_button.configure(state="disabled")
            self._start_high_accuracy_refinement(self.current_audio_path)
        else:
            self.start_button.configure(state="normal")
            self.status_label.configure(
                text="Статус: ✅ живая черновая расшифровка завершена"
            )

    def _recognize_full_audio(
        self,
        audio_path: Path,
        transcriber: Transcriber | None = None,
    ) -> None:
        try:
            engine = transcriber or self.transcriber
            if engine is None:
                raise RuntimeError("Модель Whisper ещё не загружена.")

            prompt = self.postprocessor.build_prompt(
                self.prompt_entry.get().strip()
            )
            clean_path = audio_path.with_name(
                f"{audio_path.stem}_asr_clean.wav"
            )
            input_path = audio_path
            if self.enhance_switch.get():
                input_path = enhance_speech(audio_path, clean_path)

            segments = engine.transcribe(
                input_path,
                language=self.config_data.get("language", "ru"),
                beam_size=int(self.config_data.get("beam_size_final", 5)),
                temperature=float(self.config_data.get("temperature", 0.0)),
                initial_prompt=prompt,
                live_mode=False,
                no_speech_threshold=float(
                    self.config_data.get("no_speech_threshold", 0.55)
                ),
                log_prob_threshold=float(
                    self.config_data.get("log_prob_threshold", -1.0)
                ),
                compression_ratio_threshold=float(
                    self.config_data.get(
                        "compression_ratio_threshold",
                        2.4,
                    )
                ),
            )
            text = format_segments(segments)
            if self.correction_switch.get():
                text = self.postprocessor.correct(text)

            if clean_path.exists():
                clean_path.unlink(missing_ok=True)

            self.after(
                0,
                lambda result=text: self._show_transcript(result),
            )
        except Exception as exc:
            self.after(
                0,
                lambda error=exc: self._show_error(
                    "Распознавание",
                    error,
                ),
            )

    def _start_high_accuracy_refinement(self, audio_path: Path) -> None:
        if self.final_refine_running:
            return
        self.final_refine_running = True
        threading.Thread(
            target=self._high_accuracy_refine_worker,
            args=(audio_path,),
            daemon=True,
        ).start()

    def _high_accuracy_refine_worker(self, audio_path: Path) -> None:
        live_model_name = self.config_data.get("model", "medium")
        final_model_name = self.final_model_combo.get().strip() or "large-v3"

        try:
            # Освобождаем живую модель перед large-v3, чтобы уменьшить риск нехватки RAM.
            self.transcriber = None
            gc.collect()

            self.after(
                0,
                lambda: self.model_status_label.configure(
                    text=f"Финальная загрузка: {final_model_name}"
                ),
            )
            final_engine = Transcriber(
                model_name=final_model_name,
                device=self.config_data.get("device", "cpu"),
                compute_type=self.config_data.get("compute_type", "int8"),
                cpu_threads=int(self.config_data.get("cpu_threads", 4)),
                num_workers=int(self.config_data.get("num_workers", 1)),
            )
            self.loaded_model_name = final_model_name
            self._recognize_full_audio(audio_path, transcriber=final_engine)

            # После завершения остаёмся на точной модели.
            self.transcriber = final_engine
            self.config_data["model"] = final_model_name
            self._save_config()
            self.after(
                0,
                lambda: self.model_status_label.configure(
                    text=f"Загружена: {final_model_name}"
                ),
            )
        except Exception as exc:
            self.after(
                0,
                lambda error=exc: self._show_error(
                    "Финальная расшифровка",
                    error,
                ),
            )
        finally:
            self.final_refine_running = False
        self.postprocessor = TextPostprocessor()

    def retranscribe_full_audio(self) -> None:
        audio_path = self._find_current_audio()
        if audio_path is None:
            messagebox.showwarning("Аудио", "Аудиофайл текущего совещания не найден.")
            return
        if self.recorder.recording:
            messagebox.showwarning("Аудио", "Сначала остановите запись.")
            return
        if not messagebox.askyesno(
            "Уточнить стенограмму",
            "Перераспознать весь файл? Текущий текст будет заменён.",
        ):
            return
        self.status_label.configure(
            text="Статус: высокоточная расшифровка полного аудиофайла..."
        )
        self.start_button.configure(state="disabled")
        self._start_high_accuracy_refinement(audio_path)

    def _find_current_audio(self) -> Path | None:
        if self.current_audio_path is not None and self.current_audio_path.exists():
            return self.current_audio_path
        if self.project is None:
            return None
        files = sorted(self.project.folder.glob("audio_*.wav"))
        return files[-1] if files else None

    def delete_audio(self) -> None:
        if self.recorder.recording:
            messagebox.showwarning("Удаление аудио", "Сначала остановите запись.")
            return
        if self.project is None:
            messagebox.showwarning("Удаление аудио", "Текущий проект не создан.")
            return

        files = list(self.project.folder.glob("audio_*.wav"))
        if not files:
            messagebox.showinfo("Удаление аудио", "Аудиофайлы не найдены.")
            return

        if not messagebox.askyesno(
            "Удаление аудио",
            f"Удалить аудиофайлы ({len(files)} шт.) без возможности восстановления?\n"
            "Стенограмма и протокол останутся.",
        ):
            return

        errors = []
        for file in files:
            try:
                file.unlink()
            except Exception as exc:
                errors.append(f"{file.name}: {exc}")

        self.current_audio_path = None
        if errors:
            messagebox.showerror("Удаление аудио", "\n".join(errors))
        else:
            self.status_label.configure(text="Статус: аудиофайлы удалены")
            messagebox.showinfo("Удаление аудио", "Аудиофайлы удалены.")

    def _cleanup_live_temp(self) -> None:
        if self.project is None:
            return
        temp_dir = self.project.folder / ".live_temp"
        if temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)
            
    def _show_transcript(self, text: str) -> None:
        logger.info("Расшифровка завершена. Символов=%d", len(text))
        self.transcript_box.delete("1.0", "end")
        self.transcript_box.insert("1.0", text)
        self.status_label.configure(
            text="Статус: ✅ распознавание завершено"
        )
        self.start_button.configure(state="normal")
        self.save_project()

    def analyze_transcript(self) -> None:
        text = self.transcript_box.get("1.0", "end").strip()
        if not text:
            messagebox.showwarning(
                "Черновик протокола",
                "Стенограмма пока пуста.",
            )
            return

        summary = build_summary(text)
        decisions = extract_decisions(text)
        suggested_tasks = extract_tasks(text)

        self.summary_box.delete("1.0", "end")
        self.summary_box.insert("1.0", summary)

        self.discussion_box.delete("1.0", "end")
        self.discussion_box.insert("1.0", text)

        self.decisions_box.delete("1.0", "end")
        self.decisions_box.insert(
            "1.0",
            "\n".join(f"{index}. {item}" for index, item in enumerate(decisions, 1))
        )

        existing = {task.description.lower() for task in self.tasks}
        for task in suggested_tasks:
            if task.description.lower() not in existing:
                self.tasks.append(task)
        self._render_tasks()

        self.tabview.set("Протокол")
        self.save_project()
        messagebox.showinfo(
            "Черновик протокола",
            "Черновик создан. Проверьте решения и поручения перед экспортом.",
        )

    def _update_timer(self) -> None:
        if not self.recorder.recording or self.recording_started_at is None:
            return

        elapsed = int(time.time() - self.recording_started_at)
        hours, remainder = divmod(elapsed, 3600)
        minutes, seconds = divmod(remainder, 60)

        self.timer_label.configure(
            text=f"{hours:02}:{minutes:02}:{seconds:02}"
        )
        self.timer_job = self.after(500, self._update_timer)

    def _update_level(self) -> None:
        if not self.recorder.recording:
            return

        level = min(self.recorder.last_level * 8.0, 1.0)
        self.level_bar.set(level)
        self.level_job = self.after(100, self._update_level)

    def _stop_timer_and_level(self) -> None:
        if self.timer_job is not None:
            self.after_cancel(self.timer_job)
            self.timer_job = None
        if self.level_job is not None:
            self.after_cancel(self.level_job)
            self.level_job = None
        self.level_bar.set(0)

    def _schedule_autosave(self) -> None:
        seconds = max(10, int(self.config_data.get("autosave_seconds", 30)))
        self.autosave_job = self.after(seconds * 1000, self._autosave)

    def _autosave(self) -> None:
        try:
            if self.project is not None:
                self.project.save(self._collect_meeting())
                self.status_label.configure(
                    text="Статус: автосохранение выполнено"
                )
        except Exception as exc:
            print(f"Autosave error: {exc}")
        finally:
            self._schedule_autosave()

    def add_task(self) -> None:
        description = self.task_entry.get().strip()
        if not description:
            messagebox.showwarning("Поручение", "Введите текст поручения.")
            return

        self.tasks.append(
            Task(
                responsible=self.responsible_entry.get().strip(),
                description=description,
                deadline=self.deadline_entry.get().strip(),
                status=self.status_combo.get(),
            )
        )
        self.task_entry.delete(0, "end")
        self._render_tasks()
        self.save_project()

    def remove_last_task(self) -> None:
        if self.tasks:
            self.tasks.pop()
            self._render_tasks()
            self.save_project()

    def _render_tasks(self) -> None:
        self.tasks_box.delete("1.0", "end")
        if not self.tasks:
            self.tasks_box.insert("1.0", "Поручения пока не добавлены.")
            return

        lines = []
        for number, task in enumerate(self.tasks, start=1):
            lines.append(
                f"{number}. {task.description}\n"
                f"   Ответственный: {task.responsible or '—'}\n"
                f"   Срок: {task.deadline or '—'}\n"
                f"   Статус: {task.status}\n"
            )
        self.tasks_box.insert("1.0", "\n".join(lines))

    def _collect_meeting(self) -> MeetingData:
        return MeetingData(
            title=self.title_entry.get().strip(),
            chairman=self.chairman_entry.get().strip(),
            secretary=self.secretary_entry.get().strip(),
            place=self.place_entry.get().strip(),
            agenda=self.agenda_box.get("1.0", "end").strip(),
            discussion=self.discussion_box.get("1.0", "end").strip(),
            decisions=self.decisions_box.get("1.0", "end").strip(),
            transcript=self.transcript_box.get("1.0", "end").strip(),
            summary=self.summary_box.get("1.0", "end").strip(),
            tasks=list(self.tasks),
        )

    def save_project(self) -> None:
        try:
            if self.project is None:
                self.project = MeetingProject(self.title_entry.get())

            meeting = self._collect_meeting()
            self.project.save(meeting)
            logger.info("Проект сохранён: %s", self.project.folder)
            self.status_label.configure(
                text=f"Статус: проект сохранён — {self.project.folder.name}"
            )
        except Exception as exc:
            self._show_error("Сохранение", exc)

    def open_project(self) -> None:
        folder = filedialog.askdirectory(
            title="Выберите папку совещания",
            initialdir=str(Path("archive").resolve()),
        )
        if not folder:
            return
        self._open_project_folder(Path(folder))

    def _open_project_folder(self, folder: Path) -> None:
        try:
            self.project = MeetingProject.from_folder(folder)
            meeting = self.project.load()
            self._fill_meeting(meeting)
            self.status_label.configure(
                text=f"Статус: открыт проект — {folder.name}"
            )
            self.tabview.set("Запись")
        except Exception as exc:
            self._show_error("Открытие проекта", exc)

    def _fill_meeting(self, meeting: MeetingData) -> None:
        entries = [
            (self.title_entry, meeting.title),
            (self.chairman_entry, meeting.chairman),
            (self.secretary_entry, meeting.secretary),
            (self.place_entry, meeting.place),
        ]
        for entry, value in entries:
            entry.delete(0, "end")
            entry.insert(0, value)

        boxes = [
            (self.agenda_box, meeting.agenda),
            (self.discussion_box, meeting.discussion),
            (self.decisions_box, meeting.decisions),
            (self.transcript_box, meeting.transcript),
            (self.summary_box, meeting.summary),
        ]
        for box, value in boxes:
            box.delete("1.0", "end")
            box.insert("1.0", value)

        self.tasks = list(meeting.tasks)
        self._render_tasks()

    def search_meetings(self) -> None:
        query = self.search_entry.get().strip()
        self.search_results = search_archive(query)

        self.search_box.delete("1.0", "end")

        if not self.search_results:
            self.search_box.insert("1.0", "Ничего не найдено.")
            self.result_combo.configure(values=["Нет результатов"])
            self.result_combo.set("Нет результатов")
            return

        labels = []
        lines = []
        for index, result in enumerate(self.search_results, start=1):
            label = f"{index}. {result.title} — {result.created_at[:10]}"
            labels.append(label)
            lines.append(
                f"{label}\n"
                f"Папка: {result.folder}\n"
                f"Фрагмент: {result.snippet}\n"
            )

        self.search_box.insert("1.0", "\n".join(lines))
        self.result_combo.configure(values=labels)
        self.result_combo.set(labels[0])

    def open_selected_search_result(self) -> None:
        if not self.search_results:
            return

        selected = self.result_combo.get()
        try:
            index = int(selected.split(".", 1)[0]) - 1
        except Exception:
            return

        if 0 <= index < len(self.search_results):
            self._open_project_folder(self.search_results[index].folder)

    def export_word_document(self) -> None:
        try:
            if self.project is None:
                self.project = MeetingProject(self.title_entry.get())

            meeting = self._collect_meeting()
            self.project.save(meeting)
            target = self.project.folder / "protocol.docx"
            export_word(target, meeting)
            messagebox.showinfo(
                "Готово",
                f"Документ сохранён:\n{target}",
            )
        except Exception as exc:
            self._show_error("Экспорт Word", exc)

    def export_tasks(self) -> None:
        try:
            if self.project is None:
                self.project = MeetingProject(self.title_entry.get())

            meeting = self._collect_meeting()
            self.project.save(meeting)
            target = self.project.folder / "tasks.xlsx"
            export_tasks_excel(target, meeting)
            messagebox.showinfo(
                "Готово",
                f"Поручения сохранены:\n{target}",
            )
        except Exception as exc:
            self._show_error("Экспорт Excel", exc)

    def open_project_folder(self) -> None:
        if self.project is None:
            messagebox.showwarning(
                "Папка проекта",
                "Сначала создайте или откройте совещание.",
            )
            return
        os.startfile(self.project.folder.resolve())

    def open_dictionary_file(self) -> None:
        path = Path("data/corporate_terms.json")
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_text(
                json.dumps(
                    {"terms": [], "replacements": {}},
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
        os.startfile(path.resolve())
        self.postprocessor.reload()
        self.status_label.configure(
            text="Статус: корпоративный словарь открыт"
        )

    def _show_error(self, title: str, exc: Exception) -> None:
        logger.exception("%s: %s", title, exc)
        self.status_label.configure(text=f"Статус: ошибка — {exc}")
        messagebox.showerror(title, str(exc))

    def _on_close(self) -> None:
        if self.recorder.recording:
            answer = messagebox.askyesno(
                "Выход",
                "Сейчас идёт запись. Завершить работу программы?",
            )
            if not answer:
                return
            try:
                if self.project is not None:
                    self.recorder.stop(self.project.folder)
            except Exception:
                pass

        if self.autosave_job is not None:
            try:
                self.after_cancel(self.autosave_job)
            except Exception:
                pass

        self.live_stop_event.set()
        try:
            if self.project is not None:
                self.project.save(self._collect_meeting())
        except Exception:
            pass
        self._cleanup_live_temp()

        self.destroy()
