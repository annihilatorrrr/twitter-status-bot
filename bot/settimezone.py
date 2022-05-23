#!/usr/bin/env python3
"""Conversation for deleting stored stickers."""
from typing import Dict, cast

import pytz
from telegram import (
    Bot,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InlineQuery,
    InlineQueryResultArticle,
    InputTextMessageContent,
    Message,
    Update,
    User,
)
from telegram.ext import (
    ChosenInlineResultHandler,
    CommandHandler,
    ConversationHandler,
    InlineQueryHandler,
    MessageHandler,
    filters,
)
from thefuzz import fuzz

from bot.constants import REMOVE_KEYBOARD_KEY
from bot.userdata import CCT, UserData
from bot.utils import FALLBACK_HANDLER, TIMEOUT_HANDLER, remove_reply_markup

STATE = 42


async def start(update: Update, context: CCT) -> int:
    """Starts the conversation and asks for the timezone.

    Args:
        update: The Telegram update.
        context: The callback context as provided by the application.

    Returns:
        int: The next state.
    """
    user_data = cast(UserData, context.user_data)
    message = cast(Message, update.effective_message)
    message = await message.reply_text(
        f"Your current timezone is: {user_data.tzinfo}. Please press the button below to "
        "select a new timezone. You can scroll through the available options or type something to "
        "narrow down the options.",
        reply_markup=InlineKeyboardMarkup.from_button(
            InlineKeyboardButton(text="Click me 👆", switch_inline_query_current_chat=""),
        ),
    )
    cast(Dict, context.chat_data)[REMOVE_KEYBOARD_KEY] = message
    return STATE


async def handle_inline_query(update: Update, _: CCT) -> int:
    """Handles the inline query to show appropriate timezones.

    Args:
        update: The Telegram update.
        _: The callback context as provided by the application.

    Returns:
        int: The next state.
    """
    inline_query = cast(InlineQuery, update.inline_query)
    timezones = pytz.all_timezones
    if query := inline_query.query:
        timezones.sort(key=lambda tz: fuzz.ratio(tz, query), reverse=True)
    else:
        timezones.sort()

    await inline_query.answer(
        results=[
            InlineQueryResultArticle(
                id=tz, title=tz, input_message_content=InputTextMessageContent(tz)
            )
            for tz in timezones
        ],
        auto_pagination=True,
        cache_time=0,
    )

    return STATE


async def handle_timezone(update: Update, context: CCT) -> int:
    """Handles the selected timezone.

    Args:
        update: The Telegram update.
        context: The callback context as provided by the application.

    Returns:
        int: The next state.
    """
    user_data = cast(UserData, context.user_data)
    chosen_inline_result = update.chosen_inline_result
    user = cast(User, update.effective_user)

    if chosen_inline_result:
        user_data.tzinfo = chosen_inline_result.result_id
    else:
        message = cast(Message, update.effective_message)
        user_data.tzinfo = cast(str, message.text)

    await user.send_message(f"Your new timezone is {user_data.tzinfo}.")

    await remove_reply_markup(context)
    return ConversationHandler.END


def build_set_timezone_conversation(bot: Bot) -> ConversationHandler:
    """Builds the :class:`telegram.ext.ConversationHandler` used to set the timezone.

    Args:
        bot: The bot that runs this conversation.

    Returns:
        The ConversationHandler
    """
    return ConversationHandler(
        entry_points=[CommandHandler("set_timezone", start)],
        states={
            STATE: [
                InlineQueryHandler(handle_inline_query),
                # Use both CHRH and MH because we can't be sure which comes first …
                ChosenInlineResultHandler(handle_timezone),
                MessageHandler(filters.ViaBot(bot.id), handle_timezone),
            ],
            ConversationHandler.TIMEOUT: [TIMEOUT_HANDLER],
        },
        fallbacks=[FALLBACK_HANDLER],
        conversation_timeout=30,
        persistent=False,
        per_user=True,
        per_chat=False,
    )
