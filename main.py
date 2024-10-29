import time
import sys
import telebot
from telebot import types
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from datetime import datetime, timedelta
from requests import ReadTimeout
import os

bot = telebot.TeleBot("7254235102:AAEIU4y8wI1Pyf6UgGXEfm68leJL_dpF7g4")
bot.parse_mode = 'html'

jobstores = {
    'default': SQLAlchemyJobStore(url='sqlite:///jobs.sqlite')
}
scheduler = BackgroundScheduler(jobstores=jobstores)
scheduler.start()

admins = []

from outline_vpn.outline_vpn import OutlineVPN

api_url = ''
cert_sha256 = ""

client = OutlineVPN(api_url=api_url, cert_sha256=cert_sha256)


@bot.message_handler(commands=['start'])
def start_message_handler(message):
    if message.chat.id in admins:
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add(types.KeyboardButton("Добавить"), types.KeyboardButton("Продлить"))
        bot.send_message(message.chat.id, "Выберите действие:", reply_markup=markup)


@bot.message_handler(content_types=['text'])
def text_message_handler(message):
    if message.chat.id in admins:
        if message.text == "Добавить":
            bot.send_message(message.chat.id,
                             "Введите ID пользователя и срок действия ключа.\nПример: <b>272622925 30</b>")
            bot.register_next_step_handler(message, add_new_user)
        elif message.text == "Продлить":
            bot.send_message(message.chat.id,
                             "Введите ID пользователя и срок продления ключа.\nПример: <b>272622925 30</b>")
            bot.register_next_step_handler(message, extend_user)


@bot.callback_query_handler(func=lambda call: True)
def inline_handler(call):
    pass


def add_new_user(msg):
    try:
        data = msg.text.split()
        user_id = data[0]
        day_count = data[1]
        schedule_reminder(user_id, day_count)
        key = create_new_key(user_id,
                             f"Key {user_id}, expire:{add_days_to_str_remind(int(day_count)).strftime('%Y-%m-%d')}")
        print(key)
        bot.send_message(msg.chat.id, key.access_url)
    except Exception as er:
        print(er)
        bot.send_message(msg.chat.id, "Что-то пошло не так, попробуйте снова")
        bot.register_next_step_handler(msg, add_new_user)


def extend_user(msg):
    try:
        data = msg.text.split()
        user_id = data[0]
        day_count = data[1]
        old_exp_date = get_key_info(user_id).name.split(":")[1]
        date_of_expiring = datetime.now() + (str_to_datetime(old_exp_date) - datetime.now()) + timedelta(days=
                                                                                                         int(day_count))
        print('i am here!')
        scheduler.remove_job(str(user_id))
        scheduler.add_job(delete_key, 'date', run_date=date_of_expiring, args=[user_id], id=str(user_id))
        rename_key(user_id, f"Key {user_id}, expire:{date_of_expiring.strftime('%Y-%m-%d')}")
        bot.send_message(msg.chat.id, f"Изменил дату. Новая дата: {date_of_expiring.strftime('%Y-%m-%d')}")
    except Exception as er:
        print(er)
        bot.send_message(msg.chat.id, "Что-то пошло не так, попробуйте снова")
        bot.register_next_step_handler(msg, extend_user)


def rename_key(key_id: str, new_key_name: str):
    return client.rename_key(key_id, new_key_name)


def get_key_info(key_id: str):
    return client.get_key(key_id)


def create_new_key(key_id: str = None, name: str = None):
    return client.create_key(key_id=key_id, name=name, data_limit=None)


def delete_key(key_id: str):
    return client.delete_key(key_id)


def schedule_reminder(user_id, time_to_remind):
    run_date = datetime.now() + timedelta(minutes=int(time_to_remind))
    scheduler.add_job(delete_key, 'date', run_date=run_date, args=[user_id], id=str(user_id))


def add_days_to_str_remind(days):
    current_date = datetime.now().date()
    new_date = current_date + timedelta(days=days)
    return new_date


def str_to_datetime(date_str):
    date_obj = datetime.strptime(date_str, '%Y-%m-%d')
    return date_obj


if __name__ == '__main__':
    try:
        bot.infinity_polling(timeout=10, long_polling_timeout=5)
    except (ConnectionError, ReadTimeout) as e:
        sys.stdout.flush()
        os.execv(sys.argv[0], sys.argv)
    else:
        bot.infinity_polling(timeout=10, long_polling_timeout=5)
