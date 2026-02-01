=== ИНСТРУКЦИЯ ПО НАСТРОЙКЕ ===

1. Скопируйте .env.example в .env и заполните:
   - BOT_TOKEN: получите у @BotFather
   - CHANNEL_ID: username канала (с @) или ID

2. Создайте файлы в папке data/:
   - data/questions.csv (на основе questions.csv.example)
   - data/facts.csv (на основе facts.csv.example)

3. Для фактов с картинками:
   - Создайте папку data/fact_images/
   - Загрузите туда JPG/PNG файлы

4. Запустите бота:
   - python src/bot.py
   - Или scripts/run_bot.bat