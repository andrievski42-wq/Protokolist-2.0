from app_logging import setup_logging
from gui.main_window import ProtokolistApp


logger = setup_logging()


if __name__ == "__main__":
    logger.info("Программа запущена")

    try:
        app = ProtokolistApp()
        app.mainloop()
    except Exception:
        logger.exception("Критическая ошибка приложения")
        raise
    finally:
        logger.info("Программа завершена")