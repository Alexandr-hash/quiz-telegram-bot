"""
HEALTH-CHECK СЕРВИС ДЛЯ МОНИТОРИНГА
====================================
Запускает простой HTTP сервер для проверки здоровья бота.
Используется системами мониторинга (UptimeRobot, StatusCake и т.д.)

Эндпоинты:
    GET /health     - Общий статус бота
    GET /ready      - Готовность к работе
    GET /live       - Проверка жив ли процесс
"""

import json
import socket
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Optional
import threading
import time

from src.utils.logger import setup_logger


logger = setup_logger("health")


class HealthHandler(BaseHTTPRequestHandler):
    """
    ОБРАБОТЧИК HTTP ЗАПРОСОВ ДЛЯ HEALTH-CHECK
    ------------------------------------------
    Обрабатывает запросы на проверку состояния бота.
    """
    
    # Ссылка на экземпляр бота для получения статуса
    bot_instance: Optional[object] = None
    
    def log_message(self, format, *args):
        """Кастомное логирование HTTP запросов"""
        logger.debug(f"HTTP {self.address_string()} - {format % args}")
    
    def do_GET(self):
        """Обработка GET запросов"""
        if self.path == '/health':
            self._handle_health()
        elif self.path == '/ready':
            self._handle_ready()
        elif self.path == '/live':
            self._handle_live()
        elif self.path == '/metrics':
            self._handle_metrics()
        else:
            self.send_response(404)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Not found"}).encode())
    
    def _handle_health(self):
        """Обработка запроса /health"""
        try:
            status_code = 200
            health_data = {
                "status": "healthy",
                "timestamp": time.time(),
                "service": "quiz-telegram-bot",
                "version": "1.0.0"
            }
            
            # Добавляем статус бота если доступен
            if HealthHandler.bot_instance:
                try:
                    bot_status = HealthHandler.bot_instance.get_status()
                    health_data["bot"] = {
                        "is_running": bot_status["bot"]["is_running"],
                        "initialized": bot_status["bot"]["initialized"],
                        "questions": bot_status["data"]["questions"]["total"],
                        "facts": bot_status["data"]["facts"]["total"]
                    }
                except Exception as e:
                    health_data["bot_error"] = str(e)
                    status_code = 503  # Service Unavailable
            
            self.send_response(status_code)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            self.wfile.write(json.dumps(health_data, indent=2).encode())
            
        except Exception as e:
            logger.error(f"Ошибка обработки health-check: {e}")
            self.send_response(500)
            self.end_headers()
    
    def _handle_ready(self):
        """Обработка запроса /ready (готовность к работе)"""
        try:
            if HealthHandler.bot_instance:
                status = HealthHandler.bot_instance.get_status()
                is_ready = status["bot"]["initialized"] and status["data"]["questions"]["total"] > 0
                
                response = {
                    "ready": is_ready,
                    "initialized": status["bot"]["initialized"],
                    "has_questions": status["data"]["questions"]["total"] > 0,
                    "has_facts": status["data"]["facts"]["total"] > 0
                }
                status_code = 200 if is_ready else 503
            else:
                response = {"ready": False, "error": "Bot not initialized"}
                status_code = 503
            
            self.send_response(status_code)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(response).encode())
            
        except Exception as e:
            logger.error(f"Ошибка обработки ready-check: {e}")
            self.send_response(500)
            self.end_headers()
    
    def _handle_live(self):
        """Обработка запроса /live (проверка жив ли процесс)"""
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({"alive": True}).encode())
    
    def _handle_metrics(self):
        """Обработка запроса /metrics (метрики для Prometheus)"""
        try:
            metrics = []
            
            # Базовые метрики
            metrics.append("# HELP quiz_bot_info Информация о боте")
            metrics.append("# TYPE quiz_bot_info gauge")
            metrics.append('quiz_bot_info{version="1.0.0",service="quiz-telegram-bot"} 1')
            
            # Метрики времени
            metrics.append("# HELP quiz_bot_uptime_seconds Время работы бота в секундах")
            metrics.append("# TYPE quiz_bot_uptime_seconds counter")
            
            # Добавляем метрики бота если доступны
            if HealthHandler.bot_instance:
                try:
                    status = HealthHandler.bot_instance.get_status()
                    
                    metrics.append("# HELP quiz_bot_questions_total Всего вопросов")
                    metrics.append("# TYPE quiz_bot_questions_total gauge")
                    metrics.append(f'quiz_bot_questions_total {status["data"]["questions"]["total"]}')
                    
                    metrics.append("# HELP quiz_bot_facts_total Всего фактов")
                    metrics.append("# TYPE quiz_bot_facts_total gauge")
                    metrics.append(f'quiz_bot_facts_total {status["data"]["facts"]["total"]}')
                    
                    metrics.append("# HELP quiz_bot_images_total Всего изображений")
                    metrics.append("# TYPE quiz_bot_images_total gauge")
                    metrics.append(f'quiz_bot_images_total {status["images"]["available"]}')
                    
                except Exception as e:
                    metrics.append(f"# ERROR getting bot metrics: {e}")
            
            response_text = "\n".join(metrics)
            
            self.send_response(200)
            self.send_header('Content-type', 'text/plain; version=0.0.4')
            self.end_headers()
            self.wfile.write(response_text.encode())
            
        except Exception as e:
            logger.error(f"Ошибка обработки metrics: {e}")
            self.send_response(500)
            self.end_headers()


def start_health_server(port: int = 8080, host: str = "localhost"):
    """
    ЗАПУСК HTTP СЕРВЕРА ДЛЯ HEALTH-CHECK
    -------------------------------------
    Запускает сервер в отдельном потоке.
    
    Args:
        port: Порт для сервера (по умолчанию 8080)
        host: Хост для сервера (по умолчанию localhost)
    
    Returns:
        Объект сервера (для остановки)
    """
    try:
        # Проверяем доступность порта
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex((host, port))
        sock.close()
        
        if result == 0:
            logger.warning(f"Порт {port} уже занят, health-check сервер не запущен")
            return None
        
        # Создаем и запускаем сервер
        server = HTTPServer((host, port), HealthHandler)
        
        # Запускаем в отдельном потоке
        server_thread = threading.Thread(
            target=server.serve_forever,
            daemon=True,
            name="HealthCheckServer"
        )
        server_thread.start()
        
        logger.info(f"Health-check сервер запущен на http://{host}:{port}")
        logger.info("Доступные эндпоинты:")
        logger.info(f"  http://{host}:{port}/health   - Общий статус")
        logger.info(f"  http://{host}:{port}/ready    - Готовность")
        logger.info(f"  http://{host}:{port}/live     - Проверка жив ли")
        logger.info(f"  http://{host}:{port}/metrics  - Метрики Prometheus")
        
        return server
        
    except Exception as e:
        logger.error(f"Ошибка запуска health-check сервера: {e}")
        return None


def set_bot_instance(bot):
    """
    УСТАНОВКА ССЫЛКИ НА ЭКЗЕМПЛЯР БОТА
    -----------------------------------
    Позволяет health-check серверу получать статус бота.
    
    Args:
        bot: Экземпляр QuizBot
    """
    HealthHandler.bot_instance = bot
    logger.debug("Ссылка на бот установлена для health-check сервера")


def stop_health_server(server):
    """
    ОСТАНОВКА HEALTH-CHECK СЕРВЕРА
    --------------------------------
    Корректно останавливает сервер.
    
    Args:
        server: Объект сервера от start_health_server
    """
    if server:
        server.shutdown()
        logger.info("Health-check сервер остановлен")