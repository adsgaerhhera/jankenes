import discord
from discord.ext import commands
import asyncio
import random
from dotenv import load_dotenv
import os
from flask import Flask
import threading

# ========================
# 環境変数の読み込み
# ========================
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID"))
KENNGAKU_ROLE_ID = int(os.getenv("KENNGAKU_ROLE_ID"))  # 👈 見学ロールIDを追加

# ========================
# Discord Botの準備
# ========================
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True
intents.voice_states = True
bot = commands.Bot(command_prefix="!", intents=intents)

# ========================
# Flaskアプリ（Koyeb用）
# ========================
app = Flask("")

@app.route("/")
def home():
    return "Bot is running!", 200

def run_http_server():
    port = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

def keep_alive():
    threading.Thread(target=run_http_server).start()

# ========================
# グローバル辞書でDMメッセージ管理
# ========================
user_messages = {}

@bot.event
async def on_ready():
    print(f"{bot.user.name} is ready!")

# ========================
# ✅ 見学ロール付与時にDM送信
# ========================
@bot.event
async def on_member_update(before, after):
    # 新しく追加されたロールをチェック
    new_roles = set(after.roles) - set(before.roles)
    for role in new_roles:
        if role.id == KENNGAKU_ROLE_ID:  # 👈 IDで判定
            try:
                message = await after.send(
                    f"こんにちは！あなたに '見学' ロールが付与されました！\n"
                    "このロールが付いた人はメッセージを送れなくなり、見ることしかできません。\n"
                    "それがいやな場合、以下にアクセスしてください:\n"
                    "https://discord.com/channels/1165775639798878288/1351191234961604640"
                )
                user_messages[after.id] = message.id
                print(f"{after.name} に見学ロールDMを送信しました")
            except discord.Forbidden:
                print(f"{after.name} へのDM送信ができません（許可されていないかDMがオフ）")
            break

    # ロール削除時の処理（必要があれば追加）
    removed_roles = set(before.roles) - set(after.roles)
    for role in removed_roles:
        if role.id == KENNGAKU_ROLE_ID:  # 👈 IDで判定
            if after.id in user_messages:
                try:
                    message_id = user_messages.pop(after.id)
                    channel = await after.create_dm()
                    message = await channel.fetch_message(message_id)
                    await message.delete()
                    print(f"{after.name} のDMメッセージを削除しました")
                except discord.Forbidden:
                    print(f"{after.name} のDM削除ができません（許可されていないかDMがオフ）")
                except discord.NotFound:
                    print(f"{after.name} のメッセージが見つかりませんでした")
            break

# ========================
# ✅ VC参加・退出ログを送信
# ========================
@bot.event
async def on_voice_state_update(member, before, after):
    log_channel = bot.get_channel(LOG_CHANNEL_ID)
    if not log_channel:
        return

    if before.channel is None and after.channel is not None:
        await log_channel.send(f"🔊 {member.display_name} が **{after.channel.name}** に参加しました！")
    elif after.channel is None and before.channel is not None:
        await log_channel.send(f"🔇 {member.display_name} が **{before.channel.name}** から退出しました。")

# ========================
# ✅ じゃんけんコマンド（省略なし）
# ========================
@bot.command()
async def janken(ctx, *args):
    participants = []

    if args:
        role_mentions = ctx.message.role_mentions
        if not role_mentions:
            await ctx.send("ロールが指定されていません！")
            return

        role = role_mentions[0]
        participants = [member for member in role.members if not member.bot]
        if not participants:
            await ctx.send(f"ロール {role.name} に該当するメンバーがいません！")
            return

        await ctx.send(f"{role.name} のメンバーにDMを送ります！")
    else:
        recruit_message = await ctx.send(
            "じゃんけん大会を開催します！参加する方は✋のリアクションを押してください！（15秒間）"
        )
        await recruit_message.add_reaction("✋")

        def reaction_check(reaction, user):
            return (
                user != bot.user
                and reaction.message.id == recruit_message.id
                and str(reaction.emoji) == "✋"
            )

        try:
            while True:
                reaction, user = await bot.wait_for("reaction_add", timeout=15.0, check=reaction_check)
                if user not in participants:
                    participants.append(user)
        except asyncio.TimeoutError:
            if not participants:
                await ctx.send("参加者がいませんでした！")
                return
            await ctx.send(f"{len(participants)}人の参加者が集まりました！")

    participants.append(bot.user)

    player_choices = {}
    reactions = ["👊", "✌️", "✋"]
    hand_map = {"👊": "グー", "✌️": "チョキ", "✋": "パー"}

    async def send_dm_and_wait(player):
        if player.bot:
            choice = random.choice(reactions)
            player_choices[player.id] = choice
            return

        try:
            dm_message = await player.send(
                "じゃんけんの手をリアクションで選んでください！\n"
                "👊: グー\n"
                "✌️: チョキ\n"
                "✋: パー"
            )
            for reaction in reactions:
                await dm_message.add_reaction(reaction)

            def check(reaction, user):
                return user == player and str(reaction.emoji) in reactions

            reaction, user = await bot.wait_for("reaction_add", timeout=30.0, check=check)
            player_choices[player.id] = str(reaction.emoji)
            await player.send(f"あなたの選択「{hand_map[reaction.emoji]}」を受け付けました！")

        except asyncio.TimeoutError:
            await player.send("時間切れになりました。今回は不参加とさせていただきます。")

    tasks = [send_dm_and_wait(member) for member in participants]
    await asyncio.gather(*tasks)

    active_players = {pid: choice for pid, choice in player_choices.items()}

    if len(active_players) < 2:
        await ctx.send("参加者が不足しています。じゃんけんを中止します。")
        return

    choices_set = set(active_players.values())

    results_message = "結果:\n各プレイヤーの選択:\n"
    for player_id, choice in active_players.items():
        player = bot.get_user(player_id)
        results_message += f"- {player.display_name if player else '不明'}: {hand_map[choice]}\n"

    if len(choices_set) == 1 or len(choices_set) == 3:
        results_message += "\n**あいこ（引き分け）です！**"
    else:
        win_table = {"👊": "✌️", "✌️": "✋", "✋": "👊"}
        hands_list = list(choices_set)
        if win_table[hands_list[0]] == hands_list[1]:
            winning_hand = hands_list[0]
        else:
            winning_hand = hands_list[1]

        winners = []
        losers = []

        for pid, choice in active_players.items():
            if choice == winning_hand:
                winners.append(pid)
            else:
                losers.append(pid)

        if winners:
            results_message += "\n\n**勝者:**\n"
            for winner_id in winners:
                player = bot.get_user(winner_id)
                results_message += f"- {player.display_name if player else '不明'}\n"
        if losers:
            results_message += "\n\n**敗者:**\n"
            for loser_id in losers:
                player = bot.get_user(loser_id)
                results_message += f"- {player.display_name if player else '不明'}\n"

    await ctx.send(results_message)

# ========================
# 起動！
# ========================
keep_alive()
bot.run(TOKEN)
