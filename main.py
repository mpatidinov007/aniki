import logging
from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from config import BOT_TOKEN, CHANNEL_ID, ADMIN1_ID, ADMIN2_ID, API_BEARER_TOKEN, GROQ_API_KEY
import requests
import asyncio
from datetime import datetime

logging.basicConfig(level=logging.INFO)

# Groq API sozlamalari
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# Foydalanuvchi xabar yuborgan vaqtini va tanlagan adminni saqlash
user_support_messages = {}  # {user_id: {'time': datetime, 'admin_id': int}}


# FSM States
class SupportState(StatesGroup):
    waiting_for_message = State()
    waiting_for_admin_reply = State()
    ai_support_chat = State()


class MovieSearch(StatesGroup):
    waiting_for_movie_title = State()


class AIState(StatesGroup):
    waiting_for_question = State()


# 🔍 Foydalanuvchi kanalga a'zo bo'lganligini tekshirish
async def check_subscription(user_id):
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in ["member", "administrator", "creator"]
    except Exception as e:
        print(f"Error checking subscription: {e}")
        return False


# 🎬 API dan barcha filmlarni olishhr
def get_all_movies():
    try:
        url = "https://api.aniki.uz/movies/"
        headers = {
            "Authorization": f"Bearer {API_BEARER_TOKEN}",
            "Content-Type": "application/json"
        }
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"API Error: Status {response.status_code}")
            return None
    except Exception as e:
        print(f"API Error: {e}")
        return None


# 🎬 Title bo'yicha film topish
def get_movie_by_title(title):
    try:
        movies = get_all_movies()
        if movies:
            title_lower = title.lower().strip()
            for movie in movies:
                if title_lower in movie['title'].lower():
                    return movie
        return None
    except Exception as e:
        print(f"Error finding movie: {e}")
        return None


# 🤖 Groq AI dan javob olish (Anime uchun)
def get_ai_response(question):
    try:
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }

        data = {
            "model": "llama-3.3-70b-versatile",
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Siz anikiUz ni shaxsiy suniy intellektisiz!"
                        "Aniki uz platformasini manzili aniki.uz"
                        "Sizning ismingiz AnikiAI"
                        "Siz anime bo'yicha mutaxassis yordamchisiz. "
                        "Faqat anime haqidagi savollarga javob bering. "
                        "Agar savol anime bilan bog'liq bo'lmasa, kechirim so'rab, "
                        "faqat anime mavzusida yordam bera olishingizni ayting. "
                        "Javoblaringizni qisqa va aniq bering (maksimum 400 so'z)."
                    )
                },
                {
                    "role": "user",
                    "content": question
                }
            ],
            "temperature": 0.7,
            "max_tokens": 1000,
            "top_p": 0.95,
            "stream": False
        }

        response = requests.post(GROQ_API_URL, headers=headers, json=data, timeout=30)

        if response.status_code == 200:
            result = response.json()
            if 'choices' in result and len(result['choices']) > 0:
                return result['choices'][0]['message']['content']
            else:
                return None
        else:
            return None

    except Exception as e:
        print(f"AI Error: {e}")
        return None


# 🤖 Support AI dan javob olish (Aniki.uz haqida)
def get_support_ai_response(question):
    try:
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }

        data = {
            "model": "llama-3.3-70b-versatile",
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Sen Aniki platformasing rasmiy suniy intellekti rolidasan shu rolni mohirona o'yna "
                        "Aniki.uz - bu uzbekcha anime platformasi:\n"
                        "- Sayt: aniki.uz\n"
                        "- Telegram kanal: @Aniki.uz\n"
                        "Doim muloyimlik bilan javob ber !"
                        "- Play Market va App Store'da ilovalar mavjud\n"
                        "- Til: O'zbekcha\n\n"
                        "Aniki 2025 - yili yaratilgan - Anime platformasi hisoblanadi"
                        "Siz faqat Aniki.uz va anime bilan bog'liq savollarga javob berasiz. "
                        "Boshqa mavzulardagi savollarga: 'Kechirasiz, men faqat Aniki.uz va anime haqida ma'lumot bera olaman' deb javob bering. "
                        "Matematik yoki umumiy savollarga javob bermang. "
                        "Adminga murojat qilishini sorang agar Aniki boyicha bilmagan malumotingni sorab qolsa ...!"
                        "Aniki - anime movie platformasi hisoblanadi !"
                        "Har doim o'zingizni Aniki.ai deb taniting va yordam taklif qiling."
                    )
                },
                {
                    "role": "user",
                    "content": question
                }
            ],
            "temperature": 0.7,
            "max_tokens": 1000,
            "top_p": 0.95,
            "stream": False
        }

        response = requests.post(GROQ_API_URL, headers=headers, json=data, timeout=30)

        if response.status_code == 200:
            result = response.json()
            if 'choices' in result and len(result['choices']) > 0:
                return result['choices'][0]['message']['content']
            else:
                return None
        else:
            return None

    except Exception as e:
        print(f"Support AI Error: {e}")
        return None


# Asosiy menyu
def get_main_menu():
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    keyboard.add(
        types.KeyboardButton("🎬 Anime yuklash"),
        types.KeyboardButton("🤖 AnikiAI"),
        types.KeyboardButton("📞 Yordam markazi"),
        types.KeyboardButton("ℹ️ Bot haqida"),
        types.KeyboardButton(
            "🌐 Aniki.uz saytini ochish",
            web_app=types.WebAppInfo(url="https://aniki.uz")
        )
    )
    return keyboard


# Qaytish tugmasi
def get_back_button():
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(types.KeyboardButton("🔙 Asosiy menyu"))
    return keyboard


# ============= START COMMAND =============
@dp.message_handler(commands=['start'], state='*')
async def start_handler(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state:
        await state.finish()

    user_id = message.from_user.id
    first_name = message.from_user.first_name

    print(f"User started bot - Name: {first_name}, ID: {user_id}")

    is_subscribed = await check_subscription(user_id)

    if not is_subscribed:
        keyboard = types.InlineKeyboardMarkup(row_width=1)
        keyboard.add(
            types.InlineKeyboardButton(
                text="🔗 Kanalga a'zo bo'lish", url=f"https://t.me/{CHANNEL_ID[1:]}"
            ),
            types.InlineKeyboardButton(
                text="✅ A'zo bo'ldim", callback_data="check_sub"
            )
        )

        await message.answer(
            f"👋 Salom, {first_name}!\n\n"
            f"Botdan foydalanish uchun quyidagi kanalga a'zo bo'ling 👇",
            reply_markup=keyboard
        )
    else:
        await message.answer(
            f"🎬 <b>Xush kelibsiz, {first_name}!</b>\n\n"
            f"🤖 Men <b>Aniki.ai</b> - sizning anime yordamchingizman!\n\n"
            f"📱 <b>Aniki.uz</b> haqida:\n"
            f"• 🌐 Sayt: <code>aniki.uz</code>\n"
            f"• 📺 Kanal: @Aniki.uz\n"
            f"❓ Sizga qanday yordam bera olaman?",
            parse_mode="HTML",
            reply_markup=get_main_menu()
        )


# ============= SUBSCRIPTION CHECK =============
@dp.callback_query_handler(lambda c: c.data == "check_sub", state='*')
async def check_sub_callback(callback: types.CallbackQuery, state: FSMContext):
    current_state = await state.get_state()
    if current_state:
        await state.finish()

    user_id = callback.from_user.id
    first_name = callback.from_user.first_name

    is_subscribed = await check_subscription(user_id)

    if is_subscribed:
        await callback.message.edit_text(
            f"✅ Rahmat, {first_name}!\nA'zo bo'lganingiz tasdiqlandi!"
        )
        await callback.message.answer(
            f"🎬 <b>Xush kelibsiz, {first_name}!</b>\n\n"
            f"🤖 Men <b>Aniki.ai</b> - sizning anime yordamchingizman!\n\n"
            f"📱 <b>Aniki.uz</b> haqida:\n"
            f"• 🌐 Sayt: <code>aniki.uz</code>\n"
            f"• 📺 Kanal: @Aniki.uz\n"
            f"• 📲 Play Market va App Store'da ilovalarimiz mavjud\n"
            f"❓ Sizga qanday yordam bera olaman?",
            parse_mode="HTML",
            reply_markup=get_main_menu()
        )
    else:
        await callback.answer("🚫 Hali ham a'zo emassiz JIGAR!", show_alert=True)


# ============= BACK TO MENU (PRIORITY) =============
@dp.message_handler(lambda message: message.text == "🔙 Asosiy menyu", state='*')
async def back_to_menu(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is not None:
        await state.finish()
    await message.answer("🏠 Asosiy menyu:", reply_markup=get_main_menu())


# ============= ANIME YUKLASH =============
@dp.message_handler(lambda message: message.text == "🎬 Anime yuklash", state='*')
async def movie_download_handler(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state:
        await state.finish()

    await MovieSearch.waiting_for_movie_title.set()
    await message.answer(
        "🎬 <b>Anime nomini kiriting:</b>\n\n"
        "Misol: <code>Naruto</code>,  <code>Demon Slayer</code>\n",
        parse_mode="HTML",
        reply_markup=get_back_button()
    )


@dp.message_handler(state=MovieSearch.waiting_for_movie_title, content_types=['text'])
async def process_movie_title(message: types.Message, state: FSMContext):
    if message.text == "🔙 Asosiy menyu":
        await state.finish()
        await message.answer("🏠 Asosiy menyu:", reply_markup=get_main_menu())
        return

    title = message.text
    await message.answer("⏳ Qidirilmoqda...")

    movie_data = get_movie_by_title(title)

    if movie_data:
        movie_title = movie_data.get('title', 'Noma\'lum')
        description = movie_data.get('description', 'Tavsif yo\'q')
        poster = movie_data.get('poster', '')
        release_year = movie_data.get('release_year', 'N/A')
        rating_avg = movie_data.get('rating_avg', 0)
        episodes = movie_data.get('episodes', [])

        genres = movie_data.get('genres', [])
        genre_names = ', '.join([g['name'] for g in genres]) if genres else 'Noma\'lum'

        caption = (
            f"🎬 <b>{movie_title}</b>\n\n"
            f"📝 {description}\n\n"
            f"📅 Yil: {release_year}\n"
            f"🎭 Janr: {genre_names}\n"
            f"⭐️ Reyting: {rating_avg}/5\n"
            f"📺 Epizodlar soni: {len(episodes)}"
        )

        keyboard = types.InlineKeyboardMarkup(row_width=5)
        buttons = []
        for ep in episodes:
            ep_num = ep.get('episode_number', 'N/A')
            buttons.append(
                types.InlineKeyboardButton(
                    text=f"{ep_num}",
                    callback_data=f"episode_{movie_data['id']}_{ep['id']}"
                )
            )

        for i in range(0, len(buttons), 5):
            keyboard.row(*buttons[i:i + 5])

        try:
            await bot.send_photo(
                chat_id=message.chat.id,
                photo=poster,
                caption=caption,
                parse_mode="HTML",
                reply_markup=keyboard
            )
        except:
            await message.answer(caption, parse_mode="HTML", reply_markup=keyboard)

        # ✅ YANGI: Asosiy menyu tugmasini qaytarish
        await message.answer(
            "🔍 Boshqa anime qidirish uchun nom yozing yoki menyuga qayting:",
            reply_markup=get_main_menu()
        )

    else:
        await message.answer(
            f"❌ <b>{title}</b> nomli anime topilmadi.\n\n"
            f"💡 Boshqa nom bilan urinib ko'ring yoki to'liq nomni kiriting.",
            parse_mode="HTML",
            reply_markup=get_main_menu()  # ✅ Bu ham bor edi
        )

    await state.finish()


# ============= EPIZOD YUKLASH =============
# ============= EPIZOD YUKLASH (YANGI CHIROYLI VERSIYA) =============
@dp.callback_query_handler(lambda c: c.data.startswith("episode_"), state='*')
async def send_episode(callback: types.CallbackQuery, state: FSMContext):
    try:
        parts = callback.data.split("_")
        movie_id = int(parts[1])
        episode_id = int(parts[2])

        movies = get_all_movies()
        movie = None
        episode = None

        for m in movies:
            if m['id'] == movie_id:
                movie = m
                for ep in m['episodes']:
                    if ep['id'] == episode_id:
                        episode = ep
                        break
                break

        if not episode:
            await callback.answer("Epizod topilmadi", show_alert=True)
            return

        video_url = episode.get('video_url')
        season = episode.get('season', '1')
        episode_num = episode.get('episode_number', 'N/A')
        duration = episode.get('duration', 'Nomaʼlum')
        description = episode.get('description', '')

        # Chiroyli caption
        caption = (
            f"🎬 *{movie['title']}*\n\n"
            f"📺 Mavsum: {season} | Epizod: {episode_num}\n"
            f"⏱ Davomiyligi: {duration}\n"
        )
        if description:
            caption += f"📝 {description}\n"

        await callback.answer("Tayyorlanmoqda...", show_alert=False)

        # 1-usul: Telegram ichida o'ynashga urinib ko'ramiz
        try:
            await bot.send_video(
                chat_id=callback.message.chat.id,
                video=video_url,
                caption=caption + "\n\nTez orada boshlanadi...",
                parse_mode="HTML",
                supports_streaming=True,
                disable_notification=True
            )
            return  # Agar muvaffaqiyatli bo'lsa — tugadi
        except:
            pass  # Agar ishlamasa — keyingi qadamga o'tamiz

        # 2-usul: Chiroyli link beramiz
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(
            types.InlineKeyboardButton(
                text="Koʻrish / Yuklab olish (Tez CDN)",
                url=video_url
            )
        )

        final_message = (
            f"{caption}\n\n"
            f"Real vaqtda koʻrish yoki yuklab olish uchun quyidagi tugmani bosing:\n\n"
            f"Tezlik: BunnyCDN (Yevropa + Osiyo)\n"
            f"Sifat: Toʻliq HD | Ovoz: Original\n"
            f"Internet tezligingizga qarab darhol boshlanadi!"
        )

        await callback.message.answer(
            text=final_message,
            parse_mode="HTML",
            reply_markup=keyboard,
            disable_web_page_preview=True
        )

    except Exception as e:
        print(f"Episode error: {e}")
        await callback.answer("Xatolik yuz berdi", show_alert=True)


# ============= AI YORDAMCHI =============
@dp.message_handler(lambda message: message.text == "🤖 AnikiAI", state='*')
async def ai_helper_handler(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state:
        await state.finish()

    await AIState.waiting_for_question.set()
    await message.answer(
        "🤖 <b>AI Yordamchi (Aiki.Ai)</b>\n\n"
        "Anime haqida savolingizni yozing.\n\n"
        "📝 Misol:\n"
        "• Eng yaxshi anime tavsiya qiling\n"
        "• Attack on Titan syujeti haqida\n\n"
        "💡 Faqat anime mavzusida yordam beraman",
        parse_mode="HTML",
        reply_markup=get_back_button()
    )


@dp.message_handler(state=AIState.waiting_for_question, content_types=['text'])
async def process_ai_question(message: types.Message, state: FSMContext):
    if message.text == "🔙 Asosiy menyu":
        await state.finish()
        await message.answer("🏠 Asosiy menyu:", reply_markup=get_main_menu())
        return

    question = message.text
    await bot.send_chat_action(message.chat.id, "typing")

    ai_response = get_ai_response(question)

    if ai_response:
        await message.answer(
            f"🤖 <b>AnikiAI:</b>\n\n{ai_response}",
            parse_mode="HTML"
        )
    else:
        await message.answer(
            "❌ AI xizmati hozirda ishlamayapti.\n\n"
            "💡 Yordam markazi orqali murojaat qilishingiz mumkin.",
            parse_mode="HTML"
        )


# ============= YORDAM MARKAZI (YANGI) =============
@dp.message_handler(lambda message: message.text == "📞 Yordam markazi", state='*')
async def support_handler(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state:
        await state.finish()

    # Admin tanlash tugmalari
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton(text="👨‍💼 Admin 1", callback_data="select_admin_1"),
        types.InlineKeyboardButton(text="👨‍💼 Admin 2", callback_data="select_admin_2")
    )

    await message.answer(
        "📞 <b>Yordam Markazi</b>\n\n"
        "Qaysi admin bilan bog'lanmoqchisiz?",
        parse_mode="HTML",
        reply_markup=keyboard
    )


# Admin tanlash
@dp.callback_query_handler(lambda c: c.data.startswith("select_admin_"), state='*')
async def select_admin_callback(callback: types.CallbackQuery, state: FSMContext):
    admin_num = callback.data.split("_")[-1]
    selected_admin_id = ADMIN1_ID if admin_num == "1" else ADMIN2_ID

    # Tanlangan adminni state ga saqlaymiz
    await state.update_data(selected_admin_id=selected_admin_id)

    await callback.message.edit_text(
        f"✅ <b>Admin {admin_num} tanlandi</b>\n\n"
        "📞 Endi savolingizni yoki murojaatingizni yozing.\n\n"
        "💡 Admin 10 daqiqa ichida javob bermasa,\n"
        "AI yordamchi yordam beradi.\n\n"
        "📝 Matn, rasm, video yoki fayl yuborishingiz mumkin.",
        parse_mode="HTML"
    )

    await SupportState.waiting_for_message.set()
    await callback.answer()


@dp.message_handler(state=SupportState.waiting_for_message, content_types=['text', 'photo', 'video', 'document'])
async def process_support_message(message: types.Message, state: FSMContext):
    if message.text == "🔙 Asosiy menyu":
        await state.finish()
        await message.answer("🏠 Asosiy menyu:", reply_markup=get_main_menu())
        return

    user_id = message.from_user.id
    username = message.from_user.username or "username yo'q"
    first_name = message.from_user.first_name

    # State dan tanlangan adminni olamiz
    data = await state.get_data()
    selected_admin_id = data.get('selected_admin_id', ADMIN1_ID)

    # User va tanlangan adminni saqlaymiz
    user_support_messages[user_id] = {
        'time': datetime.now(),
        'admin_id': selected_admin_id
    }

    admin_text = (
        f"📩 <b>Yangi murojaat!</b>\n\n"
        f"👤 Ism: {first_name}\n"
        f"🆔 ID: <code>{user_id}</code>\n"
        f"👨‍💼 Username: @{username}\n"
    )

    reply_keyboard = types.InlineKeyboardMarkup()
    reply_keyboard.add(
        types.InlineKeyboardButton(
            text="✍️ Javob berish",
            callback_data=f"reply_{user_id}"
        )
    )

    try:
        if message.photo:
            await bot.send_photo(
                selected_admin_id,
                photo=message.photo[-1].file_id,
                caption=admin_text + f"\n\n📷 Rasm\n💬 {message.caption or ''}",
                parse_mode="HTML",
                reply_markup=reply_keyboard
            )
        elif message.video:
            await bot.send_video(
                selected_admin_id,
                video=message.video.file_id,
                caption=admin_text + f"\n\n🎥 Video\n💬 {message.caption or ''}",
                parse_mode="HTML",
                reply_markup=reply_keyboard
            )
        elif message.document:
            await bot.send_document(
                selected_admin_id,
                document=message.document.file_id,
                caption=admin_text + f"\n\n📄 Fayl\n💬 {message.caption or ''}",
                parse_mode="HTML",
                reply_markup=reply_keyboard
            )
        else:
            await bot.send_message(
                selected_admin_id,
                admin_text + f"\n\n💬 Xabar:\n{message.text}",
                parse_mode="HTML",
                reply_markup=reply_keyboard
            )

        await message.answer(
            "✅ Xabaringiz adminga yuborildi!\n"
            "⏳ Admin 10 daqiqa ichida javob beradi...",
            reply_markup=types.ReplyKeyboardRemove()
        )

        await state.finish()

        # 10 daqiqa kutamiz
        await asyncio.sleep(600)

        if user_id in user_support_messages:
            keyboard = types.InlineKeyboardMarkup(row_width=2)
            keyboard.add(
                types.InlineKeyboardButton(text="🤖 SupportAI", callback_data=f"ai_help_{user_id}"),
                types.InlineKeyboardButton(text="👨‍💼 Admin kutish", callback_data=f"wait_admin_{user_id}")
            )

            await bot.send_message(
                user_id,
                "⏰ <b>Admin hozir javob berolmayapti!</b>\n\n"
                "💡 Tanlang:\n"
                "🤖 SupportAI - Tez javob olish\n"
                "👨‍💼 Admin kutish - Admindan javob kutish",
                parse_mode="HTML",
                reply_markup=keyboard
            )

    except Exception as e:
        print(f"Support error: {e}")
        await message.answer(
            f"❌ Xatolik: {str(e)}",
            reply_markup=get_main_menu()
        )
        await state.finish()


@dp.callback_query_handler(lambda c: c.data.startswith("ai_help_"), state='*')
async def ai_support_callback(callback: types.CallbackQuery, state: FSMContext):
    user_id = int(callback.data.split("_")[2])

    if user_id in user_support_messages:
        del user_support_messages[user_id]

    await callback.message.edit_text(
        "🤖 <b>AI Yordamchi (Aniki.ai)</b>\n\n"
        "Savolingizni yozing, men sizga yordam beraman!\n\n"
        "💡 Men Aniki.uz va anime haqida ma'lumot beraman.",
        parse_mode="HTML"
    )

    await SupportState.ai_support_chat.set()
    await callback.answer()


@dp.callback_query_handler(lambda c: c.data.startswith("wait_admin_"), state='*')
async def wait_admin_callback(callback: types.CallbackQuery):
    await callback.message.edit_text(
        "✅ <b>Admin javob berishini kutmoqdasiz</b>\n\n"
        "📞 Admin tez orada javob beradi.",
        parse_mode="HTML"
    )
    await callback.answer()


@dp.message_handler(state=SupportState.ai_support_chat, content_types=['text'])
async def ai_support_chat(message: types.Message, state: FSMContext):
    if message.text == "🔙 Asosiy menyu":
        await state.finish()
        await message.answer("🏠 Asosiy menyu:", reply_markup=get_main_menu())
        return

    question = message.text
    await bot.send_chat_action(message.chat.id, "typing")

    ai_response = get_support_ai_response(question)

    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(types.KeyboardButton("🔙 Asosiy menyu"))

    if ai_response:
        await message.answer(
            f"🤖 <b>Aniki.ai:</b>\n\n{ai_response}\n\n"
            f"❓ Boshqa savol bor?",
            parse_mode="HTML",
            reply_markup=keyboard
        )
    else:
        await message.answer(
            "❌ AI xizmati ishlamayapti.\n"
            "Admin bilan bog'laning.",
            reply_markup=get_main_menu()
        )
        await state.finish()


@dp.callback_query_handler(lambda c: c.data.startswith("reply_"), state='*')
async def admin_reply_callback(callback: types.CallbackQuery, state: FSMContext):
    user_id = int(callback.data.split("_")[1])

    if user_id in user_support_messages:
        del user_support_messages[user_id]

    await state.update_data(reply_to_user=user_id)

    await callback.message.answer(
        f"✍️ Foydalanuvchi <code>{user_id}</code> ga javobingizni yozing:",
        parse_mode="HTML"
    )
    await SupportState.waiting_for_admin_reply.set()
    await callback.answer()


@dp.message_handler(lambda m: m.from_user.id in [ADMIN1_ID, ADMIN2_ID], state=SupportState.waiting_for_admin_reply,
                    content_types=['text', 'photo', 'video', 'document'])
async def send_admin_reply(message: types.Message, state: FSMContext):
    data = await state.get_data()
    user_id = data.get('reply_to_user')

    if user_id:
        try:
            admin_msg = "📩 <b>Admin javobi:</b>\n\n"

            if message.photo:
                await bot.send_photo(
                    user_id,
                    photo=message.photo[-1].file_id,
                    caption=admin_msg + (message.caption or ""),
                    parse_mode="HTML"
                )
            elif message.video:
                await bot.send_video(
                    user_id,
                    video=message.video.file_id,
                    caption=admin_msg + (message.caption or ""),
                    parse_mode="HTML"
                )
            elif message.document:
                await bot.send_document(
                    user_id,
                    document=message.document.file_id,
                    caption=admin_msg + (message.caption or ""),
                    parse_mode="HTML"
                )
            else:
                await bot.send_message(
                    user_id,
                    admin_msg + message.text,
                    parse_mode="HTML"
                )

            await message.answer("✅ Javob yuborildi!")
        except Exception as e:
            await message.answer(f"❌ Xatolik: {e}")

    await state.finish()


# ============= BOT HAQIDA =============
@dp.message_handler(lambda message: message.text == "ℹ️ Bot haqida", state='*')
async def about_handler(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state:
        await state.finish()

    await message.answer(
        "ℹ️ <b>Aniki.ai - Rasmiy Bot</b>\n\n"
        "🤖 <b>Men kimman?</b>\n"
        "Men Aniki.uz platformasining AI yordamchisiman!\n\n"
        "🌐 <b>Aniki.uz haqida:</b>\n"
        "• Sayt: <code>aniki.uz</code>\n"
        "• Kanal: @Aniki.uz\n"
        "• Til: O'zbekcha\n"
        "• Ilovalar: Play Market, App Store\n\n"
        "⚡ <b>Imkoniyatlar:</b>\n"
        "🎬 Anime yuklash - Nom bo'yicha qidirish\n"
        "🤖 AI yordamchi - Anime maslahatlar\n"
        "📞 Yordam markazi - Admin + AI support\n\n"
        "✨ Bot doim yangilanmoqda!",
        parse_mode="HTML"
    )


# ============= CANCEL COMMAND =============
@dp.message_handler(commands=['cancel'], state='*')
async def cancel_handler(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is not None:
        await state.finish()
        await message.answer("❌ Amal bekor qilindi.", reply_markup=get_main_menu())
    else:
        await message.answer("Hozir hech qanday jarayon yo'q.", reply_markup=get_main_menu())


# ============= CLEANUP FUNCTION =============
async def on_startup(dp):
    """Bot ishga tushganda"""
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        print("✅ Webhook tozalandi")
    except Exception as e:
        print(f"⚠️ Cleanup error: {e}")


async def on_shutdown(dp):
    """Bot o'chirilganda"""
    await bot.session.close()
    await storage.close()
    print("👋 Bot to'xtatildi")


# ============= MAIN =============
if __name__ == "__main__":
    print("=" * 50)
    print("🤖 Aniki.ai Bot ishga tushdi!")
    print("=" * 50)
    print(f"📋 Admin 1 ID: {ADMIN1_ID}")
    print(f"📋 Admin 2 ID: {ADMIN2_ID}")
    print(f"📺 Kanal: {CHANNEL_ID}")
    print(f"🤖 AI Model: Groq (Llama 3.3 70B)")
    print(f"🌐 Platform: Aniki.uz")
    print(f"⚡ Status: ONLINE")
    print("=" * 50)

    executor.start_polling(
        dp,
        skip_updates=True,
        on_startup=on_startup,
        on_shutdown=on_shutdown
    )
